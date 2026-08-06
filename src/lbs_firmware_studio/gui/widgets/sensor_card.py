"""通用键值传感器卡片：标题=端口+中文类型名，下方逐行 键: 值。
MVP 方案（对所有传感器/产品统一适用，字段增改无需改代码）。
空态显示「无设备」灰字提示，有数据时显示最后刷新时间（设计走查 B6）。"""
from __future__ import annotations
import time
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QWidget
from PySide6.QtGui import QColor
from .. import theme
from ..pages.monitor_profiles import sensor_display_name


class SensorCard(QFrame):
    def __init__(self, port: int, parent=None):
        super().__init__(parent)
        self._port = port
        self._rows: list[tuple[str, str]] = []
        self._accent = theme.SENSOR_COLORS[port % 8]   # 本端口 accent 色（P1–P8 色板）
        self.setObjectName("card")
        self.setMinimumHeight(120)

        # 标题「端口 N · 类型名」：端口号部分 mono + accent 色，类型名 TEXT_PRIMARY
        self._port_title = QLabel()
        self._port_title.setStyleSheet(
            f"font-weight:{theme.WEIGHT_BOLD}; font-family:{theme.MONO_FONT};"
            f" color:{self._accent}; background:transparent;")
        self._name_title = QLabel()
        self._name_title.setStyleSheet(
            f"font-weight:{theme.WEIGHT_BOLD}; color:{theme.TEXT_PRIMARY}; background:transparent;")
        # 空态提示（B6）：标题右侧灰字「无设备」，有数据时隐藏
        self._empty = QLabel("无设备")
        self._empty.setStyleSheet(
            f"color:{theme.TEXT_SECONDARY}; font-size:{theme.FONT_CAPTION}px; background:transparent;")
        title_row = QHBoxLayout()
        title_row.setSpacing(theme.SPACE_SM)
        title_row.addWidget(self._port_title)
        title_row.addWidget(self._name_title)
        title_row.addWidget(self._empty)
        title_row.addStretch(1)

        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(theme.SPACE_MD)
        self._grid.setVerticalSpacing(theme.SPACE_XS)

        # 最后刷新时间戳（B6）：卡片底部小字，有数据时显示
        self._updated = QLabel("")
        self._updated.setStyleSheet(
            f"color:{theme.TEXT_SECONDARY}; font-size:{theme.FONT_CAPTION}px; background:transparent;")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(theme.SPACE_MD, theme.SPACE_SM, theme.SPACE_MD, theme.SPACE_SM)
        lay.setSpacing(theme.SPACE_XS)
        lay.addLayout(title_row)
        lay.addWidget(self._grid_host)
        lay.addWidget(self._updated)
        lay.addStretch(1)

        self.update(None, {})

    def update(self, sensor_key: "str | None", fields: dict) -> None:
        has_data = sensor_key is not None
        self._port_title.setText(f"端口 {self._port}")
        self._name_title.setText(sensor_display_name(sensor_key) if has_data else "")
        if has_data:
            self._empty.setText("")
            self._empty.setVisible(False)
            self._updated.setText(f"更新 {time.strftime('%H:%M:%S')}")
        else:
            self._empty.setText("无设备")
            self._empty.setVisible(True)
            self._updated.setText("")
        self._apply_card_style(has_data)
        self._rows = [(str(k), str(v)) for k, v in fields.items()]
        self._rebuild_grid()

    def _apply_card_style(self, has_data: bool) -> None:
        """卡片边框：有数据用本端口 accent 色半透明（hex8），空态用 BORDER。"""
        if has_data:
            border = QColor(self._accent)
            border.setAlpha(90)
            border_hex = border.name()   # alpha<255 时 name() 返回 #AARRGGBB
        else:
            border_hex = theme.BORDER
        self.setStyleSheet(
            f"QFrame#card {{ border: 1px solid {border_hex};"
            f" border-radius: {theme.RADIUS_LG}px; }}")

    def _rebuild_grid(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        for i, (k, v) in enumerate(self._rows):
            klab = QLabel(k + ":")
            klab.setStyleSheet(f"color:{theme.TEXT_SECONDARY}; background:transparent;")
            vlab = QLabel(v)
            # 数值：mono 等宽 + TEXT_PRIMARY（参考设计 §4 等宽数字）
            vlab.setStyleSheet(
                f"color:{theme.TEXT_PRIMARY}; font-family:{theme.MONO_FONT}; background:transparent;")
            self._grid.addWidget(klab, i, 0)
            self._grid.addWidget(vlab, i, 1)

    # --- 测试访问器 ---
    def title_text(self) -> str:
        """标题文本：端口部分 + (· 类型名)。空态仅「端口 N」。"""
        name = self._name_title.text()
        return f"{self._port_title.text()} · {name}" if name else self._port_title.text()

    def rows(self) -> list[tuple[str, str]]:
        return list(self._rows)

    def empty_hint(self) -> str:
        """空态提示文本：无设备 ->「无设备」；有数据 -> ""。"""
        return self._empty.text()
