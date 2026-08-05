"""蓝牙(BLE)传输层：方法签名与 SerialTransport 对等（鸭子类型），
把 bleak(asyncio) 封装进专用事件循环线程，notify 回调推入队列/回调，
使协议层 read_byte 拉取逻辑零改动。"""
from __future__ import annotations
import asyncio
import os
import queue
import threading
import time
from pathlib import Path
from typing import Callable

try:
    from bleak import BleakClient
except ImportError:  # 未安装 bleak：串口功能不受影响，选蓝牙时才报错
    BleakClient = None


# ---- 诊断日志（排障用）：默认关闭，环境变量 LBS_BLE_DEBUG=1 开启 ----
# 纯旁路记录，绝不影响任何收发逻辑。
# 模块加载时缓存开关状态 + 日志路径，避免每次热路径调用都读环境变量 / Path.home()。
_BLE_DEBUG_ENABLED = bool(os.environ.get("LBS_BLE_DEBUG"))
_BLE_LOG_PATH = Path.home() / "ble_debug.log"


def _ble_log(msg: str) -> None:
    if not _BLE_DEBUG_ENABLED:
        return
    try:
        line = f"[{time.strftime('%H:%M:%S')}] {msg}\n"
        with open(_BLE_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass  # 诊断日志绝不能反过来影响主流程


def _hex_preview(data: bytes, limit: int = 32) -> str:
    head = data[:limit]
    tail = "..." if len(data) > limit else ""
    return head.hex(" ") + tail


def _find_transparent_chars(pairs) -> tuple[str, str, bool]:
    """从 [(uuid, properties)] 里挑一个 notify(收) + 一个 write(发) 特征值。
    第三个返回值 write_response：所选写特征值是否支持带响应写(write)。
    带响应写会逐片等设备 BLE 层确认，形成天然背压，避免多分片背靠背连发时
    设备侧透传缓冲溢出丢字节（真机 YMODEM 1024B 数据块经蓝牙被 NAK 的根因）。"""
    notify_uuid = write_uuid = None
    write_response = False
    for uuid, props in pairs:
        if notify_uuid is None and ("notify" in props or "indicate" in props):
            notify_uuid = uuid
        if write_uuid is None and ("write" in props or "write-without-response" in props):
            write_uuid = uuid
            write_response = "write" in props   # 支持带响应写则优先用它做流控
    if notify_uuid is None or write_uuid is None:
        raise RuntimeError("未发现可透传特征值")
    return notify_uuid, write_uuid, write_response


# ---- 断开超时（T2-B2）----
# close()/wait_for_reopen() 等待设备断开命令的单次上限。设备无响应（断开命令挂起）
# 时主线程最多阻塞该时长；Task 18 已让"设备已断"场景（_connected=False）走守卫
# 快速返回，不进入此处等待。
_DISCONNECT_TIMEOUT = 2.0


class _RealBleakClient:
    """生产用：包装 bleak.BleakClient，实现 BleTransport 依赖的客户端接口。"""
    def __init__(self, address: str):
        self._c = BleakClient(address)

    @property
    def is_connected(self) -> bool:
        return self._c.is_connected

    @property
    def mtu_size(self) -> int:
        return getattr(self._c, "mtu_size", 23)

    async def connect(self):
        await self._c.connect()

    async def disconnect(self):
        await self._c.disconnect()

    async def start_notify(self, uuid, cb):
        await self._c.start_notify(uuid, cb)

    async def stop_notify(self, uuid):
        await self._c.stop_notify(uuid)

    def set_disconnected_callback(self, cb):
        # 透传 bleak 的设备侧断开回调（关机/超距触发），供 BleTransport 检测断线。
        # 旧版 bleak（<0.19）无此 API：getattr 防御，断线检测退化为写失败探测（不崩）。
        set_cb = getattr(self._c, "set_disconnected_callback", None)
        if set_cb is not None:
            set_cb(cb)

    async def write_gatt_char(self, uuid, data, response: bool = False):
        await self._c.write_gatt_char(uuid, data, response=response)

    async def get_characteristics(self):
        # 跨 bleak 版本稳定：get_services() 在所有版本均可用（client.services 属性仅新版
        # 才有）。用户环境 bleak 版本旧 → 原 `self._c.services` 抛 AttributeError
        # （"BleakClient object has no attribute"），连接失败。
        services = await self._c.get_services()
        pairs = []
        for svc in services:
            for ch in svc.characteristics:
                pairs.append((ch.uuid, list(ch.properties)))
        return pairs


def _default_client_factory(address: str):
    if BleakClient is None:
        raise RuntimeError("未安装蓝牙支持(bleak)")
    return _RealBleakClient(address)


class BleTransport:
    link_kind = "ble"   # 供 deployer 区分链路：蓝牙 YMODEM 须用 128B 块(见 deployer._make_protocol)

    def __init__(self, client_factory: "Callable[[str], object] | None" = None,
                 scanner: "Callable[[float], list] | None" = None,
                 reconnect_name: "str | None" = None):
        self._client_factory = client_factory or _default_client_factory
        self._scanner = scanner
        self._reconnect_name = reconnect_name
        # 跨线程数据通路锁：_on_notify(事件循环线程) 与 set_data_handler/_try_connect(主线程)
        # 对 _data_handler/_rx_queue 的读写全部经此锁串行化(RLock 防 handler 内重入)。
        self._lock = threading.RLock()
        self._address: str | None = None
        self._client = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None
        self._rx_queue: queue.Queue[int] = queue.Queue()
        self._data_handler: Callable[[bytes], None] | None = None
        self._disconnected_cb: Callable[[], None] | None = None
        self._notify_uuid: str | None = None
        self._write_uuid: str | None = None
        self._write_response = False   # 写特征值是否支持带响应写(逐片确认，做背压)
        self._mtu = 20
        self._connected = False

    def set_disconnected_callback(self, cb: "Callable[[], None] | None") -> None:
        """注册「链路断开」回调：设备侧断开（关机/超距，bleak 回调在事件循环线程执行）
        时调用（I1 修复：BLE 拔线/关机 UI 实时切回未连接，与 SerialTransport 对齐）。
        回调需自行保证线程安全（如 Qt 信号转发到主线程）。"""
        self._disconnected_cb = cb

    # ---- 事件循环线程 ----
    def _ensure_loop(self) -> None:
        if self._loop is not None and self._loop_thread and self._loop_thread.is_alive():
            return
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._loop_thread.start()

    def _run(self, coro, timeout: float = 30.0):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout=timeout)

    # ---- 连接 ----
    def open(self, port: str, baud: int = 0) -> None:
        self._address = port
        self._ensure_loop()
        self._run(self._connect())

    async def _connect(self) -> None:
        self._client = self._client_factory(self._address)
        # 注册设备侧断开回调（T2-B1）：在 connect 之前注册，连接刚建立即断开也不漏回调。
        # getattr 防御：测试 fake / 老客户端未实现该接口时跳过。
        set_disconnected = getattr(self._client, "set_disconnected_callback", None)
        if set_disconnected is not None:
            set_disconnected(self._on_disconnected)
        await self._client.connect()
        # 连上后的就绪步骤任一失败都属"半开链路"：先断开(吞异常)再上抛，
        # 避免残留 BLE 链路占用设备导致后续重连持续失败。
        try:
            chars = await self._client.get_characteristics()
            _ble_log(f"connect {self._address}; 特征值清单: " +
                     "; ".join(f"{u}={p}" for u, p in chars))
            self._notify_uuid, self._write_uuid, self._write_response = _find_transparent_chars(chars)
            self._mtu = max(int(getattr(self._client, "mtu_size", 23)) - 3, 20)
            _ble_log(f"选中 notify={self._notify_uuid} write={self._write_uuid} "
                     f"mtu_size={getattr(self._client, 'mtu_size', 23)} 分片={self._mtu} "
                     f"带响应写={self._write_response}")
            # 订阅前清空重连残留(对应 SerialTransport 重新武装)。订阅后不再重建
            # _rx_queue——否则「订阅生效→队列替换」窗口内到达的 notify 字节会落入旧队列
            # 被整体丢弃(T2-B4 丢字节窗口)。复用同一队列实例，read_byte 中阻塞在
            # 旧引用的消费者也不会因替换而饿死。清空与 _on_notify 入队经同一锁串行化。
            with self._lock:
                while True:
                    try:
                        self._rx_queue.get_nowait()
                    except queue.Empty:
                        break
            await self._client.start_notify(self._notify_uuid, self._on_notify)
            self._connected = True
        except Exception as e:
            _ble_log(f"连接就绪失败: {e!r}")
            try:
                await self._client.disconnect()
            except Exception:
                pass
            raise

    def _on_disconnected(self, *args) -> None:
        """bleak disconnected 回调（在事件循环线程执行）：设备侧断开（关机/超距）时
        置 _connected=False，is_open 如实反映链路状态。幂等：正常 close 后回调再触发
        也只是再次置 False，无副作用。置位经锁串行化，与 Task 7 数据通路锁一致。"""
        _ble_log(f"设备断开回调触发 address={self._address}")
        with self._lock:
            self._connected = False
        cb = self._disconnected_cb
        if cb is not None:
            try:
                cb()   # 通知上层（UI 切回未连接），回调内自行保证线程安全
            except Exception:
                _ble_log("BLE 断开回调异常(已忽略)")

    def _on_notify(self, sender, data) -> None:
        b = bytes(data)
        with self._lock:
            handler = self._data_handler
            rx_queue = self._rx_queue
            if _BLE_DEBUG_ENABLED:
                _ble_log(f"notify recv {len(b)}B mode={'handler' if handler else 'queue'} "
                         f"hex={_hex_preview(b)}")
            if handler is not None:
                try:
                    handler(b)
                except Exception as exc:
                    # 回调异常不得中断后续 notify 处理（T2-B9）：记录后继续。
                    _ble_log(f"notify handler 异常(已忽略): {exc!r}")
            else:
                for byte in b:
                    rx_queue.put(byte)

    @property
    def is_open(self) -> bool:
        return self._connected

    def set_data_handler(self, handler: "Callable[[bytes], None] | None") -> None:
        with self._lock:
            self._data_handler = handler
            if handler is not None:
                while True:
                    try:
                        self._rx_queue.get_nowait()
                    except queue.Empty:
                        break

    def start_rx(self) -> None:
        # notify 在 _connect 时已订阅；此处仅为与 SerialTransport 对等的幂等钩子。
        pass

    def stop_rx(self) -> None:
        # 交付随 close() 的 stop_notify/disconnect 结束；对等钩子，无独立 RX 线程。
        pass

    def read_byte(self, timeout: float) -> int | None:
        with self._lock:
            handler = self._data_handler
            rx_queue = self._rx_queue
        if handler is not None:
            return None
        try:
            return rx_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def write(self, data: bytes) -> int:
        if not self._connected:
            raise RuntimeError("ble not connected")
        data = bytes(data)
        if _BLE_DEBUG_ENABLED:
            _ble_log(f"write {len(data)}B -> {self._write_uuid} hex={_hex_preview(data)}")
        try:
            self._run(self._write(data))
        except Exception as e:
            _ble_log(f"write 失败: {e!r}")
            # 写失败通常意味着链路已断（设备关机/超距），同步置位让 is_open 反映真实状态。
            with self._lock:
                self._connected = False
            raise
        return len(data)

    async def _write(self, data: bytes) -> None:
        # 链路层按协商 MTU 分片（与协议层 chunk_size 正交）。
        # 带响应写(response=True)逐片等设备 BLE 层确认，形成背压，避免多分片背靠背
        # 连发时设备侧透传缓冲溢出丢字节；仅在写特征值支持 'write' 时启用。
        for i in range(0, len(data), self._mtu):
            await self._client.write_gatt_char(
                self._write_uuid, data[i:i + self._mtu], response=self._write_response)
            if not self._write_response:
                await asyncio.sleep(0.05)  # 无背压时 50ms 片间延迟，防设备缓冲溢出

    def wait_for_reopen(self, port: str, baud: int, retries: int, delay: float,
                        post_delay: float = 0.0, disappear_timeout: float = 5.0) -> bool:
        """BLE 版复位重连：断开当前连接 -> 按地址重连；地址失败则用 scanner 按名字兜底。
        成功后清空 RX 队列(对应 SerialTransport 的重新武装)。"""
        self._ensure_loop()
        try:
            if self._connected:
                self._run(self._disconnect(), timeout=_DISCONNECT_TIMEOUT)
        except Exception:
            pass
        self._connected = False

        for attempt in range(retries):
            if attempt:
                time.sleep(delay)
            # 地址优先
            if self._try_connect(port):
                if post_delay > 0:
                    time.sleep(post_delay)
                return True
            # 名字兜底
            if self._scanner is not None and self._reconnect_name:
                try:
                    for dev in self._scanner(disappear_timeout):
                        if getattr(dev, "name", None) == self._reconnect_name:
                            if self._try_connect(dev.address):
                                if post_delay > 0:
                                    time.sleep(post_delay)
                                return True
                except Exception:
                    pass
        return False

    def _try_connect(self, address: str) -> bool:
        try:
            self._address = address
            self._run(self._connect())
            # 不再重建 _rx_queue：队列生命周期与实例一致，订阅生效后的 notify 字节
            # 永不因队列替换而丢失(见 _connect 订阅前清空注释，T2-B4)。
            return True
        except Exception:
            self._connected = False
            return False

    def close(self) -> None:
        """释放 BLE 资源并停止事件循环线程。幂等：loop/线程已清理时直接返回。

        设计说明（T2-B2）：
        - 断开等待上限 _DISCONNECT_TIMEOUT 秒（原 10s），设备无响应时主线程冻结
          从最多约 12s 降到约 3s 内；Task 18 已让"设备已断"场景（_connected=False）
          走守卫快速返回，不进入断开等待。
        - 若 GUI 侧需要彻底不冻结，可在界面线程把 close() 派发到后台线程
          （QThreadPool / threading.Thread / asyncio.to_thread）；本类保持同步
          close 语义不变（释放资源、停线程、清状态），调用方式由上层选择。
        """
        if self._loop is None and self._loop_thread is None:
            return   # 幂等：从未初始化或已清理，直接返回
        if self._client is not None and self._connected:
            try:
                self._run(self._disconnect(), timeout=_DISCONNECT_TIMEOUT)
            except Exception:
                pass
        self._connected = False
        self._stop_loop()

    async def _disconnect(self) -> None:
        try:
            if self._notify_uuid:
                await self._client.stop_notify(self._notify_uuid)
        except Exception:
            pass
        await self._client.disconnect()

    def _stop_loop(self) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._loop_thread is not None:
            # join 兜底 1s：loop 正常停止时立即返回；极端情况（loop 被同步阻塞）下
            # 也不会让 close() 无限等待，剩余由 daemon 线程自然消亡。
            self._loop_thread.join(timeout=1)
        self._loop = None
        self._loop_thread = None
