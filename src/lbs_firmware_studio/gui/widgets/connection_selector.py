"""连接方式统一入口：串口 / 蓝牙二选一，make_transport() 按 kind 造对等 transport。"""
from __future__ import annotations
from typing import Callable
from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QRadioButton,
                               QButtonGroup, QStackedWidget, QComboBox, QPushButton)
from .port_selector import PortSelector
from ...backend.serial_transport import SerialTransport
from ...backend.ble_transport import BleTransport
from ...backend.ble_scanner import scan as ble_scan_default


class _ScanWorker(QObject):
    """把阻塞 ~5s 的 BLE 扫描丢到后台线程跑，扫完 emit devices 回主线程。仅做发现，不碰链路。"""
    done = Signal(object)   # payload: list[BleDevice]
    failed = Signal(str)

    def __init__(self, scan_fn: "Callable", parent=None):
        super().__init__(parent)
        self._scan_fn = scan_fn

    @Slot()
    def run(self) -> None:
        # 无参直连槽保证线程 affinity（同 worker.py 注释所述，勿用 lambda 直连）。
        try:
            self.done.emit(list(self._scan_fn()))
        except Exception as e:
            self.failed.emit(str(e))


class ConnectionSelector(QWidget):
    def __init__(self, port_lister: "Callable | None" = None,
                 ble_scan: "Callable | None" = None,
                 serial_factory=SerialTransport, ble_factory=BleTransport, parent=None):
        super().__init__(parent)
        self._ble_scan = ble_scan or (lambda timeout=5.0: ble_scan_default(timeout))
        self._serial_factory = serial_factory
        self._ble_factory = ble_factory
        self._scan_thread = None       # 后台扫描线程引用，防 GC
        self._scan_worker = None

        self._rb_serial = QRadioButton("串口")
        self._rb_ble = QRadioButton("蓝牙")
        self._rb_serial.setChecked(True)
        self._group = QButtonGroup(self)
        self._group.addButton(self._rb_serial, 0)
        self._group.addButton(self._rb_ble, 1)
        # 单选按钮组：左侧一小块横排
        radios = QHBoxLayout(); radios.setContentsMargins(0, 0, 0, 0); radios.setSpacing(4)
        radios.addWidget(self._rb_serial); radios.addWidget(self._rb_ble)

        self._port = PortSelector(lister=port_lister)
        ble_page = QWidget(); ble_lay = QHBoxLayout(ble_page); ble_lay.setContentsMargins(0, 0, 0, 0)
        self._ble_combo = QComboBox(); self._ble_combo.setMinimumWidth(180)
        self._ble_scan_btn = QPushButton("扫描")
        self._ble_scan_btn.clicked.connect(self.scan_ble)
        ble_lay.addWidget(self._ble_combo, 1); ble_lay.addWidget(self._ble_scan_btn)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._port)      # index 0 = serial
        self._stack.addWidget(ble_page)        # index 1 = ble

        # 根布局单行横排：[○串口 ○蓝牙] [下拉+扫描/刷新]，塞进 36px 顶栏
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(8)
        lay.addLayout(radios); lay.addWidget(self._stack, 1)

        self._group.idToggled.connect(self._on_kind_toggled)

    def _on_kind_toggled(self, kind_id: int, checked: bool) -> None:
        if checked:
            self._stack.setCurrentIndex(kind_id)

    def set_kind(self, kind: str) -> None:
        (self._rb_ble if kind == "ble" else self._rb_serial).setChecked(True)
        self._stack.setCurrentIndex(1 if kind == "ble" else 0)

    def selected_kind(self) -> str:
        return "ble" if self._rb_ble.isChecked() else "serial"

    def scan_ble(self) -> None:
        """点扫描：后台线程跑阻塞扫描(~5s)，UI 不冻结；扫完在主线程填充下拉。
        扫描期间禁用按钮 + 文本改「扫描中...」。重入直接忽略（线程仍在跑时）。"""
        if self._scan_thread is not None and self._scan_thread.isRunning():
            return
        self._ble_scan_btn.setEnabled(False)
        self._ble_scan_btn.setText("扫描中...")
        self._scan_thread = QThread()
        self._scan_worker = _ScanWorker(self._ble_scan)
        self._scan_worker.moveToThread(self._scan_thread)
        # 直连 worker 的无参运行槽(带子线程 affinity)，勿用 lambda——否则扫描跑在主线程卡死 GUI
        self._scan_thread.started.connect(self._scan_worker.run)
        self._scan_worker.done.connect(self._on_scan_done)
        self._scan_worker.failed.connect(self._on_scan_failed)
        self._scan_worker.done.connect(self._scan_thread.quit)
        self._scan_worker.failed.connect(self._scan_thread.quit)
        self._scan_thread.start()

    @Slot(object)
    def _on_scan_done(self, devices) -> None:
        self._populate_ble(devices)
        self._reset_scan_btn()

    @Slot(str)
    def _on_scan_failed(self, _msg: str) -> None:
        self._reset_scan_btn()

    def _reset_scan_btn(self) -> None:
        self._ble_scan_btn.setText("扫描")
        self._ble_scan_btn.setEnabled(True)

    def _populate_ble(self, devices) -> None:
        """把设备列表填进下拉；label 沿用现有格式，data=(address,name)。可被测试直接驱动。"""
        self._ble_combo.clear()
        for d in devices:
            label = f"{d.name or '(未命名)'} [{d.address}] {d.rssi}dBm"
            self._ble_combo.addItem(label, (d.address, d.name))

    def selected_target(self) -> "str | None":
        if self.selected_kind() == "serial":
            return self._port.selected_port()
        if self._ble_combo.count() == 0:
            return None
        return self._ble_combo.currentData()[0]

    def selected_name(self) -> "str | None":
        if self.selected_kind() == "serial" or self._ble_combo.count() == 0:
            return None
        return self._ble_combo.currentData()[1]

    def make_transport(self):
        if self.selected_kind() == "serial":
            return self._serial_factory()
        return self._ble_factory(scanner=lambda timeout: self._ble_scan(timeout),
                                 reconnect_name=self.selected_name())
