"""DeployWorker：把 DeviceDeployer 放到 QThread 里跑，避免阻塞 UI。

用法（MainWindow 里）：
    thread = QThread()
    worker = DeployWorker(transport, deployer)
    worker.set_job(profile, port)          # 先存参数
    worker.moveToThread(thread)
    thread.started.connect(worker.run_firmware)   # 直连 worker 的槽(带线程affinity)，勿用 lambda
    worker.finished.connect(thread.quit)
    thread.start()
本 worker 复用 deployer 的 progress/log/state_changed/error 信号（已是 Qt Signal）。

重要：started 必须直连 worker 自己的槽方法 run_firmware（无参），不能用
`lambda: worker.run_firmware(profile, port)`——lambda 无线程 affinity，会在主线程
执行，导致阻塞式串口 I/O 卡死 GUI（已用线程测试验证）。故参数改为 set_job 预存。
"""
from __future__ import annotations
from PySide6.QtCore import QObject, Signal, Slot


class DeployWorker(QObject):
    finished = Signal()

    def __init__(self, transport, deployer, parent=None, owns_lifecycle: bool = True):
        super().__init__(parent)
        self._transport = transport
        self._deployer = deployer
        self._profile = None
        self._port = None
        self._py_path = None
        self._slot = 0
        # owns_lifecycle=False：transport 是外部已连接的持久链路，本 worker 不 open/close，
        # 仅武装 RX 与执行下发（复用活链路，避免二次 open 抢占同一端口/BLE 链路）。
        self._owns_lifecycle = owns_lifecycle

    def set_job(self, profile, port: str, py_path=None, slot: int = 0) -> None:
        """预存本次任务参数。固件更新只需 profile/port；脚本下发另带 py_path/slot。"""
        self._profile = profile
        self._port = port
        self._py_path = py_path
        self._slot = slot

    @Slot()
    def run_firmware(self) -> None:
        profile, port = self._profile, self._port
        opened = False
        try:
            if self._owns_lifecycle:
                self._transport.open(port, profile.baud)
            self._transport.start_rx()
            opened = True
            self._deployer.update_firmware(profile, port)
        except Exception as e:
            # open/start_rx 阶段失败时 deployer 尚未上报，需补发；
            # update_firmware 自身失败已 emit 过 error，不再重复补发（避免 GUI 弹两次错误框）。
            if not opened:
                try:
                    self._deployer.error.emit(f"打开串口失败: {e}")
                    self._deployer.state_changed.emit("error")
                except Exception:
                    pass
        finally:
            try:
                if self._owns_lifecycle:
                    self._transport.close()
            except Exception:
                pass
            self.finished.emit()

    @Slot()
    def run_script(self) -> None:
        profile, port = self._profile, self._port
        opened = False
        try:
            if self._owns_lifecycle:
                self._transport.open(port, profile.baud)
            self._transport.start_rx()
            opened = True
            self._deployer.deploy_script(profile, port, self._py_path, self._slot)
        except Exception as e:
            # open/start_rx 阶段失败时 deployer 尚未上报，需补发；
            # deploy_script 自身失败已 emit 过 error，不再重复补发。
            if not opened:
                try:
                    self._deployer.error.emit(f"打开串口失败: {e}")
                    self._deployer.state_changed.emit("error")
                except Exception:
                    pass
        finally:
            try:
                if self._owns_lifecycle:
                    self._transport.close()
            except Exception:
                pass
            self.finished.emit()
