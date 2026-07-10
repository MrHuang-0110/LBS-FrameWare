"""数据监控页：顶部串口+启停(+传感器更新)，中部左/右两列 SensorCard，底部 HostStatusBar。
设备流式 JSON 经 MonitorWorker.frame_parsed 进来 -> 只缓存最新帧 -> QTimer(100ms) 节流渲染。"""
from __future__ import annotations
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QLabel, QPushButton, QMessageBox)
from PySide6.QtCore import QTimer
import qtawesome as qta
from .. import theme
from ..widgets.port_selector import PortSelector
from ..widgets.sensor_card import SensorCard
from ..widgets.host_status_bar import HostStatusBar
from ..monitor_worker import MonitorWorker
from .monitor_profiles import MONITOR_PROFILES

_RENDER_INTERVAL_MS = 100


class MonitorPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._profile = None
        self._cards: dict[int, SensorCard] = {}
        self._latest: dict | None = None
        self._port_getter = lambda: None
        self._monitoring = False

        self._worker = MonitorWorker()
        self._worker.frame_parsed.connect(self._on_frame)
        self._worker.error.connect(self._on_error)
        self._worker.state_changed.connect(self._on_worker_state)

        # 顶栏
        self._port = PortSelector()
        self._start_btn = QPushButton("▶ 开始监控"); self._start_btn.setObjectName("primary")
        self._start_btn.clicked.connect(self._toggle_monitor)
        self._update_btn = QPushButton("传感器更新")
        self._update_btn.setIcon(qta.icon("fa5s.sync", color=theme.TEXT_PRIMARY))
        self._update_btn.clicked.connect(self._open_sensor_update)
        self._update_btn.setEnabled(False)     # 需监控中才能下发
        top = QHBoxLayout()
        top.addWidget(QLabel("串口:")); top.addWidget(self._port, 1)
        top.addWidget(self._start_btn); top.addWidget(self._update_btn)

        # 卡片区（两列）
        self._grid = QGridLayout()
        self._grid.setHorizontalSpacing(12); self._grid.setVerticalSpacing(12)
        self._grid_host = QWidget(); self._grid_host.setLayout(self._grid)

        # 底部状态栏
        self._status = HostStatusBar()

        # 未知产品提示
        self._notice = QLabel(""); self._notice.setStyleSheet(
            f"color:{theme.TEXT_SECONDARY}; background:transparent;")

        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self._notice)
        lay.addWidget(self._grid_host, 1)
        lay.addWidget(self._status)

        # 节流渲染定时器
        self._timer = QTimer(self)
        self._timer.setInterval(_RENDER_INTERVAL_MS)
        self._timer.timeout.connect(self._render)

    # --- profile ---
    def set_profile(self, profile) -> None:
        self._profile = profile
        self._rebuild_cards()

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
            self._update_btn.setVisible(False)
            self._status.set_fields([])
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
        self._status.set_fields(prof["status_fields"])
        self._update_btn.setVisible(prof["sensor_update"])

    def set_port_getter(self, fn) -> None:
        self._port_getter = fn

    # --- 启停 ---
    def _toggle_monitor(self) -> None:
        if self._monitoring:
            self.stop_monitor()
        else:
            self.start_monitor()

    def start_monitor(self) -> None:
        port = self._port.selected_port()
        if not port:
            QMessageBox.warning(self, "提示", "未选择串口"); return
        baud = getattr(self._profile, "baud", 115200)
        self._worker.start(port, baud)

    def stop_monitor(self) -> None:
        self._timer.stop()
        self._worker.stop()

    def _on_worker_state(self, state: str) -> None:
        self._monitoring = (state == "connected")
        self._start_btn.setText("■ 停止监控" if self._monitoring else "▶ 开始监控")
        # 传感器更新仅在 NEW-AI 且监控中可用
        prof = MONITOR_PROFILES.get(self._profile.name) if self._profile else None
        can_update = self._monitoring and bool(prof and prof["sensor_update"])
        self._update_btn.setEnabled(can_update)
        if self._monitoring:
            self._timer.start()
        else:
            self._timer.stop()

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
        self._status.update_from(frame)

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

    # --- 传感器更新 ---
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

    def has_sensor_update_button(self) -> bool:
        return not self._update_btn.isHidden()

    def latest_frame(self) -> "dict | None":
        return self._latest
