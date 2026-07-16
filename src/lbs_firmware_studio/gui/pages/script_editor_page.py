"""脚本编辑器页：模板下拉 + 代码编辑器（右上角浮槽位/下发按钮）+ 进度 + 日志。
单页闭环：选模板→编辑→保存(<slot>.py)→选槽→下发。GUI 只做界面，下发经 worker。"""
from __future__ import annotations
from pathlib import Path
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QComboBox, QProgressBar, QMessageBox,
                               QMenu, QFileDialog)
from PySide6.QtCore import Signal
import qtawesome as qta
from .. import theme
from ..widgets.code_editor import CodeEditor
from ..widgets.log_view import LogView

_BLANK = "(空白)"


class ScriptEditorPage(QWidget):
    deploy_requested = Signal(Path, int)   # (write目录/<slot>.py, slot)
    run_toggle_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._profile = None
        self._slot = 0
        self._dirty = False
        self._port_getter = lambda: None

        # 顶部：模板下拉 + 打开 + 保存
        self._tpl_combo = QComboBox()
        self._tpl_combo.currentTextChanged.connect(self._on_template_changed)
        self._open_btn = QPushButton("打开…")
        self._open_btn.clicked.connect(self._on_open)
        self._save_btn = QPushButton("保存")
        self._save_btn.clicked.connect(self.save)
        top = QHBoxLayout()
        top.addWidget(QLabel("模板:")); top.addWidget(self._tpl_combo, 1)
        top.addWidget(self._open_btn)
        top.addWidget(self._save_btn)

        # 编辑器 + 右上角浮动按钮
        self._editor = CodeEditor()
        self._editor.textChanged.connect(self._on_text_changed)

        self._slot_btn = QPushButton("槽位 0", self._editor)
        self._slot_btn.setObjectName("floatbtn")
        self._slot_btn.clicked.connect(self._open_slot_menu)
        self._deploy_btn = QPushButton(self._editor)
        self._deploy_btn.setObjectName("floatbtn")
        self._deploy_btn.setIcon(qta.icon("fa5s.upload", color=theme.TEXT_ON_ACCENT))
        self._deploy_btn.setToolTip("下发到设备")
        self._deploy_btn.clicked.connect(self._on_deploy)

        # 运行按钮
        self._run_btn = QPushButton(self._editor)
        self._run_btn.setObjectName("floatbtn")
        self._run_btn.setIcon(qta.icon("fa5s.play", color=theme.ACCENT))
        self._run_btn.setToolTip("运行程序")
        self._run_btn.clicked.connect(self._on_run_toggle)
        self._run_btn.setEnabled(False)

        # 暂停按钮
        self._pause_btn = QPushButton(self._editor)
        self._pause_btn.setObjectName("floatbtn")
        self._pause_btn.setIcon(qta.icon("fa5s.stop", color=theme.WARNING))
        self._pause_btn.setToolTip("暂停程序")
        self._pause_btn.clicked.connect(self._on_run_toggle)
        self._pause_btn.setEnabled(False)

        for b in (self._run_btn, self._pause_btn, self._slot_btn, self._deploy_btn):
            b.setFixedHeight(32)
            b.setStyleSheet(
                f"QPushButton#floatbtn {{ background: {theme.BG_INPUT}; color: {theme.TEXT_PRIMARY};"
                f" border: 1px solid {theme.BORDER}; border-radius: 16px; padding: 4px 12px; }}"
                f"QPushButton#floatbtn:hover {{ background: {theme.BG_HOVER}; }}"
                f"QPushButton#floatbtn:pressed {{ background: {theme.BG_SELECTED}; }}")
        self._running = False
        self._busy = False
        self._editor.installEventFilter(self)

        # 底部：进度 + 日志（日志固定矮条，编辑器占绝大部分空间）
        self._bar = QProgressBar(); self._bar.setRange(0, 100); self._bar.setValue(0)
        self._stage = QLabel("就绪")
        self._log = LogView()
        self._log.setMinimumHeight(80)
        self._log.setMaximumHeight(140)

        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self._editor, 1)   # 唯一可伸缩
        lay.addWidget(self._stage)
        lay.addWidget(self._bar)
        lay.addWidget(self._log)         # stretch=0，固定矮

    # --- profile ---
    def set_profile(self, profile) -> None:
        self._profile = profile
        self._slot = 0
        self._reload_templates()
        self._set_slot(0)

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

    # --- 打开任意 .py ---
    def _default_open_dir(self) -> str:
        if self._profile is not None:
            try:
                return str(next(iter(self._profile.script_dirs)))
            except (StopIteration, AttributeError, TypeError):
                pass
        return str(Path.home())

    def _on_open(self):
        fn, _ = QFileDialog.getOpenFileName(
            self, "打开脚本", self._default_open_dir(), "Python (*.py)")
        if fn:
            self.load_file(fn)

    def load_file(self, path: str) -> bool:
        """读文件 → 灌编辑器 → mark_clean → 日志。纯逻辑，不弹对话框（供测试直接调）。"""
        try:
            content = Path(path).read_text(encoding="utf-8")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开失败: {e}")
            return False
        self._editor.set_text(content)
        self._mark_clean()
        self._log.append(f"已打开 {Path(path).name}", level="success")
        return True

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
        self._slot_btn.setText(f"槽位 {slot}")

    def current_slot(self) -> int:
        return self._slot

    def slot_menu_values(self) -> list[int]:
        max_slot = getattr(self._profile, "max_slot", 0) if self._profile else 0
        return list(range(0, max_slot + 1))

    def _open_slot_menu(self):
        menu = QMenu(self)
        for s in self.slot_menu_values():
            act = menu.addAction(str(s))
            act.triggered.connect(lambda _=False, v=s: self._set_slot(v))
        menu.exec(self._slot_btn.mapToGlobal(self._slot_btn.rect().bottomLeft()))

    # --- 浮动按钮定位 ---
    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj is self._editor and event.type() == QEvent.Resize:
            self._reposition_float_buttons()
        return super().eventFilter(obj, event)

    def _reposition_float_buttons(self):
        margin = 8
        w = self._editor.width()
        self._deploy_btn.adjustSize()
        self._slot_btn.adjustSize()
        self._pause_btn.adjustSize()
        self._run_btn.adjustSize()
        dx = w - margin - self._deploy_btn.width()
        self._deploy_btn.move(dx, margin)
        self._slot_btn.move(dx - self._slot_btn.width() - 8, margin)
        self._pause_btn.move(dx - self._slot_btn.width() - self._pause_btn.width() - 16, margin)
        self._run_btn.move(dx - self._slot_btn.width() - self._pause_btn.width() - self._run_btn.width() - 24, margin)

    # --- 下发 ---
    def set_port_getter(self, fn) -> None:
        self._port_getter = fn

    def _on_deploy(self):
        if self._profile is None:
            return
        if not self._port_getter():
            QMessageBox.warning(self, "提示", "未选择串口"); return
        if not self._editor.text().strip():
            QMessageBox.warning(self, "提示", "脚本内容为空"); return
        if self._dirty:
            QMessageBox.warning(self, "提示", "有未保存的改动，请先保存"); return
        path = Path(self._write_dir()) / f"{self._slot}.py"
        if not path.exists():
            QMessageBox.warning(self, "提示", "当前槽位尚未保存，请先保存"); return
        self.deploy_requested.emit(path, self._slot)

    def _on_run_toggle(self):
        """点击运行/暂停按钮：emit 信号让 MainWindow 发 0xB6 命令，乐观更新 UI。"""
        self._running = not self._running
        self._apply_run_state()
        self.run_toggle_requested.emit()

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

    # --- 进度/状态/日志回调（与固件页同构）---
    def on_progress(self, done: int, total: int) -> None:
        pct = int(done * 100 / total) if total else 0
        self._bar.setValue(pct)

    def on_state(self, state: str) -> None:
        self._stage.setText(theme.STAGE_TEXT.get(state, state))

    def on_log(self, msg: str) -> None:
        level = "error" if ("失败" in msg or "错误" in msg) else "info"
        self._log.append(msg, level=level)

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._deploy_btn.setEnabled(not busy)
        self._save_btn.setEnabled(not busy)
        self._open_btn.setEnabled(not busy)
        self._slot_btn.setEnabled(not busy)
        self._tpl_combo.setEnabled(not busy)
        if busy:
            self._run_btn.setEnabled(False)
            self._pause_btn.setEnabled(False)
        else:
            self._apply_run_state()

    def on_host_state_changed(self, state: str) -> None:
        """接收监控帧确认的运行状态，以帧值为准。"""
        if state == "start":
            self._running = True
        elif state == "stop":
            self._running = False
        else:
            self._running = False   # 未知/空 → 禁用两按钮
        self._apply_run_state()

    def _apply_run_state(self) -> None:
        """根据 _running 和 _busy 更新运行/暂停按钮启用态。"""
        if self._busy:
            self._run_btn.setEnabled(False)
            self._pause_btn.setEnabled(False)
        elif self._running:
            self._run_btn.setEnabled(False)
            self._pause_btn.setEnabled(True)
        else:
            self._run_btn.setEnabled(True)
            self._pause_btn.setEnabled(False)

    def progress_value(self) -> int:
        return self._bar.value()

    def stage_text(self) -> str:
        return self._stage.text()

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
