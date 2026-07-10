"""监控 worker：普通 QObject。用 SerialTransport 的 RX 后台线程 + set_data_handler
接原始字节，喂 MonitorParser，每帧经 frame_parsed 信号送主线程。

_on_data 在 transport 的 RX 线程被调用；MonitorWorker 存活于主线程，故 emit 会被
Qt 自动以 QueuedConnection 投递到主线程，UI 更新安全。绝不在此碰 widget。
"""
from __future__ import annotations
from PySide6.QtCore import QObject, Signal
from ..backend.serial_transport import SerialTransport
from ..backend.monitor_parser import MonitorParser


class MonitorWorker(QObject):
    frame_parsed = Signal(object)   # payload: dict
    error = Signal(str)
    state_changed = Signal(str)     # "connected" | "disconnected"

    def __init__(self, transport: "SerialTransport | None" = None, parent=None):
        super().__init__(parent)
        self._transport = transport if transport is not None else SerialTransport()
        self._parser = MonitorParser()

    def start(self, port: str, baud: int) -> None:
        try:
            self._parser = MonitorParser()          # 每次连接重置缓冲
            self._transport.open(port, baud)
            self._transport.set_data_handler(self._on_data)
            self._transport.start_rx()
            self.state_changed.emit("connected")
        except Exception as e:
            self.error.emit(f"打开串口失败: {e}")
            self.state_changed.emit("disconnected")

    def send_frame(self, frame: bytes) -> None:
        try:
            self._transport.write(frame)
        except Exception as e:
            self.error.emit(f"下发失败: {e}")

    def stop(self) -> None:
        try:
            self._transport.close()
        except Exception:
            pass
        self.state_changed.emit("disconnected")

    def _on_data(self, data: bytes) -> None:
        for frame in self._parser.feed(data):
            self.frame_parsed.emit(frame)
