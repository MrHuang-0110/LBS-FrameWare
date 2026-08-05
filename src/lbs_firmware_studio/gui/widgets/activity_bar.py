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

# 浮窗触发类 key：点击只发 action_triggered（弹浮窗），不切页、不改变选中态
_POPUP_KEYS = {"device", "sensor"}

# E3：键盘焦点环（a11y），全部按钮共用；不参与图标着色逻辑
_FOCUS_QSS = (
    f"QToolButton:focus {{ border: 1px solid {theme.ACCENT_FOCUS};"
    f" border-radius: {theme.RADIUS_SM}px; }}"
)


class ActivityBar(QWidget):
    current_changed = Signal(str)
    action_triggered = Signal(str)   # 浮窗类图标（popup keys）点击

    def __init__(self, items: list[tuple[str, str, bool]], parent=None,
                 popup_keys: set[str] | None = None,
                 settings_key: str | None = None):
        super().__init__(parent)
        self.setFixedWidth(48)
        self.setStyleSheet(f"background: {theme.BG_BAR};")
        self._items = items
        self._popup_keys = set(popup_keys) if popup_keys is not None else set(_POPUP_KEYS)
        # 底部设置键：key 必须存在于 items（图标由 items 提供）；不存在则视为未指定
        if settings_key is not None and not any(k == settings_key for k, _, _ in items):
            settings_key = None
        self._settings_key = settings_key
        self._buttons: dict[str, QToolButton] = {}
        self._icon_colors: dict[str, str] = {}
        self._current: str | None = None
        self._locked = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 4); lay.setSpacing(0)
        for key, icon_name, enabled in items:
            if key == self._settings_key:
                lay.addStretch(1)   # 底部设置键沉底（stretch 分隔）
            btn = self._make_button(key, icon_name, enabled)
            self._buttons[key] = btn
            lay.addWidget(btn, 0, Qt.AlignHCenter)

    def _make_button(self, key, icon_name, enabled):
        btn = QToolButton()
        btn.setFixedSize(48, 48)
        btn.setIconSize(QSize(24, 24))
        btn.setToolTip(_LABELS.get(key, key) + ("" if enabled else " · 即将推出"))
        btn.setCursor(Qt.PointingHandCursor if enabled else Qt.ArrowCursor)
        btn.setFocusPolicy(Qt.StrongFocus)   # E3：Tab 可达 + 焦点环
        color = theme.ICON_IDLE if enabled else theme.ICON_DISABLED
        btn.setIcon(qta.icon(icon_name, color=color))
        self._icon_colors[key] = color
        btn.setStyleSheet(
            f"QToolButton {{ border: none; background: transparent; }}"
            f"QToolButton:hover {{ background: {theme.BG_HOVER}; }} {_FOCUS_QSS}")
        btn.setEnabled(enabled)
        if enabled:
            btn.clicked.connect(lambda _=False, k=key: self._on_clicked(k))
        self._icon_names = getattr(self, "_icon_names", {})
        self._icon_names[key] = icon_name
        return btn

    def _on_clicked(self, key: str) -> None:
        """统一点击入口：底部设置键/浮窗类 key → action_triggered；页面类 → current_changed。"""
        if key == self._settings_key or key in self._popup_keys:
            self.action_triggered.emit(key)   # 设置/浮窗触发：不切页、不改选中态
        else:
            self.set_current(key)

    def set_current(self, key: str) -> None:
        if self._locked:
            return
        if key == self._settings_key:
            return   # 底部设置键不参与选中态（只发 action_triggered）
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
            # 选中：左侧 2px ACCENT 亮条 + BG_HOVER 底；focus 环叠加（E3）
            if selected:
                btn.setStyleSheet(
                    f"QToolButton {{ border: none; background: {theme.BG_HOVER};"
                    f" border-left: 2px solid {theme.ACCENT}; }}"
                    f"QToolButton:hover {{ background: {theme.BG_HOVER}; }} {_FOCUS_QSS}")
            else:
                btn.setStyleSheet(
                    f"QToolButton {{ border: none; background: transparent; }}"
                    f"QToolButton:hover {{ background: {theme.BG_HOVER}; }} {_FOCUS_QSS}")

    def current_key(self) -> str:
        return self._current

    def keys(self) -> list[str]:
        return [k for k, _, _ in self._items]

    def nav_keys(self) -> list[str]:
        """导航键列表（不含底部设置键）——MainWindow 的 nav 语义。"""
        return [k for k, _, _ in self._items if k != self._settings_key]

    def is_enabled(self, key: str) -> bool:
        return self._buttons[key].isEnabled()

    def icon_color(self, key: str) -> str:
        """当前应用于该项图标的颜色（供测试断言锁定置灰效果）。"""
        return self._icon_colors.get(key, "")

    def set_locked(self, locked: bool) -> None:
        self._locked = locked
        self._restyle()
