"""固件更新页：固件源 + 待发送文件夹 + 开始按钮 + 阶段进度 + 日志。分组框布局。"""
from __future__ import annotations
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QProgressBar, QLineEdit, QGroupBox,
                               QMessageBox)
from PySide6.QtCore import Signal
import qtawesome as qta
from .. import theme
from ..widgets.log_view import LogView


class FirmwarePage(QWidget):
    start_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._profile = None
        self._dir_edit = QLineEdit(); self._dir_edit.setReadOnly(True)
        self._summary = QLabel("待发送: -")
        # 「开始固件更新」：主色按钮（QSS #primary = ACCENT 底 + TEXT_ON_ACCENT 前景，
        # 图标 fa5s.download、ICON_MD），宽度限 180px，点击弹二次确认（B2）。
        self._start = QPushButton("开始固件更新"); self._start.setObjectName("primary")
        self._start.setIcon(qta.icon("fa5s.download", color=theme.TEXT_ON_ACCENT))
        self._start.setMaximumWidth(180)
        self._start.clicked.connect(self.confirm_start)
        # 阶段 chip：色点（state_color 矢量图标）+ 阶段文案（STAGE_TEXT），文字随状态变色。
        self._stage_dot = QLabel()
        self._stage = QLabel()
        self._bar = QProgressBar(); self._bar.setRange(0, 100); self._bar.setValue(0)
        self._bar.setFormat("0%")
        self._log = LogView(max_blocks=500)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(theme.SPACE_LG, theme.SPACE_LG, theme.SPACE_LG, theme.SPACE_LG)
        lay.setSpacing(theme.SPACE_MD)

        # 组1：固件源
        src_group = QGroupBox("固件源")
        src_lay = QVBoxLayout(src_group)
        src_lay.setSpacing(theme.SPACE_SM)
        row = QHBoxLayout(); row.setSpacing(theme.SPACE_SM)
        row.addWidget(QLabel("目录:")); row.addWidget(self._dir_edit, 1)
        src_lay.addLayout(row)
        src_lay.addWidget(self._summary)
        lay.addWidget(src_group)

        # 组2：操作与进度（§4.4：按钮 + 阶段 chip 同行，进度条下一行）
        op_group = QGroupBox("操作")
        op_lay = QVBoxLayout(op_group)
        op_lay.setSpacing(theme.SPACE_SM)
        op_row = QHBoxLayout(); op_row.setSpacing(theme.SPACE_SM)
        op_row.addWidget(self._start)
        op_row.addStretch(1)
        op_row.addWidget(self._stage_dot)
        op_row.addWidget(self._stage)
        op_lay.addLayout(op_row)
        op_lay.addWidget(self._bar)
        lay.addWidget(op_group)

        # 组3：日志
        log_group = QGroupBox("日志")
        log_lay = QVBoxLayout(log_group)
        log_lay.setSpacing(theme.SPACE_SM)
        log_lay.addWidget(self._log)
        lay.addWidget(log_group, 1)

        self.on_state("idle")  # 初始化阶段 chip（色点 + 文案 + 颜色）

    def set_profile(self, profile) -> None:
        self._profile = profile
        self._dir_edit.setText(str(profile.firmware_dir))
        self._summary.setText("待发送: " + ", ".join(profile.folders))

    def set_busy(self, busy: bool) -> None:
        self._start.setEnabled(not busy)

    def confirm_start(self) -> None:
        """开始固件更新二次确认（B2）：No 不发信号，Yes 才发 start_requested。"""
        if self._profile is None:
            detail = "未选择产品"
        else:
            detail = (f"目标: {self._profile.firmware_dir}\n待发送: "
                      + ", ".join(self._profile.folders))
        answer = QMessageBox.question(
            self, "确认开始固件更新",
            f"确认开始固件更新？\n\n{detail}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer == QMessageBox.Yes:
            self.start_requested.emit()

    def on_progress(self, done: int, total: int) -> None:
        pct = int(done * 100 / total) if total else 0
        self._bar.setValue(pct)
        self._bar.setFormat(f"{pct}%")  # B10：进度条显示百分比

    def on_state(self, state: str) -> None:
        color = theme.state_color(state)
        self._stage_dot.setPixmap(qta.icon("fa5s.circle", color=color)
                                  .pixmap(theme.ICON_SM, theme.ICON_SM))
        self._stage.setText(theme.STAGE_TEXT.get(state, state))
        self._stage.setStyleSheet(f"color: {color}; background: transparent;")

    def on_log(self, msg: str) -> None:
        level = "error" if ("失败" in msg or "错误" in msg) else "info"
        self._log.append(msg, level=level)

    # --- 测试辅助访问器 ---
    def start_button(self): return self._start
    def stage_dot(self): return self._stage_dot
    def summary_text(self): return self._summary.text()
    def firmware_dir_text(self): return self._dir_edit.text()
    def progress_value(self): return self._bar.value()
    def stage_text(self): return self._stage.text()
    def log_text(self): return self._log.plain_text()
