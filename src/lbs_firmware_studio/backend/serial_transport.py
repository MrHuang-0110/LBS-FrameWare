"""串口层：封装 pyserial，后台 RX 线程把字节路由给队列或数据回调。"""
from __future__ import annotations
import threading, queue, time
from typing import Callable

try:
    import serial
    import serial.tools.list_ports
except ImportError:  # 测试环境用 FakeSerial，pyserial 可能未装
    serial = None


class SerialTransport:
    def __init__(self, serial_obj=None):
        self._serial = serial_obj
        self._rx_queue: queue.Queue[int] = queue.Queue()
        self._data_handler: Callable[[bytes], None] | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def is_open(self) -> bool:
        return self._serial is not None and getattr(self._serial, "is_open", True)

    def open(self, port: str, baud: int) -> None:
        if self._serial is None:
            self._serial = serial.Serial(port=port, baudrate=baud, timeout=0.1)
        else:
            self._serial.timeout = 0.1

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
        while not self._stop.is_set():
            try:
                chunk = self._serial.read(64)
            except Exception:
                time.sleep(0.05)
                continue
            if not chunk:
                continue
            if self._data_handler is not None:
                self._data_handler(bytes(chunk))
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

    def wait_for_reopen(self, port: str, baud: int, retries: int, delay: float) -> bool:
        self.close()
        for attempt in range(retries):
            time.sleep(delay if attempt else min(delay, 0.5))
            try:
                if serial is not None:
                    self._serial = serial.Serial(port=port, baudrate=baud, timeout=0.1)
                else:
                    self._serial.is_open = True
                self._rx_queue = queue.Queue()
                return True
            except Exception:
                continue
        return False
