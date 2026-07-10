"""通用键值传感器卡片：标题=端口+中文类型名，下方逐行 键: 值。
MVP 方案（对所有传感器/产品统一适用，字段增改无需改代码）。"""
from __future__ import annotations
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QGridLayout, QWidget
from .. import theme
from ..pages.monitor_profiles import sensor_display_name


class SensorCard(QFrame):
    def __init__(self, port: int, parent=None):
        super().__init__(parent)
        self._port = port
        self._rows: list[tuple[str, str]] = []
        self.setObjectName("card")
        self.setMinimumHeight(120)

        self._title = QLabel()
        self._title.setStyleSheet(
            f"font-weight:600; color:{theme.TEXT_PRIMARY}; background:transparent;")
        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(12)
        self._grid.setVerticalSpacing(2)

        lay = QVBoxLayout(self)
        lay.addWidget(self._title)
        lay.addWidget(self._grid_host)
        lay.addStretch(1)

        self.update(None, {})

    def update(self, sensor_key: "str | None", fields: dict) -> None:
        if sensor_key:
            self._title.setText(f"端口 {self._port} · {sensor_display_name(sensor_key)}")
        else:
            self._title.setText(f"端口 {self._port}")
        self._rows = [(str(k), str(v)) for k, v in fields.items()]
        self._rebuild_grid()

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
            vlab.setStyleSheet(f"color:{theme.TEXT_PRIMARY}; background:transparent;")
            self._grid.addWidget(klab, i, 0)
            self._grid.addWidget(vlab, i, 1)

    # --- 测试访问器 ---
    def title_text(self) -> str:
        return self._title.text()

    def rows(self) -> list[tuple[str, str]]:
        return list(self._rows)
