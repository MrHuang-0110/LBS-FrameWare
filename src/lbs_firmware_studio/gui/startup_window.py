"""启动产品选择界面：每产品一张卡片，点击发出 product_selected。"""
from __future__ import annotations
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
                               QPushButton)
from PySide6.QtCore import Signal, Qt
from . import theme

_PROTO_LABEL = {"custom_frame": "自定义帧", "ymodem": "YMODEM"}


class StartupWindow(QWidget):
    product_selected = Signal(str)

    def __init__(self, profiles: dict, parent=None):
        super().__init__(parent)
        self._buttons = {}
        self.setWindowTitle("LBS Firmware Studio")
        outer = QVBoxLayout(self)
        outer.addWidget(self._center_label("LBS Firmware Studio", 22, theme.TEXT))
        outer.addWidget(self._center_label("选择要操作的产品", 15, theme.MUTED))
        cards = QHBoxLayout(); cards.setSpacing(20)
        for name, prof in profiles.items():
            cards.addWidget(self._make_card(name, prof))
        outer.addLayout(cards)
        outer.addStretch()

    def _center_label(self, text, size, color):
        lbl = QLabel(text); lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"font-size:{size}px; color:{color};")
        return lbl

    def _make_card(self, name, prof):
        card = QFrame(); card.setObjectName("card")
        card.setFixedSize(180, 200)
        lay = QVBoxLayout(card)
        title = QLabel(name); title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size:18px; font-weight:600;")
        ports = QLabel(f"{prof.display_ports} 端口"); ports.setAlignment(Qt.AlignCenter)
        proto = QLabel(_PROTO_LABEL.get(prof.protocol, prof.protocol))
        proto.setAlignment(Qt.AlignCenter); proto.setStyleSheet(f"color:{theme.MUTED};")
        btn = QPushButton("选择"); btn.setObjectName("primary")
        btn.clicked.connect(lambda: self.product_selected.emit(name))
        self._buttons[name] = btn
        lay.addStretch(); lay.addWidget(title); lay.addWidget(ports)
        lay.addWidget(proto); lay.addWidget(btn); lay.addStretch()
        return card

    def click_product(self, name: str) -> None:
        self._buttons[name].click()

    def all_text(self) -> str:
        return " ".join(b_name for b_name in self._buttons)
