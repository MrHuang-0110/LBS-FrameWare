"""连接方式统一入口：串口 / 蓝牙二选一 + 连接/断开。

- 模式切换用绿色小圆点标记选中项（QRadioButton 样式收敛于 theme.app_qss()，走查 E1）。
- 「连接」按钮建立并保持链路（BLE 连接会阻塞，故在后台线程跑），
  再点变「断开」。绿色状态点表示已连接。
- 已连接时 make_transport() 返回这条活链路，下发流程复用它（不重开/不关闭）。
"""
from __future__ import annotations
from typing import Callable
from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QRadioButton, QLabel,
                               QButtonGroup, QStackedWidget, QComboBox, QPushButton)
import qtawesome as qta
from .port_selector import PortSelector
from .. import theme
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


class _ConnectWorker(QObject):
    """把阻塞的建连(open+start_rx，BLE 可达数秒)丢到后台线程，成功/失败回主线程。"""
    done = Signal()
    failed = Signal(str)

    def __init__(self, transport, port: str, baud: int, parent=None):
        super().__init__(parent)
        self._transport = transport
        self._port = port
        self._baud = baud

    @Slot()
    def run(self) -> None:
        try:
            self._transport.open(self._port, self._baud)
            self._transport.start_rx()
            self.done.emit()
        except Exception as e:
            # open() 成功但 start_rx() 失败时，transport 已打开但无引用可关闭 → 泄漏。
            # 此处主动关闭，避免残留串口句柄/BLE 链路（下次连接同一端口会 access denied）。
            try:
                self._transport.close()
            except Exception:
                pass
            self.failed.emit(str(e))


class ConnectionSelector(QWidget):
    connection_changed = Signal(bool)   # True=已连接 False=已断开
    target_changed = Signal()           # 选中的串口/蓝牙设备变化（用于更新下发按钮使能态）

    def __init__(self, port_lister: "Callable | None" = None,
                 ble_scan: "Callable | None" = None,
                 serial_factory=SerialTransport, ble_factory=BleTransport, parent=None):
        super().__init__(parent)
        self._ble_scan = ble_scan or (lambda timeout=5.0: ble_scan_default(timeout))
        self._serial_factory = serial_factory
        self._ble_factory = ble_factory
        self._baud_getter: "Callable[[], int]" = lambda: 0
        self._scan_thread = None       # 后台扫描线程引用，防 GC
        self._scan_worker = None
        self._conn_thread = None       # 后台建连线程引用，防 GC
        self._conn_worker = None
        self._transport = None         # 已连接的活链路（None=未连接）

        self._rb_serial = QRadioButton("串口")
        self._rb_ble = QRadioButton("蓝牙")
        self._rb_serial.setChecked(True)
        self._group = QButtonGroup(self)
        self._group.addButton(self._rb_serial, 0)
        self._group.addButton(self._rb_ble, 1)
        # 单选按钮组：左侧一小块横排，绿色小圆点标记选中项（样式在 theme.app_qss()）
        radios = QHBoxLayout(); radios.setContentsMargins(0, 0, 0, 0); radios.setSpacing(10)
        radios.addWidget(self._rb_serial); radios.addWidget(self._rb_ble)

        self._port = PortSelector(lister=port_lister)
        ble_page = QWidget(); ble_lay = QHBoxLayout(ble_page)
        ble_lay.setContentsMargins(0, 0, 0, 0); ble_lay.setSpacing(6)
        self._ble_combo = QComboBox(); self._ble_combo.setMinimumWidth(240)
        self._ble_scan_btn = QPushButton("扫描")
        self._ble_scan_btn.clicked.connect(self.scan_ble)
        ble_lay.addWidget(self._ble_combo, 1); ble_lay.addWidget(self._ble_scan_btn)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._port)      # index 0 = serial
        self._stack.addWidget(ble_page)        # index 1 = ble

        # 连接/断开按钮 + 绿色状态点（矢量图标，A3）
        self._connect_btn = QPushButton("连接")
        self._connect_btn.clicked.connect(self.toggle_connection)
        self._dot = QLabel()
        self._dot.setToolTip("未连接")
        self._update_dot(False)

        # 根布局单行横排：[○串口 ○蓝牙] [下拉+扫描/刷新] [连接] [●]
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(10)
        lay.addLayout(radios); lay.addWidget(self._stack, 1)
        lay.addWidget(self._connect_btn); lay.addWidget(self._dot)

        self._group.idToggled.connect(self._on_kind_toggled)
        # 串口/蓝牙下拉选择变化时通知外部（用于更新下发按钮使能态）
        self._port._combo.currentIndexChanged.connect(lambda _: self.target_changed.emit())
        self._ble_combo.currentIndexChanged.connect(lambda _: self.target_changed.emit())

        # 顶栏 48px 适配（设计 §4.1/§4.3）：交互控件统一 30px 高，在 48px 顶栏内垂直居中
        for w in (self._rb_serial, self._rb_ble, self._port, self._ble_combo,
                  self._ble_scan_btn, self._connect_btn):
            w.setFixedHeight(30)

    # ---- 外部注入 ----
    def set_baud_getter(self, getter: "Callable[[], int]") -> None:
        """串口建连需要波特率；由 MainWindow 注入 profile.baud。"""
        self._baud_getter = getter

    # ---- 模式切换 ----
    def _on_kind_toggled(self, kind_id: int, checked: bool) -> None:
        if checked:
            self._stack.setCurrentIndex(kind_id)
            # 切换连接方式时若已连接，先断开旧链路，避免目标与链路不一致
            if self.is_connected():
                self.disconnect()
            self.target_changed.emit()

    def set_kind(self, kind: str) -> None:
        (self._rb_ble if kind == "ble" else self._rb_serial).setChecked(True)
        self._stack.setCurrentIndex(1 if kind == "ble" else 0)

    def selected_kind(self) -> str:
        return "ble" if self._rb_ble.isChecked() else "serial"

    # ---- 扫描 ----
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
        """把设备列表填进下拉；只显示设备名（未命名回退到地址短码），data=(address,name)。"""
        self._ble_combo.clear()
        for d in devices:
            label = d.name or f"(未命名 {d.address[-5:]})"
            self._ble_combo.addItem(label, (d.address, d.name))

    # ---- 目标 ----
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

    # ---- 连接 / 断开 ----
    def is_connected(self) -> bool:
        return self._transport is not None

    def persistent_transport(self):
        """已连接时返回活链路供下发复用；未连接返回 None。"""
        return self._transport

    def toggle_connection(self) -> None:
        if self.is_connected():
            self.disconnect()
        else:
            self.connect()

    def connect(self) -> None:
        """建立并保持链路。建连阻塞（BLE 可数秒），放后台线程；期间禁用按钮。"""
        if self.is_connected() or (self._conn_thread is not None and self._conn_thread.isRunning()):
            return
        target = self.selected_target()
        if not target:
            return
        transport = self.make_transport()
        self._connect_btn.setEnabled(False)
        self._connect_btn.setText("连接中...")
        self._set_inputs_enabled(False)
        self._conn_thread = QThread()
        self._conn_worker = _ConnectWorker(transport, target, int(self._baud_getter() or 0))
        self._conn_worker.moveToThread(self._conn_thread)
        self._conn_thread.started.connect(self._conn_worker.run)
        # 用局部 transport 传回，避免竞态：done 时才落成 self._transport
        self._conn_worker.done.connect(lambda t=transport: self._on_connect_done(t))
        self._conn_worker.failed.connect(self._on_connect_failed)
        self._conn_worker.done.connect(self._conn_thread.quit)
        self._conn_worker.failed.connect(self._conn_thread.quit)
        self._conn_thread.start()

    @Slot()
    def _on_connect_done(self, transport) -> None:
        self._transport = transport
        self._connect_btn.setText("断开")
        self._connect_btn.setEnabled(True)
        self._set_inputs_enabled(True)  # 连接成功后恢复模式切换和目标选择
        self._update_dot(True)
        self.connection_changed.emit(True)

    @Slot(str)
    def _on_connect_failed(self, msg: str) -> None:
        # 失败的 transport 已在 _ConnectWorker.run() 的 except 中关闭；
        # 此处仅清理 UI 状态，不重复关闭。
        self._transport = None
        self._connect_btn.setText("连接")
        self._connect_btn.setEnabled(True)
        self._set_inputs_enabled(True)
        self._update_dot(False, error=True, msg=msg)

    def disconnect(self) -> None:
        if self._transport is not None:
            try:
                self._transport.close()
            except Exception:
                pass
            self._transport = None
        self._connect_btn.setText("连接")
        self._connect_btn.setEnabled(True)
        self._set_inputs_enabled(True)
        self._update_dot(False)
        self.connection_changed.emit(False)
        # 清理上一次连接的后台线程引用（避免对象累积）
        self._conn_thread = None
        self._conn_worker = None

    def _set_inputs_enabled(self, enabled: bool) -> None:
        """连接期间锁定模式切换与目标选择，避免链路与选择错位。"""
        self._rb_serial.setEnabled(enabled)
        self._rb_ble.setEnabled(enabled)
        self._stack.setEnabled(enabled)

    def _update_dot(self, connected: bool, error: bool = False, msg: str = "") -> None:
        """连接状态点：矢量图标（A3），颜色走令牌，尺寸 ICON_MD。"""
        if connected:
            color, name, tip = theme.SUCCESS, "fa5s.circle", "已连接"
        elif error:
            color, name = theme.ERROR, "fa5s.exclamation-triangle"
            tip = f"连接失败: {msg}" if msg else "连接失败"
        else:
            color, name, tip = theme.ICON_DISABLED, "fa5s.circle-notch", "未连接"
        self._dot.setPixmap(qta.icon(name, color=color).pixmap(theme.ICON_MD, theme.ICON_MD))
        self._dot.setToolTip(tip)

    def make_transport(self):
        # 已连接时复用活链路，避免二次 open 抢占同一端口/BLE 链路
        if self._transport is not None:
            return self._transport
        if self.selected_kind() == "serial":
            return self._serial_factory()
        return self._ble_factory(scanner=lambda timeout: self._ble_scan(timeout),
                                 reconnect_name=self.selected_name())
