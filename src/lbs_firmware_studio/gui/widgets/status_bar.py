"""VS Code 风格底部状态栏：蓝色条，左连接状态，右产品名+运行状态。"""
from __future__ import annotations
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
import qtawesome as qta
from .. import theme

_STATE_TEXT = {
    "idle": "空闲", "compiling": "编译中", "connecting": "连接中",
    "entering_upgrade": "进入升级", "reconnecting": "重连中",
    "transfering": "传输中", "done": "完成", "error": "错误",
}


class StatusBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(24)
        self.setStyleSheet(f"background: {theme.STATUSBAR};")
        self._icon = QLabel()
        self._conn = QLabel("未连接")
        self._product_lbl = QLabel("")
        self._state = "idle"
        self._product = ""
        for lbl in (self._conn, self._product_lbl):
            lbl.setStyleSheet(f"color: {theme.TEXT_ON_ACCENT}; font-size: {theme.FONT_CAPTION}px; background: transparent;")
        self._icon.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(theme.SPACE_MD, 0, theme.SPACE_MD, 0)
        lay.setSpacing(theme.SPACE_XS + 2)
        lay.addWidget(self._icon)
        lay.addWidget(self._conn)
        lay.addStretch(1)
        lay.addWidget(self._product_lbl)
        self._update_conn_icon(False)
        self._refresh_product()

    def _update_conn_icon(self, connected: bool) -> None:
        color = theme.TEXT_ON_ACCENT if connected else theme.TEXT_DISABLED
        name = "fa5s.circle" if connected else "fa5s.circle-notch"
        self._icon.setPixmap(qta.icon(name, color=color).pixmap(10, 10))

    def set_connection(self, port, baud) -> None:
        if port:
            self._conn.setText(f"{port} · {baud}")
            self._update_conn_icon(True)
        else:
            self._conn.setText("未连接")
            self._update_conn_icon(False)

    def set_product(self, name: str) -> None:
        self._product = name
        self._refresh_product()

    def set_state(self, state: str) -> None:
        self._state = state
        self._refresh_product()

    def _refresh_product(self) -> None:
        st = _STATE_TEXT.get(self._state, self._state)
        self._product_lbl.setText(f"{self._product} · {st}" if self._product else st)

    def connection_text(self) -> str:
        return self._conn.text()

    def state_text(self) -> str:
        return self._product_lbl.text()

    def state_color(self) -> str:
        return theme.state_color(self._state)
