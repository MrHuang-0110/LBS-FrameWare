"""主窗口：顶栏(产品+状态+串口+切换) + 左导航 + 右 QStackedWidget。
固件更新走 DeployWorker 在 QThread 里跑，信号回主线程更新页面。"""
from __future__ import annotations
from pathlib import Path
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QListWidget, QListWidgetItem, QStackedWidget,
                               QMessageBox)
from PySide6.QtCore import Signal, Qt, QThread
from . import theme
from .widgets.status_badge import StatusBadge
from .widgets.port_selector import PortSelector
from .pages.firmware_page import FirmwarePage
from .pages.settings_page import SettingsPage
from .pages.placeholder_page import PlaceholderPage
from .worker import DeployWorker
from ..backend.serial_transport import SerialTransport
from ..backend.deployer import DeviceDeployer

# 导航项: (标签, 是否可用)
_NAV = [("固件更新", True), ("脚本下发", False), ("代码编辑", False),
        ("数据监控", False), ("设置", True)]
_BUSY_STATES = {"compiling", "connecting", "entering_upgrade", "reconnecting", "transfering"}


class MainWindow(QWidget):
    switch_product_requested = Signal()

    def __init__(self, profile, raw_config: dict, config_path: Path, parent=None):
        super().__init__(parent)
        self._profile = profile
        # raw/path 必须在 _make_page 之前赋值（构建 设置 页时会用到）
        self._raw = raw_config
        self._path = Path(config_path)
        self._busy = False
        self._thread = None
        self._worker = None
        self.setWindowTitle(f"LBS Firmware Studio - {profile.name}")

        # 顶栏
        self._product_lbl = QLabel(profile.name)
        self._product_lbl.setStyleSheet("font-size:16px; font-weight:600;")
        self._badge = StatusBadge()
        self._port = PortSelector()
        self._switch_btn = QPushButton("切换产品")
        self._switch_btn.clicked.connect(self.switch_product_requested.emit)
        top = QHBoxLayout()
        top.addWidget(self._product_lbl); top.addWidget(self._badge)
        top.addStretch(); top.addWidget(self._port); top.addWidget(self._switch_btn)

        # 左导航 + 右内容
        self._nav = QListWidget(); self._nav.setFixedWidth(160)
        self._stack = QStackedWidget()
        self._pages = {}
        for label, enabled in _NAV:
            item = QListWidgetItem(label if enabled else f"{label} 🔒")
            if not enabled:
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            self._nav.addItem(item)
            page = self._make_page(label)
            self._pages[label] = page
            self._stack.addWidget(page)
        self._nav.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._nav.setCurrentRow(0)

        body = QHBoxLayout()
        body.addWidget(self._nav); body.addWidget(self._stack, 1)

        outer = QVBoxLayout(self)
        outer.addLayout(top); outer.addLayout(body, 1)

        # 固件页信号
        self._firmware.set_profile(profile)
        self._firmware.start_requested.connect(self._start_firmware)

    def _make_page(self, label):
        if label == "固件更新":
            self._firmware = FirmwarePage(); return self._firmware
        if label == "设置":
            return SettingsPage(self._raw, self._path)
        return PlaceholderPage(label)

    # ---- 固件更新流程 ----
    def _start_firmware(self):
        port = self._port.selected_port()
        if not port:
            QMessageBox.warning(self, "提示", "未选择串口"); return
        self._transport = SerialTransport()
        self._deployer = DeviceDeployer(self._transport)
        self._deployer.progress.connect(self._firmware.on_progress)
        self._deployer.state_changed.connect(self._on_state)
        self._deployer.log.connect(self._firmware.on_log)
        self._deployer.error.connect(self._on_error)
        self._thread = QThread()
        self._worker = DeployWorker(self._transport, self._deployer)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(lambda: self._worker.run_firmware(self._profile, port))
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._on_finished)
        self._thread.start()

    def _on_state(self, state: str):
        self._badge.set_state(state)
        self._firmware.on_state(state)
        self._busy = state in _BUSY_STATES
        self._firmware.set_busy(self._busy)
        self._port.setEnabled(not self._busy)
        self._switch_btn.setEnabled(not self._busy)

    def _on_error(self, msg: str):
        QMessageBox.critical(self, "错误", msg)

    def _on_finished(self):
        self._busy = False
        self._firmware.set_busy(False)
        self._port.setEnabled(True)
        self._switch_btn.setEnabled(True)

    # ---- 测试辅助 ----
    def header_text(self): return self._product_lbl.text()
    def nav_labels(self): return [self._nav.item(i).text().replace(" 🔒", "")
                                  for i in range(self._nav.count())]
    def is_nav_enabled(self, label):
        for i in range(self._nav.count()):
            if self._nav.item(i).text().replace(" 🔒", "") == label:
                return bool(self._nav.item(i).flags() & Qt.ItemIsEnabled)
        return False
    def navigate(self, label):
        for i in range(self._nav.count()):
            if self._nav.item(i).text().replace(" 🔒", "") == label:
                self._nav.setCurrentRow(i); return
    def current_page_name(self):
        idx = self._stack.currentIndex()
        return list(self._pages.keys())[idx]
    def click_switch_product(self): self._switch_btn.click()
    def is_busy(self): return self._busy
