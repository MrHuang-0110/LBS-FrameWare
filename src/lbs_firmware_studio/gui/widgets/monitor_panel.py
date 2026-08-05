"""右侧监控栏 MonitorPanel：连接提示条 + 传感器卡片网格（布局重构 v3 从 monitor_page 提取）。

- 常驻主内容区右侧（固定宽 280px，MainWindow 布局），不再作为独立页面。
- 连接入口在设备浮窗（ActivityBar device 图标），本组件无端口选择；
  数据流与 monitor_page 一致：设备流式 JSON 经 MonitorWorker.frame_parsed 进来 ->
  只缓存最新帧 -> QTimer(100ms) 节流渲染，卡片网格按产品 MONITOR_PROFILES 重建。
- host_state_changed / frame_rendered 信号分别驱动编辑页运行/暂停按钮与顶栏 HostStatusBar
  （MainWindow 接线，与 monitor_page 行为完全一致）。
- 深色主题全部走 theme 令牌；图标统一 qta fa5s.*；GUI 层不碰协议/串口/BLE。
"""
from __future__ import annotations
from PySide6.QtWidgets import (QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QLabel, QPushButton, QMessageBox)
from PySide6.QtCore import QTimer, Signal
import qtawesome as qta
from .. import theme
from .sensor_card import SensorCard
from ..monitor_worker import MonitorWorker
from ..pages.monitor_profiles import MONITOR_PROFILES, get_host_state_path, get_by_path

_RENDER_INTERVAL_MS = 100


class MonitorPanel(QWidget):
    host_state_changed = Signal(str)
    frame_rendered = Signal(object)   # 每帧节流渲染后转发最新帧（顶栏主机信息数据源）

    def __init__(self, parent=None):
        super().__init__(parent)
        self._profile = None
        self._cards: dict[int, SensorCard] = {}
        self._latest: dict | None = None
        self._monitoring = False
        self._transport_getter = lambda: None   # 由 MainWindow 注入：取设备浮窗已连接的持久链路

        self._worker = MonitorWorker()
        self._worker.frame_parsed.connect(self._on_frame)
        self._worker.error.connect(self._on_error)
        self._worker.state_changed.connect(self._on_worker_state)

        # 监控自动启动（连接成功即监控），保留隐藏按钮对象供状态回调引用但不显示
        self._start_btn = QPushButton("开始监控"); self._start_btn.setObjectName("primary")
        self._start_btn.setIcon(qta.icon("fa5s.play", color=theme.TEXT_ON_ACCENT))
        self._start_btn.setVisible(False)
        # 连接提示条（设计 §4.5）：未连接 WARNING「请先在设备浮窗连接设备」/ 已连接 SUCCESS「已连接设备」
        self._conn_hint = QFrame()
        self._conn_hint.setObjectName("connHint")
        hint_lay = QHBoxLayout(self._conn_hint)
        hint_lay.setContentsMargins(theme.SPACE_MD, theme.SPACE_SM, theme.SPACE_MD, theme.SPACE_SM)
        hint_lay.setSpacing(theme.SPACE_SM)
        hint_icon = QLabel()
        hint_icon.setPixmap(qta.icon("fa5s.link", color=theme.TEXT_PRIMARY)
                            .pixmap(theme.ICON_SM, theme.ICON_SM))
        self._conn_hint_text = QLabel("")
        self._conn_hint_text.setStyleSheet(f"color:{theme.TEXT_PRIMARY}; background:transparent;")
        hint_lay.addWidget(hint_icon)
        hint_lay.addWidget(self._conn_hint_text)
        hint_lay.addStretch(1)
        self._refresh_connection_hint()

        # 卡片区（两列）
        self._grid = QGridLayout()
        self._grid.setHorizontalSpacing(12); self._grid.setVerticalSpacing(12)
        self._grid_host = QWidget(); self._grid_host.setLayout(self._grid)

        # 未知产品提示
        self._notice = QLabel(""); self._notice.setStyleSheet(
            f"color:{theme.TEXT_SECONDARY}; background:transparent;")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(theme.SPACE_MD, theme.SPACE_LG, theme.SPACE_MD, theme.SPACE_LG)
        lay.setSpacing(theme.SPACE_MD)
        lay.addWidget(self._conn_hint)
        lay.addWidget(self._notice)
        lay.addWidget(self._grid_host, 1)

        # 节流渲染定时器
        self._timer = QTimer(self)
        self._timer.setInterval(_RENDER_INTERVAL_MS)
        self._timer.timeout.connect(self._render)
        self._last_host_state = ""

    # --- profile ---
    def set_profile(self, profile) -> None:
        self._profile = profile
        self._rebuild_cards()

    def set_transport_getter(self, getter) -> None:
        """注入取设备浮窗持久链路的回调。返回非 None 时监控复用该链路（串口/蓝牙皆可）。"""
        self._transport_getter = getter
        self._refresh_connection_hint()

    def _refresh_connection_hint(self) -> None:
        """依据浮窗持久链路是否可用切换提示条：未连接 WARNING / 已连接 SUCCESS（设计 §4.5）。"""
        connected = self._transport_getter() is not None
        bg = theme.SUCCESS_BG if connected else theme.WARNING_BG
        self._conn_hint.setStyleSheet(
            f"QFrame#connHint {{ background: {bg}; border-radius: {theme.RADIUS_MD}px; }}")
        self._conn_hint_text.setText("已连接设备" if connected else "请先在设备浮窗连接设备")

    def _rebuild_cards(self) -> None:
        # 清空旧卡片
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._cards = {}

        prof = MONITOR_PROFILES.get(self._profile.name) if self._profile else None
        if prof is None:
            self._notice.setText(f"产品 {getattr(self._profile, 'name', '?')} 暂不支持数据监控")
            return

        self._notice.setText("")
        n = prof["ports"]
        half = (n + 1) // 2
        for port in range(n):
            card = SensorCard(port)
            self._cards[port] = card
            col = 0 if port < half else 1
            rowpos = port if port < half else port - half
            self._grid.addWidget(card, rowpos, col)

    # --- 启停 ---
    def start_monitor(self) -> None:
        # 仅复用设备浮窗已连接的持久链路（串口或蓝牙）；本组件无独立端口选择
        transport = self._transport_getter()
        if transport is None:
            QMessageBox.warning(self, "提示", "未连接设备，请先在设备浮窗连接"); return
        self._worker.start_on(transport)

    def stop_monitor(self) -> None:
        self._timer.stop()
        self._worker.stop()

    def is_monitoring(self) -> bool:
        return self._monitoring

    def _on_worker_state(self, state: str) -> None:
        self._monitoring = (state == "connected")
        if not self._monitoring:
            self._last_host_state = ""
            self.host_state_changed.emit("")
        if self._monitoring:
            self._start_btn.setText("停止监控")
            self._start_btn.setIcon(qta.icon("fa5s.stop", color=theme.TEXT_ON_ACCENT))
        else:
            self._start_btn.setText("开始监控")
            self._start_btn.setIcon(qta.icon("fa5s.play", color=theme.TEXT_ON_ACCENT))
        if self._monitoring:
            self._timer.start()
        else:
            self._timer.stop()
        # 提示条随连接状态刷新（监控中必然已连接；停止后重新按链路可用性判定）
        self._refresh_connection_hint()

    def _on_error(self, msg: str) -> None:
        QMessageBox.critical(self, "错误", msg)

    # --- 帧渲染（节流）---
    def _on_frame(self, frame: dict) -> None:
        self._latest = frame

    def _render(self) -> None:
        frame = self._latest
        if not frame:
            return
        by_port = {}
        for item in frame.get("deviceList", []):
            if isinstance(item, dict) and "port" in item:
                by_port[item["port"]] = item
        for port, card in self._cards.items():
            item = by_port.get(port)
            sensor_key, fields = self._extract_sensor(item)
            card.update(sensor_key, fields)
        # --- 提取运行状态 ---
        self._emit_host_state(frame)
        # --- 转发最新帧给顶栏主机信息（HostStatusBar 数据源） ---
        self.frame_rendered.emit(frame)

    @staticmethod
    def _extract_sensor(item: "dict | None"):
        """从 deviceList 项取 (传感器key, 字段dict)。无设备 -> (None, {})。"""
        if not item:
            return None, {}
        for k, v in item.items():
            if k == "port":
                continue
            return k, (v if isinstance(v, dict) else {})
        return None, {}

    def _emit_host_state(self, frame: dict) -> None:
        """从帧中提取运行状态，变化时 emit host_state_changed。"""
        name = getattr(self._profile, "name", None) if self._profile else None
        if name is None:
            return
        path = get_host_state_path(name)
        if path is None:
            return
        raw = get_by_path(frame, path)
        state = str(raw).strip().lower() if raw is not None else ""
        if state not in ("start", "stop"):
            state = ""  # 非预期值当未知处理
        if state != self._last_host_state:
            self._last_host_state = state
            self.host_state_changed.emit(state)

    # --- 传感器更新（入口在设备浮窗，MainWindow._on_sensor_action 复用本方法）---
    def _open_sensor_update(self) -> None:
        from ..dialogs.sensor_update_dialog import SensorUpdateDialog
        dlg = SensorUpdateDialog(self)
        dlg.frame_ready.connect(self._worker.send_frame)
        dlg.exec()

    # --- 测试访问器 ---
    def card_count(self) -> int:
        return len(self._cards)

    def card_at(self, port: int) -> SensorCard:
        return self._cards[port]

    def has_sensor_update_action(self) -> bool:
        """该产品是否支持传感器更新（入口在设备浮窗，本组件仅报告能力）。"""
        prof = MONITOR_PROFILES.get(self._profile.name) if self._profile else None
        return bool(prof and prof["sensor_update"])

    def has_connection_hint(self) -> bool:
        """连接提示条是否显示。"""
        return not self._conn_hint.isHidden()

    def connection_hint_text(self) -> str:
        """当前提示条文案（未连接/已连接两态）。"""
        return self._conn_hint_text.text()

    def latest_frame(self) -> "dict | None":
        return self._latest
