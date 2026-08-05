"""主窗口：左 Activity Bar + 顶栏（主机信息）+ 右内容区 + 底部 StatusBar（VS Code 风格）。
布局重构 v2（设计 §4.1/§4.2）：顶栏只放主机信息（HostStatusBar，横向紧凑）；
产品选择/连接收进设备浮窗（ConnectionPopup，device 图标弹出，Task 2 组件）；
传感器更新走 sensor 图标弹 SensorUpdateDialog；固件更新仍走 DeployWorker(QThread)。
产品切换：设备浮窗内 ProductSelector 触发，MainWindow 窗内重建页面栈（设计 §4.2）。"""
from __future__ import annotations
from pathlib import Path
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame,
                               QStackedWidget, QMessageBox, QSplitter)
from PySide6.QtCore import QThread, Qt
from . import theme
from .widgets.activity_bar import ActivityBar
from .widgets.status_bar import StatusBar
from .widgets.host_status_bar import HostStatusBar
from .widgets.connection_popup import ConnectionPopup
from .pages.firmware_page import FirmwarePage
from .pages.script_editor_page import ScriptEditorPage
from .pages.settings_page import SettingsPage
from .pages.monitor_page import MonitorPage
from .pages.monitor_profiles import MONITOR_PROFILES
from .worker import DeployWorker
from ..backend.deployer import DeviceDeployer
from ..backend import protocol_frame as pf

# (key, 中文标签, icon, enabled)——device/sensor 为浮窗触发键（不切页），其余为页面键
_NAV = [
    ("device", "设备连接", "fa5s.microchip", True),
    ("device-page", "固件与监控", "fa5s.tachometer-alt", True),
    ("editor", "代码编辑", "fa5s.code", True),
    ("sensor", "传感器更新", "fa5s.thermometer-half", True),
    ("settings", "设置", "fa5s.cog", True),
]
_KEY2LABEL = {k: lbl for k, lbl, _, _ in _NAV}
_LABEL2KEY = {lbl: k for k, lbl, _, _ in _NAV}
_POPUP_KEYS = {"device", "sensor"}   # ActivityBar 浮窗触发键：点击只发 action_triggered
_BUSY_STATES = {"compiling", "connecting", "entering_upgrade", "reconnecting", "transfering"}


class MainWindow(QWidget):
    # switch_product_requested 已删除：产品切换由设备浮窗内 ProductSelector.product_changed
    # 驱动，MainWindow 在窗内重建页面栈处理（设计 §6.2）。

    def __init__(self, profile, raw_config: dict, config_path: Path,
                 profiles: dict | None = None, parent=None):
        """构造签名保持 MainWindow(profile, raw, path)（Task 3 兼容）；
        新增可选 profiles：全部产品字典（供设备浮窗切换）。
        未传时退化为单产品字典。"""
        super().__init__(parent)
        self._profiles = profiles if profiles else {profile.name: profile}
        self._profile = profile
        self._raw = raw_config
        self._path = Path(config_path)
        self._busy = False
        self._thread = None
        self._worker = None
        self.setWindowTitle(f"LBS Firmware Studio - {profile.name}")
        self.resize(1200, 800)
        self.setMinimumSize(900, 600)

        # 顶栏（48px，BG_BAR）：只放主机信息（HostStatusBar，横向紧凑）
        self._host_bar = HostStatusBar()
        top = QWidget(); top.setFixedHeight(48); top.setStyleSheet(f"background: {theme.BG_BAR};")
        toplay = QHBoxLayout(top); toplay.setContentsMargins(theme.SPACE_MD, 0, theme.SPACE_MD, 0)
        toplay.setSpacing(theme.SPACE_SM)
        toplay.addWidget(self._host_bar)

        # 设备连接浮窗（Task 2 ConnectionPopup，Qt.Popup 顶层窗口，MainWindow 持有）
        self._popup = ConnectionPopup(self._profiles, self._profile.name, parent=self)
        self._popup.product_changed.connect(self._on_product_change)
        conn = self._popup.connection()
        # _conn/_product_selector 兼容引用：既有测试与内部使用点（下发门禁/运行按钮等）沿用
        self._conn = conn
        self._product_selector = self._popup._product

        # Activity Bar + 页面栈
        self._activity = ActivityBar([(k, icon, en) for k, _, icon, en in _NAV],
                                     popup_keys=set(_POPUP_KEYS))
        # tooltip 统一用 _NAV 中文标签（ActivityBar._LABELS 未含浮窗键，此处覆盖）
        for key, label, _icon, _en in _NAV:
            self._activity._buttons[key].setToolTip(label)
        self._activity.current_changed.connect(self._on_nav)
        self._activity.action_triggered.connect(self._on_action)
        self._stack = QStackedWidget()
        self._pages: dict[str, QWidget] = {}
        for key, _label, _icon, _en in _NAV:
            if key in _POPUP_KEYS:
                continue
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

        # 页面接线（重建时整体重连）；浮窗内 ConnectionSelector 的常驻信号仅连接一次
        self._wire_pages()
        conn.connection_changed.connect(self._on_connection_changed)
        conn.target_changed.connect(self._update_deploy_buttons)
        self._activity.set_current("device-page")
        self._update_deploy_buttons()  # 初始状态：PortSelector 异步扫描完成前按钮禁用

    def _make_page(self, key):
        if key == "device-page":
            # 固件更新 + 数据监控 左右分栏合并
            self._firmware = FirmwarePage()
            self._monitor = MonitorPage()
            self._monitor.set_profile(self._profile)
            # 监控复用设备浮窗持久链路（串口/蓝牙）；未连接时回退本页串口选择
            self._monitor.set_transport_getter(self._conn.persistent_transport)
            splitter = QSplitter(Qt.Horizontal)
            splitter.addWidget(self._firmware)
            splitter.addWidget(self._monitor)
            splitter.setStretchFactor(0, 2)   # 左固件
            splitter.setStretchFactor(1, 3)   # 右监控（占更多）
            splitter.setChildrenCollapsible(False)
            return splitter
        if key == "editor":
            self._editor_page = ScriptEditorPage(); return self._editor_page
        if key == "settings":
            return SettingsPage(self._raw, self._path)
        # _NAV 页面键已在上方覆盖；浮窗键不进入 _make_page
        raise KeyError(f"unknown page key: {key}")

    def _rebuild_pages(self) -> None:
        """整体重建页面栈（Firmware/Monitor/Editor/Settings 新实例）。
        _firmware/_monitor/_editor_page 属性名保留，测试兼容（设计 §6.2）。
        QStackedWidget 没有 clear()（那是 QLayout 的），需逐 widget 移除并
        deleteLater 释放旧页实例。"""
        while self._stack.count():
            w = self._stack.widget(0)
            self._stack.removeWidget(w)
            w.deleteLater()
        self._pages = {}
        for key, _label, _icon, _en in _NAV:
            if key in _POPUP_KEYS:
                continue
            page = self._make_page(key)
            self._pages[key] = page
            self._stack.addWidget(page)
        self._wire_pages()

    def _wire_pages(self) -> None:
        """页面级信号接线（Firmware/Editor/Monitor 相互联动；重建后重连）。
        同时把监控页主机信息（最新帧）转发到顶栏 HostStatusBar。"""
        self._firmware.set_profile(self._profile)
        self._firmware.start_requested.connect(self._start_firmware)
        self._editor_page.set_profile(self._profile)
        self._editor_page.set_port_getter(self._conn.selected_target)
        self._conn.set_baud_getter(lambda: getattr(self._profile, "baud", 0))
        self._editor_page.deploy_requested.connect(self._start_script)
        # 监控运行状态 → 编辑页按钮状态
        self._monitor.host_state_changed.connect(self._editor_page.on_host_state_changed)
        # 监控帧 → 顶栏主机信息（HostStatusBar 数据源）
        self._monitor.frame_rendered.connect(self._on_host_frame)
        prof = MONITOR_PROFILES.get(self._profile.name)
        self._host_bar.set_fields(prof["status_fields"] if prof else [])
        # 编辑页运行/暂停按钮 → 发 0xB6 命令
        self._editor_page.run_toggle_requested.connect(self._on_run_toggle)

    def _on_host_frame(self, frame) -> None:
        """监控页节流渲染后的最新帧 → 顶栏 HostStatusBar 更新主机信息。"""
        self._host_bar.update_from(frame)

    def _on_product_change(self, name: str) -> None:
        """产品切换（窗内重建页面栈，设计 §4.2）。
        守卫 → 停监控 → 重建 → 重接线 → 状态栏重置 → 连接处理（决策点 §6.4）。"""
        # Task 2 Minor ②：弹层开着时程序化 select 不刷新高亮——先确保弹层关闭再切
        if self._product_selector.is_popup_open():
            self._product_selector._close_popup()
        if self._busy:
            # busy 守卫：回滚选择到原产品（同名 select 不 emit，无递归）
            self._product_selector.select_product(self._profile.name)
            return
        if name == self._profile.name:
            return
        old_baud = getattr(self._profile, "baud", 0)
        new_profile = self._profiles[name]
        baud_same = getattr(new_profile, "baud", 0) == old_baud
        was_connected = self._conn.is_connected()

        self._monitor.stop_monitor()          # 停旧监控
        self._profile = new_profile
        self._rebuild_pages()                 # 重建页面栈（新实例，属性名保留）
        self._status.set_product(name)        # 状态栏产品名 + 阶段重置为「就绪」
        self._status.set_state("idle")
        self._activity.set_current("device-page")  # 回到默认设备页
        self._update_deploy_buttons()
        # 连接状态处理（决策点 2：baud 一致保持链路并自动重启监控；否则断开提示）
        if was_connected:
            if baud_same:
                self._monitor.start_monitor()
            else:
                self._conn.disconnect()
                QMessageBox.warning(self, "提示", "产品波特率变化，请重新连接")

    def _on_nav(self, key: str):
        # 浮窗键不进页面栈（ActivityBar 浮窗类只发 action_triggered；此处兜底防误导航）
        if key not in self._pages:
            return
        # 页面切换时收起设备浮窗（reviewer M6：popup 生命周期随导航关闭）
        if self._popup.isVisible():
            self._popup.hide()
        # 离开设备页且目标不是编辑页时停监控（编辑页依赖监控数据驱动运行/暂停按钮）
        monitor = getattr(self, "_monitor", None)
        if monitor is not None and key != "device-page" and key != "editor" and monitor.is_monitoring():
            monitor.stop_monitor()
        self._stack.setCurrentWidget(self._pages[key])

    def _on_action(self, key: str) -> None:
        """ActivityBar 浮窗触发键：device → 设备连接浮窗；sensor → 传感器更新对话框。"""
        if key == "device":
            self._show_device_popup()
        elif key == "sensor":
            self._on_sensor_action()

    def _show_device_popup(self) -> None:
        """在 ActivityBar device 图标右侧弹出 ConnectionPopup（Qt.Popup 外部点击自动关闭）。
        busy 时浮窗可弹（Task 1 决策）：内部产品/连接由 set_locked 禁用。"""
        btn = self._activity._buttons["device"]
        pos = btn.mapToGlobal(btn.rect().topRight())
        pos.setX(pos.x() + theme.SPACE_XS)   # 图标右侧小间距
        self._popup.move(pos)
        self._popup.show()
        self._popup.raise_()

    def _on_sensor_action(self) -> None:
        """sensor 图标：弹传感器更新对话框（复用监控页既有对话框与数据源）。"""
        monitor = getattr(self, "_monitor", None)
        if monitor is None:
            return
        if self._popup.isVisible():
            self._popup.hide()
        monitor._open_sensor_update()

    def _on_connection_changed(self, connected: bool) -> None:
        """设备浮窗连接状态变化：连上即自动开始监控，断开即停止。"""
        monitor = getattr(self, "_monitor", None)
        if monitor is None:
            return
        monitor.set_transport_getter(self._conn.persistent_transport)
        if connected:
            monitor.start_monitor()   # 连接成功即自动监控，无需手动按钮
        else:
            monitor.stop_monitor()
        self._update_deploy_buttons()

    def _on_run_toggle(self):
        """发送运行/暂停切换命令 (0xB6) 到设备。"""
        transport = self._conn.persistent_transport()
        if transport is None:
            return
        if self._busy:
            return
        try:
            transport.write(pf.build_frame(pf.CMD_RUN_TOGGLE, b"\x01"))
        except OSError:
            pass  # 传输层写失败，等下一帧监控数据修正按钮状态

    def _update_deploy_buttons(self) -> None:
        """按「是否选中连接目标」和「是否蓝牙固件门禁」更新下发按钮使能态。
        未选串口/蓝牙设备时固件更新和脚本下发按钮均禁用，避免点了弹警告。"""
        has_target = self._conn.selected_target() is not None
        can_firmware = has_target and not self._ble_firmware_blocked()
        self._firmware._start.setEnabled(can_firmware and not self._busy)
        self._editor_page._deploy_btn.setEnabled(has_target and not self._busy)
        # 运行/暂停按钮：委托 _apply_run_state() 统一管理，避免多源覆盖
        self._editor_page.set_has_target(has_target and not self._busy)

    # ---- 固件更新流程（沿用已修复版本）----
    def _ble_firmware_blocked(self) -> bool:
        """蓝牙通道 + 该产品不支持蓝牙固件更新(custom_frame) -> 阻止。"""
        return (self._conn.selected_kind() == "ble"
                and not getattr(self._profile, "ble_firmware", False))

    def _start_firmware(self):
        if self._ble_firmware_blocked():
            QMessageBox.warning(self, "提示", "当前产品的蓝牙通道不支持固件更新，请改用串口")
            return
        self._run_deploy(self._firmware, "run_firmware")

    def _start_script(self, py_path: Path, slot: int):
        self._run_deploy(self._editor_page, "run_script", py_path=py_path, slot=slot)

    def _run_deploy(self, page, run_slot_name: str, **job_kwargs):
        """统一的下发接线：守卫→建 transport/deployer→接线→moveToThread→start。
        page 为当前忙碌页(进度/日志回调目标)，run_slot_name 为 worker 上的直连无参运行槽。"""
        if self._busy or (self._thread is not None and self._thread.isRunning()):
            return
        port = self._conn.selected_target()
        if not port:
            QMessageBox.warning(self, "提示", "未选择连接目标"); return
        # 复用持久链路时先停监控，避免 data_handler 抢占串口字节导致下发协议超时
        persistent = self._conn.persistent_transport()
        if persistent is not None and self._monitor.is_monitoring():
            self._monitor.stop_monitor()
        self._busy = True
        page.set_busy(True)
        # 已手动建连则复用活链路（worker 不再 open/close）；否则沿用一次性建连
        if persistent is not None:
            self._transport = persistent
            owns_lifecycle = False
        else:
            self._transport = self._conn.make_transport()
            owns_lifecycle = True
        self._deployer = DeviceDeployer(self._transport)
        self._deployer.progress.connect(page.on_progress)
        self._deployer.state_changed.connect(self._on_state)
        self._deployer.log.connect(page.on_log)
        self._deployer.error.connect(self._on_error)
        self._thread = QThread()
        self._worker = DeployWorker(self._transport, self._deployer, owns_lifecycle=owns_lifecycle)
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
        if not self._busy:
            self._update_deploy_buttons()  # 从忙碌恢复时按目标可用性更新按钮
        # busy：禁用浮窗内产品切换与连接按钮（浮窗本身可弹，Task 1 决策）
        self._popup.set_locked(self._busy)
        self._activity.set_locked(self._busy)

    def _on_error(self, msg: str):
        QMessageBox.critical(self, "错误", msg)

    def _on_finished(self):
        self._busy = False
        self._firmware.set_busy(False)
        self._editor_page.set_busy(False)
        self._update_deploy_buttons()  # 恢复按钮使能态（未选目标时仍禁用）
        self._popup.set_locked(False)
        self._activity.set_locked(False)
        self._status.set_connection(None, None)
        # 下发前停了监控释放串口；下发结束后若链路仍在则自动恢复监控
        monitor = getattr(self, "_monitor", None)
        if monitor is not None and self._conn.persistent_transport() is not None:
            monitor.start_monitor()

    # ---- 测试访问器（签名不变）----
    def header_text(self): return self._popup.current_product()
    def nav_labels(self): return [lbl for _, lbl, _, _ in _NAV]
    def is_nav_enabled(self, label): return self._activity.is_enabled(_LABEL2KEY[label])
    def navigate(self, label):
        key = _LABEL2KEY[label]
        if key in self._pages:
            self._activity.set_current(key)
    def current_page_name(self):
        for key, page in self._pages.items():
            if page is self._stack.currentWidget():
                return _KEY2LABEL[key]
        return ""
    def click_switch_product(self): self._product_selector.trigger_button().click()
    def is_busy(self): return self._busy
    def status_bar_text(self): return self._status.state_text()
    def host_bar(self): return self._host_bar
    def popup_visible(self): return self._popup.isVisible()
