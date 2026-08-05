"""ProductSelector 顶栏产品选择器（VS Code 风格下拉，设计文档 §4.2）。

- 触发器：16px 产品图标 + 当前产品名 + 12px chevron（自定义绘制，随禁用态变色）。
- 弹层：QFrame + Qt.Popup 窗口标志（点击外部自动关闭），BG_RAISED + BORDER + RADIUS_PANEL；
  内部 QListWidget 无边框，行高 36px，最多 6 行可见后滚动（全局 QSS 定制滚动条，走查 A1）。
- 列表项：16px 产品图标 + 产品名；当前项 BG_SELECTED 底 + 左 3px ACCENT 条 + 右 fa5s.check（SUCCESS 色）
  + 产品名 PRODUCT_GREEN，其它项 TEXT_PRIMARY（QStyledItemDelegate 自定义绘制，延续启动窗卡片视觉）。
- 交互：点击触发器开合 / Esc / 点击外部关闭；单击即选并 emit product_changed；QListWidget 原生键盘导航；
  set_locked 禁用触发器并强制关弹层；空列表显示「无可用产品」禁用态。
- 颜色/尺寸全部走 theme 令牌，无硬编码色值；图标统一 qta fa5s.*。
"""
from __future__ import annotations

import qtawesome as qta
from PySide6.QtCore import QEvent, QRect, Qt, QSize, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QFrame, QListWidget, QListWidgetItem, QPushButton, QStyle,
    QStyledItemDelegate, QStyleOptionButton, QStyleOptionViewItem, QVBoxLayout, QWidget,
)

from .. import theme

# 弹层最多可见行数，超出滚动
_MAX_VISIBLE_ROWS = 6
_ROW_HEIGHT = 36
_POPUP_WIDTH = 220
# 触发器尺寸（设计 §4.2）
_TRIGGER_MIN_W = 168
_TRIGGER_H = 30


class _TriggerButton(QPushButton):
    """自定义绘制触发器：16px microchip + 产品名 + 12px chevron-down，全部走 theme 令牌。"""

    def paintEvent(self, event):
        painter = QPainter(self)
        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        # 只画 QSS 背景/边框（含 hover/pressed/focus 环），图标与文字由下方手动绘制
        self.style().drawPrimitive(QStyle.PE_PanelButtonCommand, opt, painter, self)

        enabled = self.isEnabled()
        text_color = theme.PRODUCT_GREEN if enabled else theme.TEXT_DISABLED
        icon_color = theme.PRODUCT_GREEN if enabled else theme.TEXT_DISABLED
        chevron_color = theme.TEXT_SECONDARY if enabled else theme.TEXT_DISABLED

        icon = qta.icon("fa5s.microchip", color=icon_color).pixmap(theme.ICON_MD, theme.ICON_MD)
        painter.drawPixmap(theme.SPACE_MD + 4, (self.height() - theme.ICON_MD) // 2, icon)

        painter.setPen(QColor(text_color))
        text_rect = QRect(theme.SPACE_MD + 4 + theme.ICON_MD + theme.SPACE_SM, 0,
                          self.width() - (theme.SPACE_MD + 4 + theme.ICON_MD + theme.SPACE_SM) - 28,
                          self.height())
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text())

        chevron = qta.icon("fa5s.chevron-down", color=chevron_color).pixmap(12, 12)
        painter.drawPixmap(self.width() - 12 - 12, (self.height() - 12) // 2, chevron)
        painter.end()


class _ProductDelegate(QStyledItemDelegate):
    """列表项自定义绘制：当前项 BG_SELECTED 底 + 左 3px ACCENT 条 + 右 fa5s.check + 产品名 PRODUCT_GREEN。"""

    def sizeHint(self, option, index):
        return QSize(_POPUP_WIDTH, _ROW_HEIGHT)

    def paint(self, painter: QPainter, option, index) -> None:
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        painter.save()

        rect = opt.rect
        selected = bool(opt.state & QStyle.State_Selected)
        hovered = bool(opt.state & QStyle.State_MouseOver)

        # 背景
        if selected:
            painter.fillRect(rect, QColor(theme.BG_SELECTED))
        elif hovered:
            painter.fillRect(rect, QColor(theme.BG_HOVER))
        # 左 3px ACCENT 条（仅当前项）
        if selected:
            painter.fillRect(QRect(rect.left(), rect.top(), 3, rect.height()), QColor(theme.ACCENT))

        # 16px 产品图标
        icon_color = theme.PRODUCT_GREEN if selected else theme.ICON_IDLE
        icon = qta.icon("fa5s.microchip", color=icon_color).pixmap(theme.ICON_MD, theme.ICON_MD)
        icon_x = rect.left() + theme.SPACE_MD
        icon_y = rect.top() + (rect.height() - theme.ICON_MD) // 2
        painter.drawPixmap(icon_x, icon_y, icon)

        # 产品名（当前项 PRODUCT_GREEN，其它项 TEXT_PRIMARY）
        color = theme.PRODUCT_GREEN if selected else theme.TEXT_PRIMARY
        painter.setPen(QColor(color))
        text_rect = QRect(icon_x + theme.ICON_MD + theme.SPACE_SM, rect.top(),
                          rect.width() - (icon_x + theme.ICON_MD + theme.SPACE_SM) - 28, rect.height())
        name = index.data(Qt.DisplayRole) or ""
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, name)

        # 右侧 fa5s.check（仅当前项）
        if selected:
            check = qta.icon("fa5s.check", color=theme.SUCCESS).pixmap(theme.ICON_MD, theme.ICON_MD)
            painter.drawPixmap(rect.right() - theme.ICON_MD - theme.SPACE_MD, icon_y, check)

        painter.restore()


class _PopupFrame(QFrame):
    """弹层：Qt.Popup 窗口标志，点击外部自动关闭（hide 时经事件过滤器通知 selector）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("popup")
        self.setWindowFlags(Qt.Popup)
        self.setFixedWidth(_POPUP_WIDTH)
        self.setStyleSheet(
            f"QFrame#popup {{ background: {theme.BG_RAISED};"
            f" border: 1px solid {theme.BORDER}; border-radius: {theme.RADIUS_PANEL}px; }}")


class ProductSelector(QWidget):
    """顶栏产品选择器：当前产品 + 下拉切换（设计 §4.2）。"""

    product_changed = Signal(str)  # 切换产品（选中即发）

    def __init__(self, profiles: dict, current: str, parent=None):
        super().__init__(parent)
        # 容器最小宽度对齐触发器（168px）：防止顶层 QHBoxLayout 把它压成 0 宽
        # 导致触发器溢出容器（BUG1 回归测试 test_product_selector_min_width_after_show）。
        # 高度由顶栏 48px 容器决定，此处只约束宽度。
        self.setMinimumWidth(_TRIGGER_MIN_W)
        self._names = list(profiles.keys())
        self._locked = False
        self._popup_open = False

        # 触发器
        self._trigger = _TriggerButton(self)
        self._trigger.setObjectName("product-trigger")
        self._trigger.setMinimumWidth(_TRIGGER_MIN_W)
        self._trigger.setFixedHeight(_TRIGGER_H)
        self._trigger.setCursor(Qt.PointingHandCursor)
        self._trigger.clicked.connect(self._toggle_popup)

        # 弹层 + 列表
        self._popup = _PopupFrame(self)
        self._popup.installEventFilter(self)
        self._list = QListWidget(self._popup)
        self._list.setItemDelegate(_ProductDelegate(self._list))
        self._list.setUniformItemSizes(True)
        self._list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # 弹层固定宽 220px，item 视觉完整，无需横向滚动
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        lay = QVBoxLayout(self._popup)
        lay.setContentsMargins(theme.SPACE_XS, theme.SPACE_XS, theme.SPACE_XS, theme.SPACE_XS)
        lay.setSpacing(0)
        lay.addWidget(self._list)
        self._list.itemClicked.connect(self._on_item_activated)
        self._list.itemActivated.connect(self._on_item_activated)

        # 初始状态
        if self._names:
            self._current = current if current in self._names else self._names[0]
            self._trigger.setText(self._current)
        else:
            self._current = ""
            self._trigger.setText("无可用产品")
            self._trigger.setEnabled(False)

    # ---- 弹层开合 ----
    def _toggle_popup(self) -> None:
        if self._locked:
            return
        if self._popup_open:
            self._close_popup()
        else:
            self._open_popup()

    def _open_popup(self) -> None:
        if not self._names or self._locked:
            return
        self._rebuild_list()
        pos = self._trigger.mapToGlobal(self._trigger.rect().bottomLeft())
        pos.setY(pos.y() + theme.SPACE_XS)
        self._popup.move(pos)
        self._popup.show()
        self._popup.raise_()
        self._list.setFocus()
        self._popup_open = True

    def _close_popup(self) -> None:
        if self._popup_open:
            self._popup.hide()   # hide 触发 Hide 事件 → eventFilter 置 _popup_open=False
        else:
            self._popup_open = False

    def is_popup_open(self) -> bool:
        return self._popup_open

    def eventFilter(self, obj, event) -> bool:
        if obj is self._popup:
            if event.type() == QEvent.Hide:
                self._popup_open = False
            elif event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
                self._close_popup()
                return True
        return super().eventFilter(obj, event)

    # ---- 列表 ----
    def _rebuild_list(self) -> None:
        self._list.clear()
        for name in self._names:
            item = QListWidgetItem(name)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._list.addItem(item)
        idx = self._names.index(self._current) if self._current in self._names else 0
        self._list.setCurrentRow(idx)
        self._list.setFixedHeight(min(len(self._names), _MAX_VISIBLE_ROWS) * _ROW_HEIGHT)

    def _on_item_activated(self, item: QListWidgetItem | None) -> None:
        name = item.data(Qt.DisplayRole) if item is not None else None
        self._close_popup()
        if name and name in self._names and name != self._current and not self._locked:
            self._current = name
            self._trigger.setText(name)
            self.product_changed.emit(name)

    # ---- 公开接口 ----
    def current_product(self) -> str:
        return self._current

    def product_names(self) -> list[str]:
        return list(self._names)

    def trigger_button(self) -> QPushButton:
        return self._trigger

    def select_product(self, name: str) -> bool:
        """程序化切换。锁定中或名字不存在返回 False。"""
        if self._locked or name not in self._names:
            return False
        if name != self._current:
            self._current = name
            self._trigger.setText(name)
            self.product_changed.emit(name)
        return True

    def set_locked(self, locked: bool) -> None:
        self._locked = locked
        self._trigger.setEnabled(not locked)
        if locked:
            self._close_popup()
