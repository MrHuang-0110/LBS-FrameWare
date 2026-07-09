"""DeployWorker：把 DeviceDeployer 放到 QThread 里跑，避免阻塞 UI。

用法（MainWindow 里）：
    thread = QThread()
    worker = DeployWorker(transport, deployer)
    worker.moveToThread(thread)
    thread.started.connect(lambda: worker.run_firmware(profile, port))
    worker.finished.connect(thread.quit)
    thread.start()
本 worker 复用 deployer 的 progress/log/state_changed/error 信号（已是 Qt Signal）。
"""
from __future__ import annotations
from PySide6.QtCore import QObject, Signal


class DeployWorker(QObject):
    finished = Signal()

    def __init__(self, transport, deployer, parent=None):
        super().__init__(parent)
        self._transport = transport
        self._deployer = deployer

    def run_firmware(self, profile, port: str) -> None:
        try:
            self._transport.open(port, profile.baud)
            self._transport.start_rx()
            self._deployer.update_firmware(profile, port)
        except Exception as e:
            # open()/start_rx() 失败在 update_firmware 之前，deployer 尚未上报；此处补发，
            # 使 MainWindow 的 _on_error 弹窗 + _on_state("error") 能触发。
            # 若 update_firmware 自身抛出，它已先发过 error；再发一次无害。
            try:
                self._deployer.error.emit(f"打开串口失败: {e}")
                self._deployer.state_changed.emit("error")
            except Exception:
                pass
        finally:
            try:
                self._transport.close()
            except Exception:
                pass
            self.finished.emit()
