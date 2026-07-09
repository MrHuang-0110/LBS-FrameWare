"""日志区：只读文本，时间戳 + 级别着色。"""
from __future__ import annotations
import time
from PySide6.QtWidgets import QPlainTextEdit
from .. import theme

_LEVEL_COLOR = {
    "info": theme.TEXT_PRIMARY, "success": theme.SUCCESS,
    "progress": theme.ACCENT, "error": theme.ERROR,
}


class LogView(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)

    def append(self, message: str, level: str = "info") -> None:
        ts = time.strftime("%H:%M:%S")
        color = _LEVEL_COLOR.get(level, theme.TEXT_PRIMARY)
        self.appendHtml(f'<span style="color:{theme.TEXT_SECONDARY}">{ts}</span> '
                        f'<span style="color:{color}">{message}</span>')

    def plain_text(self) -> str:
        return self.toPlainText()
