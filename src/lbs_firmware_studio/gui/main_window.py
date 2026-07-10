"""主窗口：左 Activity Bar + 顶栏 + 右内容区 + 底部 StatusBar（VS Code 风格）。
固件更新走 DeployWorker(QThread)，信号回主线程。业务接线沿用已修复版本。"""
from __future__ import annotations
from pathlib import Path
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QStackedWidget, QMessageBox)
from PySide6.QtCore import Signal, QThread
from . import theme
from .widgets.activity_bar import ActivityBar
from .widgets.status_bar import StatusBar
from .widgets.port_selector import PortSelector
from .pages.firmware_page import FirmwarePage
from .pages.script_editor_page import ScriptEditorPage
from .pages.settings_page import SettingsPage
from .pages.placeholder_page import PlaceholderPage
from .pages.monitor_page import MonitorPage
from .worker import DeployWorker
from ..backend.serial_transport import SerialTransport
from ..backend.deployer import DeviceDeployer

# (key, 中文标签, icon, enabled)
_NAV = [
    ("firmware", "固件更新", "fa5s.download", True),
    ("editor", "代码编辑", "fa5s.code", True),
    ("monitor", "数据监控", "fa5s.chart-line", True),
    ("settings", "设置", "fa5s.cog", True),
]
_KEY2LABEL = {k: lbl for k, lbl, _, _ in _NAV}
_LABEL2KEY = {lbl: k for k, lbl, _, _ in _NAV}
_BUSY_STATES = {"compiling", "connecting", "entering_upgrade", "reconnecting", "transfering"}


class MainWindow(QWidget):
    switch_product_requested = Signal()

    def __init__(self, profile, raw_config: dict, config_path: Path, parent=None):
        super().__init__(parent)
        self._profile = profile
        self._raw = raw_config
        self._path = Path(config_path)
        self._busy = False
        self._thread = None
        self._worker = None
        self.setWindowTitle(f"LBS Firmware Studio - {profile.name}")
        self.resize(1200, 800)
        self.setMinimumSize(900, 600)

        # 顶栏
        self._product_lbl = QLabel(f"◆ {profile.name}")
        self._product_lbl.setStyleSheet(f"font-size:14px; font-weight:600; color:{theme.TEXT_PRIMARY}; background:transparent;")
        self._port = PortSelector()
        self._switch_btn = QPushButton("切换产品")
        self._switch_btn.clicked.connect(self.switch_product_requested.emit)
        top = QWidget(); top.setFixedHeight(36); top.setStyleSheet(f"background: {theme.BG_BAR};")
        toplay = QHBoxLayout(top); toplay.setContentsMargins(12, 0, 12, 0)
        toplay.addWidget(self._product_lbl); toplay.addStretch(1)
        toplay.addWidget(self._port); toplay.addWidget(self._switch_btn)

        # Activity Bar + 页面栈
        self._activity = ActivityBar([(k, icon, en) for k, _, icon, en in _NAV])
        self._activity.current_changed.connect(self._on_nav)
        self._stack = QStackedWidget()
        self._pages: dict[str, QWidget] = {}
        for key, label, _icon, _en in _NAV:
            page = self._make_page(key)
            self._pages[key] = page
            self._stack.addWidget(page)

        # 底部状态栏
        self._status = StatusBar()
        self._status.set_product(profile.name)
        self._status.set_state("idle")

        # 组装
        mid = QWidget()
        midlay = QHBoxLayout(mid); midlay.setContentsMargins(0, 0, 0, 0); midlay.setSpacing(0)
        midlay.addWidget(self._activity)
        midlay.addWidget(self._stack, 1)

        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)
        outer.addWidget(top); outer.addWidget(mid, 1); outer.addWidget(self._status)

        # 固件页接线
        self._firmware.set_profile(profile)
        self._firmware.start_requested.connect(self._start_firmware)
        # 脚本编辑/下发页接线
        self._editor_page.set_profile(profile)
        self._editor_page.set_port_getter(self._port.selected_port)
        self._editor_page.deploy_requested.connect(self._start_script)
        self._activity.set_current("firmware")

    def _make_page(self, key):
        if key == "firmware":
            self._firmware = FirmwarePage(); return self._firmware
        if key == "editor":
            self._editor_page = ScriptEditorPage(); return self._editor_page
        if key == "monitor":
            self._monitor = MonitorPage()
            self._monitor.set_profile(self._profile)
            return self._monitor
        if key == "settings":
            return SettingsPage(self._raw, self._path)
        return PlaceholderPage(_KEY2LABEL[key])

    def _on_nav(self, key: str):
        # 离开监控页时停监控，释放串口
        if key != "monitor" and self._pages.get("monitor") is self._stack.currentWidget():
            self._monitor.stop_monitor()
        self._stack.setCurrentWidget(self._pages[key])

    # ---- 固件更新流程（沿用已修复版本）----
    def _start_firmware(self):
        self._run_deploy(self._firmware, "run_firmware")

    def _start_script(self, py_path: Path, slot: int):
        self._run_deploy(self._editor_page, "run_script", py_path=py_path, slot=slot)

    def _run_deploy(self, page, run_slot_name: str, **job_kwargs):
        """统一的下发接线：守卫→建 transport/deployer→接线→moveToThread→start。
        page 为当前忙碌页(进度/日志回调目标)，run_slot_name 为 worker 上的直连无参运行槽。"""
        if self._busy or (self._thread is not None and self._thread.isRunning()):
            return
        port = self._port.selected_port()
        if not port:
            QMessageBox.warning(self, "提示", "未选择串口"); return
        self._busy = True
        page.set_busy(True)
        self._transport = SerialTransport()
        self._deployer = DeviceDeployer(self._transport)
        self._deployer.progress.connect(page.on_progress)
        self._deployer.state_changed.connect(self._on_state)
        self._deployer.log.connect(page.on_log)
        self._deployer.error.connect(self._on_error)
        self._thread = QThread()
        self._worker = DeployWorker(self._transport, self._deployer)
        self._worker.set_job(self._profile, port, **job_kwargs)
        self._worker.moveToThread(self._thread)
        # 直连 worker 的运行槽(带子线程 affinity)，勿用 lambda——否则工作会跑在主线程卡死 GUI
        self._thread.started.connect(getattr(self._worker, run_slot_name))
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._on_finished)
        self._status.set_connection(port, self._profile.baud)
        self._thread.start()

    def _on_state(self, state: str):
        self._firmware.on_state(state)
        self._editor_page.on_state(state)
        self._status.set_state(state)
        self._busy = state in _BUSY_STATES
        self._firmware.set_busy(self._busy)
        self._editor_page.set_busy(self._busy)
        self._port.setEnabled(not self._busy)
        self._switch_btn.setEnabled(not self._busy)
        self._activity.set_locked(self._busy)

    def _on_error(self, msg: str):
        QMessageBox.critical(self, "错误", msg)

    def _on_finished(self):
        self._busy = False
        self._firmware.set_busy(False)
        self._editor_page.set_busy(False)
        self._port.setEnabled(True)
        self._switch_btn.setEnabled(True)
        self._activity.set_locked(False)
        self._status.set_connection(None, None)

    # ---- 测试访问器（签名不变）----
    def header_text(self): return self._product_lbl.text()
    def nav_labels(self): return [lbl for _, lbl, _, _ in _NAV]
    def is_nav_enabled(self, label): return self._activity.is_enabled(_LABEL2KEY[label])
    def navigate(self, label): self._activity.set_current(_LABEL2KEY[label])
    def current_page_name(self):
        for key, page in self._pages.items():
            if page is self._stack.currentWidget():
                return _KEY2LABEL[key]
        return ""
    def click_switch_product(self): self._switch_btn.click()
    def is_busy(self): return self._busy
    def status_bar_text(self): return self._status.state_text()
