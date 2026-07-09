"""固件更新页：固件源 + 待发送文件夹 + 开始按钮 + 阶段进度 + 日志。"""
from __future__ import annotations
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QProgressBar, QLineEdit)
from PySide6.QtCore import Signal
from ..widgets.log_view import LogView
from ..widgets.status_badge import _STATE_TEXT

_STAGE_TEXT = {
    "idle": "就绪", "compiling": "编译中", "connecting": "连接中",
    "entering_upgrade": "进入升级模式", "reconnecting": "等待设备重连",
    "transfering": "传输中", "done": "完成", "error": "出错",
}


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
        lay.addWidget(QLabel("固件更新"))
        row = QHBoxLayout(); row.addWidget(QLabel("固件源:")); row.addWidget(self._dir_edit, 1)
        lay.addLayout(row)
        lay.addWidget(self._summary)
        lay.addWidget(self._start)
        lay.addWidget(self._stage)
        lay.addWidget(self._bar)
        lay.addWidget(QLabel("日志"))
        lay.addWidget(self._log, 1)

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
        self._stage.setText(_STAGE_TEXT.get(state, state))

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
