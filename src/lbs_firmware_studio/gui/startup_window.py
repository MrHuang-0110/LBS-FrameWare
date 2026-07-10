"""启动产品选择：单击框选高亮，双击进入。VS Code 深色卡片。"""
from __future__ import annotations
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Signal, Qt
from . import theme


class _Card(QFrame):
    clicked = Signal(str)
    double_clicked = Signal(str)

    def __init__(self, name, prof, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self._name = name
        self.setFixedSize(180, 140)
        self._selected = False
        lay = QVBoxLayout(self)
        title = QLabel(name); title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"font-size:18px; font-weight:600; color:{theme.PRODUCT_GREEN}; background:transparent;")
        lay.addStretch(); lay.addWidget(title); lay.addStretch()
        self._apply()

    def set_selected(self, sel: bool) -> None:
        self._selected = sel; self._apply()

    def _apply(self) -> None:
        border = theme.ACCENT if self._selected else theme.BORDER
        width = 2 if self._selected else 1
        self.setStyleSheet(
            f"QFrame#card {{ background: {theme.BG_SIDEBAR}; border: {width}px solid {border};"
            f" border-radius: 10px; }}")

    def mousePressEvent(self, e):
        self.clicked.emit(self._name); super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        self.double_clicked.emit(self._name); super().mouseDoubleClickEvent(e)


class StartupWindow(QWidget):
    product_selected = Signal(str)     # 双击进入
    selection_changed = Signal(str)    # 单击框选

    def __init__(self, profiles: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LBS Firmware Studio")
        self._cards: dict[str, _Card] = {}
        self._selected: str | None = None
        outer = QVBoxLayout(self)
        t = QLabel("LBS Firmware Studio"); t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet(f"font-size:22px; color:{theme.TEXT_PRIMARY}; background:transparent;")
        sub = QLabel("双击选择要操作的产品"); sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(f"font-size:13px; color:{theme.TEXT_SECONDARY}; background:transparent;")
        outer.addWidget(t); outer.addWidget(sub)
        row = QHBoxLayout(); row.setSpacing(20)
        for name, prof in profiles.items():
            card = _Card(name, prof)
            card.clicked.connect(self._on_click)
            card.double_clicked.connect(self.product_selected.emit)
            self._cards[name] = card
            row.addWidget(card)
        outer.addLayout(row); outer.addStretch()

    def _on_click(self, name: str) -> None:
        self._selected = name
        for k, c in self._cards.items():
            c.set_selected(k == name)
        self.selection_changed.emit(name)

    def selected_product(self):
        return self._selected

    def click_product(self, name: str) -> None:
        self._cards[name].clicked.emit(name)

    def double_click_product(self, name: str) -> None:
        self._cards[name].double_clicked.emit(name)

    def all_text(self) -> str:
        return " ".join(self._cards.keys())
