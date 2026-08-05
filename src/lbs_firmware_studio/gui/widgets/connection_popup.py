"""ConnectionPopup 设备连接浮窗（布局重构 v2 Task 2）。

- Qt.Popup 顶层窗口：BG_RAISED 底 + 1px BORDER + RADIUS_PANEL 圆角，宽约 300px；
  点击外部自动关闭（Qt::Popup 内建行为）。
- 竖向堆叠：标题「设备连接」（TEXT_SECONDARY 小字）→ ProductSelector（复用顶栏
  触发器）→ QFrame.HLine 分隔线 → ConnectionSelector(vertical=True)：串口/蓝牙
  radio 一行、端口下拉+刷新 一行、连接按钮+状态点 一行。
- 接口：current_product()/product_changed 透传 ProductSelector；connection() 返回
  ConnectionSelector；set_locked(busy) 禁用产品触发器与连接区（radio 组/目标/连接按钮）。
- 浮窗定位由 MainWindow 负责（Task 3），本组件仅提供固定宽度与 sizeHint。
- 颜色/尺寸全部走 theme 令牌，无硬编码色值；图标统一 qta fa5s.*。
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from .. import theme
from ...backend.serial_transport import SerialTransport
from ...backend.ble_transport import BleTransport
from .connection_selector import ConnectionSelector
from .product_selector import ProductSelector

# 浮窗固定宽度（设计：设备浮窗约 300px）
_POPUP_WIDTH = 300


class ConnectionPopup(QWidget):
    """设备连接浮窗：产品选择 + 连接区竖向堆叠。"""

    product_changed = Signal(str)  # 透传 ProductSelector.product_changed

    def __init__(self, profiles: dict, current: str,
                 port_lister: "Callable | None" = None,
                 ble_scan: "Callable | None" = None,
                 serial_factory=SerialTransport, ble_factory=BleTransport,
                 parent=None):
        super().__init__(parent)
        self.setObjectName("connection-popup")
        self.setWindowFlags(Qt.Popup)
        # QWidget 需显式启用 QSS 背景绘制（Qt 默认不画 QWidget 的 stylesheet 背景）
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedWidth(_POPUP_WIDTH)
        self.setStyleSheet(
            f"QWidget#connection-popup {{ background: {theme.BG_RAISED};"
            f" border: 1px solid {theme.BORDER};"
            f" border-radius: {theme.RADIUS_PANEL}px; }}")

        # 标题「设备连接」：TEXT_SECONDARY 小字
        self._title = QLabel("设备连接", self)
        self._title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._title.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; background: transparent;"
            f" font-size: {theme.FONT_CAPTION}px;"
            f" font-weight: {theme.WEIGHT_MEDIUM};")

        # 产品选择：复用顶栏 ProductSelector（横向触发器）
        self._product = ProductSelector(profiles, current, self)
        self._product.product_changed.connect(self.product_changed)

        # 分隔线
        self._line = QFrame(self)
        self._line.setFrameShape(QFrame.HLine)
        self._line.setFixedHeight(1)
        self._line.setStyleSheet(
            f"background-color: {theme.BORDER}; border: none;")

        # 连接区：ConnectionSelector 竖向模式（radio 一行 / 下拉+刷新 一行 / 连接+状态点 一行）
        self._connection = ConnectionSelector(
            port_lister=port_lister, ble_scan=ble_scan,
            serial_factory=serial_factory, ble_factory=ble_factory,
            vertical=True, parent=self)

        # 根布局：竖向堆叠
        lay = QVBoxLayout(self)
        lay.setContentsMargins(theme.SPACE_LG, theme.SPACE_MD,
                               theme.SPACE_LG, theme.SPACE_MD)
        lay.setSpacing(theme.SPACE_SM)
        lay.addWidget(self._title)
        lay.addSpacing(theme.SPACE_XS)
        lay.addWidget(self._product)
        lay.addWidget(self._line)
        lay.addWidget(self._connection)

    # ---- 公开接口 ----
    def current_product(self) -> str:
        """透传 ProductSelector 当前产品名。"""
        return self._product.current_product()

    def connection(self) -> ConnectionSelector:
        """返回连接区组件（ConnectionSelector）。"""
        return self._connection

    def set_locked(self, locked: bool) -> None:
        """整体忙碌：禁用产品触发器与连接区（radio 组/目标选择/连接按钮）。
        必须锁住 radio 组，否则 busy 时点 radio 会触发 ConnectionSelector._on_kind_toggled
        → disconnect() 关闭正在被下发流程复用的活链路（I1）。"""
        self._product.set_locked(locked)
        self._connection.set_locked(locked)
