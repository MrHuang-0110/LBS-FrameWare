"""固件更新页：固件源 + 待发送文件夹 + 开始按钮 + 阶段进度 + 日志。分组框布局。"""
from __future__ import annotations
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QProgressBar, QLineEdit, QGroupBox)
from PySide6.QtCore import Signal
from .. import theme
from ..widgets.log_view import LogView


class FirmwarePage(QWidget):
    start_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._profile = None
        self._dir_edit = QLineEdit(); self._dir_edit.setReadOnly(True)
        self._summary = QLabel("待发送: -")
        self._start = QPushButton("▶ 开始固件更新"); self._start.setObjectName("primary")
        self._start.clicked.connect(self.start_requested.emit)
        self._stage = QLabel("就绪")
        self._bar = QProgressBar(); self._bar.setRange(0, 100); self._bar.setValue(0)
        self._log = LogView()

        lay = QVBoxLayout(self)

        # 组1：固件源
        src_group = QGroupBox("固件源")
        src_lay = QVBoxLayout(src_group)
        row = QHBoxLayout(); row.addWidget(QLabel("目录:")); row.addWidget(self._dir_edit, 1)
        src_lay.addLayout(row)
        src_lay.addWidget(self._summary)
        lay.addWidget(src_group)

        # 组2：操作与进度
        op_group = QGroupBox("操作")
        op_lay = QVBoxLayout(op_group)
        op_lay.addWidget(self._start)
        op_lay.addWidget(self._stage)
        op_lay.addWidget(self._bar)
        lay.addWidget(op_group)

        # 组3：日志
        log_group = QGroupBox("日志")
        log_lay = QVBoxLayout(log_group)
        log_lay.addWidget(self._log)
        lay.addWidget(log_group, 1)

    def set_profile(self, profile) -> None:
        self._profile = profile
        self._dir_edit.setText(str(profile.firmware_dir))
        self._summary.setText("待发送: " + ", ".join(profile.folders))

    def set_busy(self, busy: bool) -> None:
        self._start.setEnabled(not busy)

    def on_progress(self, done: int, total: int) -> None:
        pct = int(done * 100 / total) if total else 0
        self._bar.setValue(pct)

    def on_state(self, state: str) -> None:
        self._stage.setText(theme.STAGE_TEXT.get(state, state))

    def on_log(self, msg: str) -> None:
        level = "error" if ("失败" in msg or "错误" in msg) else "info"
        self._log.append(msg, level=level)

    # --- 测试辅助访问器 ---
    def start_button(self): return self._start
    def summary_text(self): return self._summary.text()
    def firmware_dir_text(self): return self._dir_edit.text()
    def progress_value(self): return self._bar.value()
    def stage_text(self): return self._stage.text()
    def log_text(self): return self._log.plain_text()
