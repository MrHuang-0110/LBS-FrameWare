"""串口层：封装 pyserial，后台 RX 线程把字节路由给队列或数据回调。"""
from __future__ import annotations
import logging
import threading, queue, time
from typing import Callable

try:
    import serial
    import serial.tools.list_ports
except ImportError:  # 测试环境用 FakeSerial，pyserial 可能未装
    serial = None

_logger = logging.getLogger("lbs_firmware_studio.backend.serial_transport")

# 串口拔出/驱动错误时 in_waiting/read 会持续抛错；连续异常达此上限即退出 RX 线程，
# 避免无日志 50ms 忙循环空转（审查项 T2-S1）。
_RX_ERROR_RETRY_LIMIT = 3


class SerialTransport:
    link_kind = "serial"   # 供 deployer 区分链路(与 BleTransport.link_kind 对等)

    def __init__(self, serial_obj=None, reopen_factory: "Callable[[str, int], object] | None" = None,
                 port_lister: "Callable[[], set[str]] | None" = None):
        self._serial = serial_obj
        self._reopen_factory = reopen_factory
        self._port_lister = port_lister  # 返回当前存在的端口名集合；None=用 pyserial 探测
        self._rx_queue: queue.Queue[int] = queue.Queue()
        self._data_handler: Callable[[bytes], None] | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def set_reopen_factory(self, factory: "Callable[[str, int], object] | None") -> None:
        self._reopen_factory = factory

    def _port_present(self, port: str) -> bool:
        """端口当前是否存在。测试可注入 port_lister；生产用 pyserial。"""
        if self._port_lister is not None:
            return port in self._port_lister()
        if serial is not None:
            return port in {p.device for p in serial.tools.list_ports.comports()}
        return True

    @property
    def is_open(self) -> bool:
        return self._serial is not None and getattr(self._serial, "is_open", True)

    def open(self, port: str, baud: int) -> None:
        if self._serial is None:
            self._serial = serial.Serial(port=port, baudrate=baud, timeout=0.1)
        else:
            self._serial.timeout = 0.1
        # 打开后拉低 DTR/RTS，避免 MCU 误复位（FakeSerial 也有这两个属性，设置无害）
        for attr in ("dtr", "rts"):
            try:
                setattr(self._serial, attr, False)
            except Exception:
                pass

    def close(self) -> None:
        self.stop_rx()
        if self._serial and getattr(self._serial, "is_open", False):
            try:
                self._serial.close()
            except Exception:
                pass

    def write(self, data: bytes) -> int:
        if self._serial is None:
            raise RuntimeError("serial not open")
        return self._serial.write(data)

    def set_data_handler(self, handler: Callable[[bytes], None] | None) -> None:
        self._data_handler = handler
        if handler is not None:
            while True:
                try:
                    self._rx_queue.get_nowait()
                except queue.Empty:
                    break

    def start_rx(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._rx_loop, daemon=True)
        self._thread.start()

    def stop_rx(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def _rx_loop(self) -> None:
        consecutive_errors = 0
        while not self._stop.is_set():
            try:
                # 优先读缓冲区内「当前可用」的字节，有多少读多少，避免 read(64)
                # 为凑满 64 字节而阻塞满串口 timeout（8 字节的 ACK 会被拖满 ~100ms）。
                n = getattr(self._serial, "in_waiting", 0)
                if n:
                    chunk = self._serial.read(n)
                else:
                    # 无数据时读 1 字节（受串口 timeout 限制）阻塞等待，不忙等
                    chunk = self._serial.read(1)
            except Exception as exc:
                # 串口拔出/驱动错误时 read 持续抛错：记录日志（不再静默），连续异常
                # 达上限即退出，防无日志 50ms 忙循环空转（T2-S1）。偶发一次不退出。
                consecutive_errors += 1
                _logger.warning("串口 RX 读取异常(%d/%d): %r",
                                consecutive_errors, _RX_ERROR_RETRY_LIMIT, exc)
                if consecutive_errors >= _RX_ERROR_RETRY_LIMIT:
                    _logger.error("串口 RX 连续读取异常 %d 次，RX 线程退出", consecutive_errors)
                    break
                time.sleep(0.05)
                continue
            consecutive_errors = 0  # 正常读到（含超时空数据）即重置连续错误计数
            if not chunk:
                continue
            if self._data_handler is not None:
                try:
                    self._data_handler(bytes(chunk))
                except Exception as exc:
                    # 回调异常不得杀死 RX 线程（T2-S3）：记日志后继续。该异常属于
                    # 上层 handler 的缺陷，与 T2-S1 的 read 硬件异常计数相互独立，
                    # 不递增 consecutive_errors（那是串口读错误阈值，handler 异常
                    # 只是「丢一次回调」而非链路损坏）。
                    _logger.warning("数据回调异常(已忽略，RX 线程继续): %r", exc)
            else:
                for b in chunk:
                    self._rx_queue.put(b)

    def read_byte(self, timeout: float) -> int | None:
        if self._data_handler is not None:
            return None
        try:
            return self._rx_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def wait_for_reopen(self, port: str, baud: int, retries: int, delay: float,
                        post_delay: float = 0.0, disappear_timeout: float = 5.0) -> bool:
        """复位后重连。真机上复位帧发出到端口消失有延迟(实测~1.4s)，若 close 后
        固定睡一小段就抢开，会打开一个「即将失效」的旧句柄 -> 首次写入 winerror 22。
        正确顺序：等端口真正消失 -> 等它重现 -> 再打开 -> 等设备初始化(post_delay)。

        若在 disappear_timeout 内端口始终未消失（设备已在固件模式/不重枚举），
        则退化为直接打开（覆盖「第二次运行」场景）。
        """
        was_rx = self._thread is not None and self._thread.is_alive()
        self.close()

        # 阶段1：等端口从「存在」变为「消失」（USB 重新枚举开始）
        deadline = time.monotonic() + disappear_timeout
        disappeared = False
        while time.monotonic() < deadline:
            if not self._port_present(port):
                disappeared = True
                break
            time.sleep(0.05)

        # 阶段2：若发生了消失，等它重现
        if disappeared:
            reappear_deadline = time.monotonic() + max(delay * retries, disappear_timeout)
            while time.monotonic() < reappear_deadline:
                if self._port_present(port):
                    break
                time.sleep(0.05)

        # 阶段3：端口就绪，尝试打开（带重试），成功后等设备初始化
        for attempt in range(retries):
            if attempt:
                time.sleep(delay)
            try:
                if self._reopen_factory is not None:
                    self._serial = self._reopen_factory(port, baud)
                elif serial is not None:
                    self._serial = serial.Serial(port=port, baudrate=baud, timeout=0.1)
                else:
                    self._serial.is_open = True
                self._rx_queue = queue.Queue()
                # 端口重现且能打开 != 设备就绪：USB CDC 接口/固件复位后需初始化时间，
                # 过早写入会被驱动拒绝 (winerror 22 ERROR_BAD_COMMAND)。等待设备就绪。
                if post_delay > 0:
                    time.sleep(post_delay)
                if was_rx:
                    self.start_rx()  # close() 停了 RX 线程，这里重新武装
                return True
            except Exception:
                continue
        return False
