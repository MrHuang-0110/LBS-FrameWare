"""三段式布局左侧宽侧栏（256px，BG_SIDEBAR）：分组小标题「工作台」+ 图标+文字导航项。
选中 = BG_SELECTED 底 + ACCENT 文字/图标 + 左 3px ACCENT 亮条；常态 ICON_IDLE/TEXT_SECONDARY，
hover 背景 BG_HOVER 提亮；底部设置键 stretch 沉底，点击只发 action_triggered（设计 doc/ui-redesign.md §3）。"""
from __future__ import annotations
import qtawesome as qta
from PySide6.QtWidgets import QWidget, QVBoxLayout, QToolButton, QLabel
from PySide6.QtCore import Signal, Qt, QSize
from .. import theme

# 功能名（按钮文字标签，tooltip 同源）
_LABELS = {
    "device": "设备连接", "firmware": "固件更新", "scripts": "脚本下发",
    "editor": "代码编辑", "monitor": "数据监控", "settings": "设置",
}

# 分组小标题（设计 §3：10px 灰字 + 字距；参考 HTML uppercase tracking）
_GROUP_TITLE = "工作台"

# 浮窗触发类 key：点击只发 action_triggered（弹浮窗），不切页、不改变选中态
_POPUP_KEYS = {"device", "sensor"}

# 导航项行高约 44px；左内边距 16px（选中态 3px 亮条占用后视觉对齐）
_ITEM_H = 44
_PAD_LEFT = theme.SPACE_LG          # 16px，常态文字缩进
_PAD_LEFT_SEL = _PAD_LEFT - 3       # 13px，选中态补偿 3px 亮条宽度

# E3：键盘焦点环（a11y），全部按钮共用；不参与图标着色逻辑
_FOCUS_QSS = (
    f"QToolButton:focus {{ border: 1px solid {theme.ACCENT_FOCUS};"
    f" border-radius: {theme.RADIUS_SM}px; }}"
)


def _button_qss(selected: bool) -> str:
    """导航按钮样式：选中 = BG_SELECTED 底 + ACCENT 文字 + 左 3px ACCENT 亮条（内边距补偿 3px）；
    非选中 = 透明底 + TEXT_SECONDARY 文字，hover 用 BG_HOVER 提亮。"""
    if selected:
        return (
            f"QToolButton {{ border: none; background: {theme.BG_SELECTED};"
            f" color: {theme.ACCENT}; border-radius: {theme.RADIUS_SM}px;"
            f" border-left: 3px solid {theme.ACCENT};"
            f" padding-left: {_PAD_LEFT_SEL}px;"
            f" font-size: {theme.FONT_BODY}px; text-align: left; }}"
            f"QToolButton:hover {{ background: {theme.BG_SELECTED}; }} {_FOCUS_QSS}")
    return (
        f"QToolButton {{ border: none; background: transparent;"
        f" color: {theme.TEXT_SECONDARY}; border-radius: {theme.RADIUS_SM}px;"
        f" padding-left: {_PAD_LEFT}px;"
        f" font-size: {theme.FONT_BODY}px; text-align: left; }}"
        f"QToolButton:hover {{ background: {theme.BG_HOVER};"
        f" color: {theme.TEXT_PRIMARY}; }}"
        f"QToolButton:disabled {{ color: {theme.TEXT_DISABLED}; }} {_FOCUS_QSS}")


class ActivityBar(QWidget):
    current_changed = Signal(str)
    action_triggered = Signal(str)   # 浮窗类图标（popup keys）点击

    def __init__(self, items: list[tuple[str, str, bool]], parent=None,
                 popup_keys: set[str] | None = None,
                 settings_key: str | None = None):
        super().__init__(parent)
        self.setFixedWidth(theme.SIDEBAR_WIDTH)
        self.setStyleSheet(f"background: {theme.BG_SIDEBAR};"
                           f" border-right: 1px solid {theme.BORDER};")
        self._items = items
        self._popup_keys = set(popup_keys) if popup_keys is not None else set(_POPUP_KEYS)
        # 底部设置键：key 必须存在于 items（图标由 items 提供）；不存在则视为未指定
        if settings_key is not None and not any(k == settings_key for k, _, _ in items):
            settings_key = None
        self._settings_key = settings_key
        self._buttons: dict[str, QToolButton] = {}
        self._icon_names: dict[str, str] = {}
        self._icon_colors: dict[str, str] = {}
        self._current: str | None = None
        self._locked = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, theme.SPACE_SM, 0, theme.SPACE_SM)
        lay.setSpacing(theme.SPACE_XS)
        # 分组小标题（工作台，位于导航项之前）
        group = QLabel(_GROUP_TITLE)
        group.setStyleSheet(
            f"color: {theme.TEXT_DISABLED}; background: transparent;"
            f" font-size: 10px; letter-spacing: 2px;"
            f" padding: {theme.SPACE_SM}px {theme.SPACE_LG}px {theme.SPACE_XS}px {theme.SPACE_LG}px;")
        lay.addWidget(group)
        for key, icon_name, enabled in items:
            if key == self._settings_key:
                lay.addStretch(1)   # 底部设置键沉底（stretch 分隔）
            btn = self._make_button(key, icon_name, enabled)
            self._buttons[key] = btn
            lay.addWidget(btn)

    def _make_button(self, key, icon_name, enabled):
        btn = QToolButton()
        btn.setFixedSize(theme.SIDEBAR_WIDTH, _ITEM_H)
        btn.setIconSize(QSize(theme.ICON_LG, theme.ICON_LG))
        label = _LABELS.get(key, key)
        btn.setText(label)
        btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        btn.setToolTip(label + ("" if enabled else " · 即将推出"))
        btn.setCursor(Qt.PointingHandCursor if enabled else Qt.ArrowCursor)
        btn.setFocusPolicy(Qt.StrongFocus)   # E3：Tab 可达 + 焦点环
        color = theme.ICON_IDLE if enabled else theme.ICON_DISABLED
        btn.setIcon(qta.icon(icon_name, color=color))
        self._icon_names[key] = icon_name
        self._icon_colors[key] = color
        btn.setStyleSheet(_button_qss(False))
        btn.setEnabled(enabled)
        if enabled:
            btn.clicked.connect(lambda _=False, k=key: self._on_clicked(k))
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
        btn = self._buttons.get(key)
        if btn is None or not btn.isEnabled():
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
                color = theme.ACCENT
            elif self._locked:
                color = theme.ICON_DISABLED   # 锁定时置灰非当前项，给出视觉提示
            else:
                color = theme.ICON_IDLE
            self._icon_colors[key] = color
            btn.setIcon(qta.icon(self._icon_names[key], color=color))
            # 选中：BG_SELECTED 底 + ACCENT 文字/图标 + 左 3px ACCENT 亮条；focus 环叠加（E3）
            btn.setStyleSheet(_button_qss(selected))

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
