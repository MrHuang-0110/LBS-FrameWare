"""固件更新区组件：固件源 + 开始按钮 + 进度条 + 阶段 chip + 单行进度文本（可复用）。

- 固件源：set_profile(profile)（页面场景，含「待发送」摘要）或
  set_firmware_dir_getter(getter)（浮窗场景）填充只读目录框。
- 开始按钮：QSS #primary 主色，全宽 30px，点击直接发 start_requested（无二次确认）。
- 阶段 chip：色点（state_color）+ 阶段文案（STAGE_TEXT）包进药丸容器，背景/边框随状态变色。
- 深色主题全部走 theme 令牌；图标统一 qta fa5s.*。
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QProgressBar, QLineEdit, QFrame)
from PySide6.QtGui import QColor
from PySide6.QtCore import Signal
import qtawesome as qta

from .. import theme


class FirmwareUpdateSection(QWidget):
    """固件更新区：固件源选择 + 开始按钮 + 进度条 + 单行进度文本。"""

    start_requested = Signal()   # 开始固件更新（点击直接触发，无确认框）

    def __init__(self, parent=None):
        super().__init__(parent)
        self._profile = None
        self._dir_getter: Callable | None = None
        self._dir_edit = QLineEdit(); self._dir_edit.setReadOnly(True)
        # 「待发送」摘要：仅页面场景（set_profile）显示；浮窗场景无 profile 时隐藏
        self._summary = QLabel("待发送: -")
        self._summary.hide()
        # 开始按钮：QSS #primary 主色（ACCENT 底 + TEXT_ON_ACCENT 前景），全宽 30px 高，
        # 点击直接发 start_requested（无二次确认）。
        self._start = QPushButton("开始固件更新")
        self._start.setObjectName("primary")
        self._start.setIcon(qta.icon("fa5s.download", color=theme.TEXT_ON_ACCENT))
        self._start.setFixedHeight(30)
        self._start.clicked.connect(self.confirm_start)
        # 阶段 chip：色点 + 阶段文案包进药丸容器，背景/边框随状态变色
        #（idle 中性 / 进行中 WARNING / done SUCCESS / error ERROR）
        self._stage_dot = QLabel()
        self._stage = QLabel()
        self._stage_chip = QFrame()
        self._stage_chip.setObjectName("stageChip")
        chip_lay = QHBoxLayout(self._stage_chip)
        chip_lay.setContentsMargins(theme.SPACE_SM, theme.SPACE_XS, theme.SPACE_MD, theme.SPACE_XS)
        chip_lay.setSpacing(theme.SPACE_XS)
        chip_lay.addWidget(self._stage_dot)
        chip_lay.addWidget(self._stage)
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setFormat("0%")
        # 单行当前进度：日志末条 + 进度百分比合成（TEXT_SECONDARY + mono 字体），
        # 无活动时显示「就绪」。
        self._progress_text = QLabel(theme.STAGE_TEXT["idle"])
        self._progress_text.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-family: {theme.MONO_FONT};")
        self._last_log: str | None = None
        self._last_pct: int | None = None

        # 布局：目录行 / 开始按钮（全宽）/ 进度条行（进度条+阶段 chip）/ 单行进度文本（底部）
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(theme.SPACE_SM)
        row = QHBoxLayout()
        row.setSpacing(theme.SPACE_SM)
        row.addWidget(QLabel("目录:"))
        row.addWidget(self._dir_edit, 1)
        lay.addLayout(row)
        lay.addWidget(self._summary)
        lay.addWidget(self._start)          # 全宽（同连接按钮）
        bar_row = QHBoxLayout()
        bar_row.setSpacing(theme.SPACE_SM)
        bar_row.addWidget(self._bar, 1)
        bar_row.addWidget(self._stage_chip)
        lay.addLayout(bar_row)
        lay.addWidget(self._progress_text)

        self.on_state("idle")  # 初始化阶段 chip（色点 + 文案 + 颜色）与进度文本

    # ---- 固件源 ----
    def set_profile(self, profile) -> None:
        """页面场景：设置产品 profile，目录/摘要由 profile 填充。"""
        self._profile = profile
        self._dir_edit.setText(str(profile.firmware_dir))
        self._summary.setText("待发送: " + ", ".join(profile.folders))
        self._summary.show()

    def set_firmware_dir_getter(self, getter: Callable | None) -> None:
        """浮窗场景：设置固件目录 getter（返回固件路径 str/Path），立即刷新目录文本。"""
        self._dir_getter = getter
        if getter is not None:
            self._dir_edit.setText(str(getter()))

    def set_source_locked(self, locked: bool) -> None:
        """锁定固件源选择（只读目录框禁用）。"""
        self._dir_edit.setEnabled(not locked)

    # ---- 开始按钮 / 二次确认 ----
    def set_busy(self, busy: bool) -> None:
        self._start.setEnabled(not busy)

    def confirm_start(self) -> None:
        """开始固件更新：点击直接发 start_requested（无二次确认）。方法名保留（按钮接线不变）。"""
        self.start_requested.emit()

    # ---- 进度回填（deployer 信号接线：progress/log/state_changed）----
    def on_progress(self, done: int, total: int) -> None:
        pct = int(done * 100 / total) if total else 0
        self.set_progress_pct(pct)

    def set_progress_pct(self, pct: int) -> None:
        """直接设置进度百分比（浮窗回填接口的基础）。"""
        self._bar.setValue(pct)
        self._bar.setFormat(f"{pct}%")  # B10：进度条显示百分比
        self._last_pct = pct
        self._refresh_progress_text()

    def _update_chip_style(self, state: str) -> None:
        """阶段 chip 背景/边框随状态变色（设计 §4 状态 chip）。
        done=SUCCESS_BG / error=ERROR_BG / 进行中=WARNING_BG / idle=中性；
        边框用语义色半透明（QColor.setAlpha 后 name() 得 hex8）。"""
        if state == "done":
            bg, base = theme.SUCCESS_BG, theme.SUCCESS
        elif state == "error":
            bg, base = theme.ERROR_BG, theme.ERROR
        elif state == "idle":
            bg, base = theme.BG_INPUT, theme.ICON_IDLE
        else:  # compiling/connecting/entering_upgrade/reconnecting/transfering
            bg, base = theme.WARNING_BG, theme.WARNING
        border = QColor(base)
        border.setAlpha(80)
        self._stage_chip.setStyleSheet(
            f"QFrame#stageChip {{ background: {bg}; border: 1px solid {border.name(QColor.HexArgb)};"
            f" border-radius: {theme.RADIUS_FULL}px; }}")

    def on_state(self, state: str) -> None:
        color = theme.state_color(state)
        self._stage_dot.setPixmap(qta.icon("fa5s.circle", color=color)
                                  .pixmap(theme.ICON_SM, theme.ICON_SM))
        self._stage.setText(theme.STAGE_TEXT.get(state, state))
        self._stage.setStyleSheet(f"color: {color}; background: transparent;")
        self._update_chip_style(state)
        # done/error 保留「最后日志 + 进度」快照；其余状态清掉上一轮残留并刷新为「就绪」
        #（deployer 新一轮从 connecting 开始不经 idle，不清空会残留上一轮文本）。
        if state not in ("done", "error"):
            self._last_log = None
            self._last_pct = None
            self._refresh_progress_text()

    def on_log(self, msg: str) -> None:
        self._last_log = msg
        self._refresh_progress_text()

    def set_current_text(self, text: str) -> None:
        """直接覆盖单行进度文本（浮窗回填接口的基础）。"""
        self._progress_text.setText(text)

    def _refresh_progress_text(self) -> None:
        """单行当前进度 = 最后一条日志 + 进度百分比；两者皆无时显示「就绪」。"""
        if self._last_pct is not None:
            if self._last_log:
                self._progress_text.setText(f"{self._last_log} {self._last_pct}%")
            else:
                self._progress_text.setText(f"{self._last_pct}%")
        else:
            self._progress_text.setText(self._last_log or theme.STAGE_TEXT["idle"])

    # --- 测试辅助访问器 ---
    def start_button(self): return self._start
    def stage_dot(self): return self._stage_dot
    def summary_text(self): return self._summary.text()
    def firmware_dir_text(self): return self._dir_edit.text()
    def progress_value(self): return self._bar.value()
    def stage_text(self): return self._stage.text()
    def current_progress_text(self): return self._progress_text.text()
