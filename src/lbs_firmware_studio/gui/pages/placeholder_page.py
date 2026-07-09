"""占位页：脚本下发/代码编辑/数据监控共用，显示 <title> · 即将推出。"""
from __future__ import annotations
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from .. import theme


class PlaceholderPage(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._text = f"{title} · 即将推出"
        lay = QVBoxLayout(self)
        lbl = QLabel(self._text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"color: {theme.MUTED}; font-size: 18px;")
        lay.addStretch(); lay.addWidget(lbl); lay.addStretch()

    def displayed_text(self) -> str:
        return self._text
