"""底部状态栏（24px BG_BAR 深色）：左连接状态，右部署阶段（去产品名，设计 §3/§4.1/B9）。
阶段文案唯一来源 = theme.STAGE_TEXT（§3.6 C4）；前景统一走 STATUSBAR_ON 组（A7）；
状态点用矢量图标 fa5s.*（A3），颜色走令牌。"""
from __future__ import annotations
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
import qtawesome as qta
from .. import theme


class StatusBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(24)
        self.setStyleSheet(f"background: {theme.STATUSBAR};")
        self._icon = QLabel()
        self._conn = QLabel("未连接")
        self._deploy = QLabel("")   # 单行部署进度文本（固件更新浮窗关闭后仍可见的进展反馈）
        self._stage_dot = QLabel()
        self._stage_lbl = QLabel("")
        self._state = "idle"
        for lbl in (self._conn, self._stage_lbl):
            lbl.setStyleSheet(
                f"color: {theme.STATUSBAR_ON}; font-size: {theme.FONT_CAPTION}px; background: transparent;")
        self._deploy.setStyleSheet(
            f"color: {theme.STATUSBAR_ON_MUTED}; font-size: {theme.FONT_CAPTION}px;"
            f" font-family: {theme.MONO_FONT}; background: transparent;")
        # 超长日志（如固件文件名/超时消息）限宽 320px，避免挤压右侧阶段 chip/推出窗口
        # （QLabel 无 setTextElideMode，超长部分被裁剪，完整文本可经 tooltip 查看）
        self._deploy.setMaximumWidth(320)
        self._icon.setStyleSheet("background: transparent;")
        self._stage_dot.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(theme.SPACE_MD, 0, theme.SPACE_MD, 0)
        lay.setSpacing(theme.SPACE_XS + 2)
        lay.addWidget(self._icon)
        lay.addWidget(self._conn)
        lay.addStretch(1)
        lay.addWidget(self._deploy)
        lay.addWidget(self._stage_dot)
        lay.addWidget(self._stage_lbl)
        self._update_conn_icon(False)
        self._refresh_state()

    def _update_conn_icon(self, connected: bool) -> None:
        """连接点矢量图标（A3）：已连接 SUCCESS 实心圆；未连接弱化圈（A7 STATUSBAR_ON_MUTED）。"""
        color = theme.SUCCESS if connected else theme.STATUSBAR_ON_MUTED
        name = "fa5s.circle" if connected else "fa5s.circle-notch"
        self._icon.setPixmap(qta.icon(name, color=color).pixmap(theme.ICON_XS, theme.ICON_XS))
        self._conn.setStyleSheet(
            f"color: {theme.STATUSBAR_ON if connected else theme.STATUSBAR_ON_MUTED};"
            f" font-size: {theme.FONT_CAPTION}px; background: transparent;")

    def set_connection(self, port, baud) -> None:
        if port:
            self._conn.setText(f"{port} · {baud}")
        else:
            self._conn.setText("未连接")
        self._update_conn_icon(bool(port))

    def set_product(self, name: str) -> None:
        """兼容保留（main_window 调用点）：状态栏不再显示产品名（设计 B9/§4.1），输入被忽略。
        产品身份由顶栏 ProductSelector 承担。"""
        pass

    def set_deploy_text(self, text: str) -> None:
        """单行部署进度文本（deployer 日志/百分比；固件更新浮窗关闭后仍可见）。
        超长文本被限宽裁剪，完整内容经 tooltip 查看。"""
        self._deploy.setText(text)
        self._deploy.setToolTip(text)   # 限宽裁剪的完整文本 hover 可看
        self._deploy.setVisible(bool(text))

    def set_state(self, state: str) -> None:
        self._state = state
        self._refresh_state()

    def _refresh_state(self) -> None:
        """阶段文案 = theme.STAGE_TEXT（§3.6 唯一来源）+ 状态色点矢量图标（颜色走 state_color）。"""
        st = theme.STAGE_TEXT.get(self._state, self._state)
        self._stage_lbl.setText(st)
        color = theme.state_color(self._state)
        self._stage_dot.setPixmap(qta.icon("fa5s.circle", color=color).pixmap(theme.ICON_XS, theme.ICON_XS))

    def connection_text(self) -> str:
        return self._conn.text()

    def deploy_text(self) -> str:
        return self._deploy.text()

    def state_text(self) -> str:
        return self._stage_lbl.text()

    def state_color(self) -> str:
        return theme.state_color(self._state)
