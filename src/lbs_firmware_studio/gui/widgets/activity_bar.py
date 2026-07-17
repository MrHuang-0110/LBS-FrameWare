"""VS Code 风格 Activity Bar：纯图标竖条，悬停 tooltip，选中左侧 2px 蓝亮条。"""
from __future__ import annotations
import qtawesome as qta
from PySide6.QtWidgets import QWidget, QVBoxLayout, QToolButton
from PySide6.QtCore import Signal, Qt, QSize
from .. import theme

# 功能名 tooltip
_LABELS = {
    "device": "固件与监控", "firmware": "固件更新", "scripts": "脚本下发",
    "editor": "代码编辑", "monitor": "数据监控", "settings": "设置",
}


class ActivityBar(QWidget):
    current_changed = Signal(str)

    def __init__(self, items: list[tuple[str, str, bool]], parent=None):
        super().__init__(parent)
        self.setFixedWidth(48)
        self.setStyleSheet(f"background: {theme.BG_BAR};")
        self._items = items
        self._buttons: dict[str, QToolButton] = {}
        self._icon_colors: dict[str, str] = {}
        self._current: str | None = None
        self._locked = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 4); lay.setSpacing(0)
        for key, icon_name, enabled in items:
            if key == "settings":
                lay.addStretch(1)   # 设置沉底
            btn = self._make_button(key, icon_name, enabled)
            self._buttons[key] = btn
            lay.addWidget(btn, 0, Qt.AlignHCenter)

    def _make_button(self, key, icon_name, enabled):
        btn = QToolButton()
        btn.setFixedSize(48, 48)
        btn.setIconSize(QSize(24, 24))
        btn.setToolTip(_LABELS.get(key, key) + ("" if enabled else " · 即将推出"))
        btn.setCursor(Qt.PointingHandCursor if enabled else Qt.ArrowCursor)
        color = theme.ICON_IDLE if enabled else theme.ICON_DISABLED
        btn.setIcon(qta.icon(icon_name, color=color))
        self._icon_colors[key] = color
        btn.setStyleSheet("QToolButton { border: none; background: transparent; }")
        btn.setEnabled(enabled)
        if enabled:
            btn.clicked.connect(lambda _=False, k=key: self.set_current(k))
        self._icon_names = getattr(self, "_icon_names", {})
        self._icon_names[key] = icon_name
        return btn

    def set_current(self, key: str) -> None:
        if self._locked:
            return
        if key not in self._buttons or not self._buttons[key].isEnabled():
            return
        if key == self._current:
            return
        self._current = key
        self._restyle()
        self.current_changed.emit(key)

    def _restyle(self) -> None:
        for key, btn in self._buttons.items():
            if not btn.isEnabled():
                continue
            selected = (key == self._current)
            if selected:
                color = theme.TEXT_ON_ACCENT
            elif self._locked:
                color = theme.ICON_DISABLED   # 锁定时置灰非当前项，给出视觉提示
            else:
                color = theme.ICON_IDLE
            self._icon_colors[key] = color
            btn.setIcon(qta.icon(self._icon_names[key], color=color))
            # 选中：左侧 2px 蓝亮条 + 轻背景
            if selected:
                btn.setStyleSheet(
                    f"QToolButton {{ border: none; background: {theme.BG_HOVER};"
                    f" border-left: 2px solid {theme.ACCENT}; }}")
            else:
                btn.setStyleSheet("QToolButton { border: none; background: transparent; }")

    def current_key(self) -> str:
        return self._current

    def keys(self) -> list[str]:
        return [k for k, _, _ in self._items]

    def is_enabled(self, key: str) -> bool:
        return self._buttons[key].isEnabled()

    def icon_color(self, key: str) -> str:
        """当前应用于该项图标的颜色（供测试断言锁定置灰效果）。"""
        return self._icon_colors.get(key, "")

    def set_locked(self, locked: bool) -> None:
        self._locked = locked
        self._restyle()
