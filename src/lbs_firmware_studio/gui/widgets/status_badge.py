"""左上角状态灯：圆点 + 文字，颜色随 state 变化。"""
from __future__ import annotations
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt
from .. import theme

_STATE_TEXT = {
    "idle": "空闲", "compiling": "编译中", "connecting": "连接中",
    "entering_upgrade": "进入升级", "reconnecting": "重连中",
    "transfering": "传输中", "done": "完成", "error": "错误",
}


class StatusBadge(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = theme.MUTED
        self._dot = QLabel("●")
        self._label = QLabel(_STATE_TEXT["idle"])
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(6)
        lay.addWidget(self._dot); lay.addWidget(self._label)
        self._apply()

    def set_state(self, state: str) -> None:
        self._color = theme.state_color(state)
        self._label.setText(_STATE_TEXT.get(state, state))
        self._apply()

    def _apply(self) -> None:
        self._dot.setStyleSheet(f"color: {self._color}; font-size: 14px;")

    def current_color(self) -> str:
        return self._color

    def text(self) -> str:
        return self._label.text()
