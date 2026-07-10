"""脚本编辑器页：模板下拉 + 代码编辑器（右上角浮槽位/下发按钮）+ 进度 + 日志。
单页闭环：选模板→编辑→保存(<slot>.py)→选槽→下发。GUI 只做界面，下发经 worker。"""
from __future__ import annotations
from pathlib import Path
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QComboBox, QProgressBar, QMessageBox, QMenu)
from PySide6.QtCore import Signal
from ..widgets.code_editor import CodeEditor
from ..widgets.log_view import LogView

_BLANK = "(空白)"
_STAGE_TEXT = {
    "idle": "就绪", "compiling": "编译中", "connecting": "连接中",
    "entering_upgrade": "进入升级模式", "reconnecting": "等待设备重连",
    "transfering": "传输中", "done": "完成", "error": "出错",
}


class ScriptEditorPage(QWidget):
    deploy_requested = Signal(Path, int)   # (write目录/<slot>.py, slot)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._profile = None
        self._slot = 0
        self._dirty = False

        # 顶部：模板下拉 + 保存
        self._tpl_combo = QComboBox()
        self._tpl_combo.currentTextChanged.connect(self._on_template_changed)
        self._save_btn = QPushButton("保存")
        self._save_btn.clicked.connect(self.save)
        top = QHBoxLayout()
        top.addWidget(QLabel("模板:")); top.addWidget(self._tpl_combo, 1)
        top.addWidget(self._save_btn)

        # 编辑器 + 右上角浮动按钮（在 Task 6 加按钮，本任务先放编辑器）
        self._editor = CodeEditor()
        self._editor.textChanged.connect(self._on_text_changed)

        # 底部：进度 + 日志
        self._bar = QProgressBar(); self._bar.setRange(0, 100); self._bar.setValue(0)
        self._stage = QLabel("就绪")
        self._log = LogView()

        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self._editor, 1)
        lay.addWidget(self._stage)
        lay.addWidget(self._bar)
        lay.addWidget(self._log, 1)

    # --- profile ---
    def set_profile(self, profile) -> None:
        self._profile = profile
        self._slot = 0
        self._reload_templates()

    def _reload_templates(self):
        self._tpl_combo.blockSignals(True)
        self._tpl_combo.clear()
        self._tpl_combo.addItem(_BLANK)
        tdir = getattr(self._profile, "templates_dir", None)
        if tdir and Path(tdir).is_dir():
            for f in sorted(Path(tdir).glob("*.py")):
                self._tpl_combo.addItem(f.name)
        self._tpl_combo.blockSignals(False)

    # --- 模板加载 ---
    def select_template(self, name: str) -> None:
        idx = self._tpl_combo.findText(name)
        if idx >= 0:
            self._tpl_combo.setCurrentIndex(idx)
            self._on_template_changed(name)  # 显式触发（setCurrentIndex 相同项不发信号）

    def _on_template_changed(self, name: str):
        if name == _BLANK or not name:
            self._editor.set_text("")
        else:
            tdir = Path(self._profile.templates_dir)
            content = (tdir / name).read_text(encoding="utf-8")
            self._editor.set_text(content)
        self._mark_clean()

    # --- dirty 追踪 ---
    def _on_text_changed(self):
        self._mark_dirty()

    def _mark_dirty(self):
        self._dirty = True
        self._save_btn.setStyleSheet("QPushButton { border: 1px solid %s; }" % _accent())

    def _mark_clean(self):
        self._dirty = False
        self._save_btn.setStyleSheet("")

    def is_dirty(self) -> bool:
        return self._dirty

    # --- 槽位 ---
    def _set_slot(self, slot: int) -> None:
        self._slot = slot

    def current_slot(self) -> int:
        return self._slot

    # --- 保存 ---
    def _write_dir(self) -> Path:
        return next(iter(self._profile.script_dirs))  # script_dirs 的 key 是 write 目录

    def save(self) -> bool:
        if self._profile is None:
            return False
        try:
            wd = self._write_dir()
            Path(wd).mkdir(parents=True, exist_ok=True)
            path = Path(wd) / f"{self._slot}.py"
            path.write_text(self._editor.text(), encoding="utf-8")
            self._mark_clean()
            self._log.append(f"已保存 {self._slot}.py", level="success")
            return True
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {e}")
            return False

    # --- 测试访问器 ---
    def template_names(self) -> list[str]:
        return [self._tpl_combo.itemText(i) for i in range(self._tpl_combo.count())]

    def editor_text(self) -> str:
        return self._editor.text()

    def log_text(self) -> str:
        return self._log.plain_text()


def _accent() -> str:
    from .. import theme
    return theme.ACCENT
