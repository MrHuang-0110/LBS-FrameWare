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
        self._owns_lifecycle = True   # True=本 worker 自己 open/close；False=复用外部持久链路

    def start(self, port: str, baud: int) -> None:
        """自建串口链路：本 worker 负责 open/close。"""
        try:
            self._parser = MonitorParser()
            self._owns_lifecycle = True
            self._transport.open(port, baud)
            self._arm()
        except Exception as e:
            self.error.emit(f"打开串口失败: {e}")
            self.state_changed.emit("disconnected")

    def start_on(self, transport) -> None:
        """复用外部已连接的持久链路（串口/蓝牙）：不 open/不 close，仅挂 data_handler
        接管字节流；stop 时摘掉 handler 把链路归还给顶栏，不断开。"""
        try:
            self._parser = MonitorParser()
            self._transport = transport
            self._owns_lifecycle = False
            self._arm()
        except Exception as e:
            self.error.emit(f"接入连接失败: {e}")
            self.state_changed.emit("disconnected")

    def _arm(self) -> None:
        """共用：挂 data_handler + 启动 RX，发出 connected 信号。"""
        self._transport.set_data_handler(self._on_data)
        self._transport.start_rx()                     # 幂等：串口重新武装RX；蓝牙为空操作
        self.state_changed.emit("connected")

    def send_frame(self, frame: bytes) -> None:
        try:
            self._transport.write(frame)
        except Exception as e:
            self.error.emit(f"下发失败: {e}")

    def stop(self) -> None:
        try:
            if self._owns_lifecycle:
                self._transport.close()
            else:
                # 归还持久链路：摘掉 handler 让其回到队列模式，不关闭链路
                self._transport.set_data_handler(None)
        except Exception:
            pass
        self.state_changed.emit("disconnected")

    def _on_data(self, data: bytes) -> None:
        for frame in self._parser.feed(data):
            self.frame_parsed.emit(frame)
