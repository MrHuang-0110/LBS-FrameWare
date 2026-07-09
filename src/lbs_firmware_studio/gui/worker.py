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
        except Exception:
            pass  # 错误已由 deployer.error 信号上报；此处不再抛以保证 finished 必发
        finally:
            try:
                self._transport.close()
            except Exception:
                pass
            self.finished.emit()
