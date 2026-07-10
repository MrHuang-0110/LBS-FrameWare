# 脚本编辑器 + 脚本下发 + 槽位选择 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在「代码编辑」页做一个 Python 脚本编辑器单页闭环——选模板→编辑→保存→选槽→下发，复用已就绪的后端 `deploy_script()` 与 `DeployWorker`。

**Architecture:** 新增自制编辑器控件 `CodeEditor`（QPlainTextEdit + 行号 + Python 高亮 + Tab 缩进）；新增页面 `ScriptEditorPage`（模板下拉 + 编辑器 + 编辑器内部右上角两个圆形按钮选槽/下发 + 进度 + 日志）；后端 `DeviceProfile` 加 `max_slot`/`templates_dir`；`DeployWorker` 加 `run_script` 槽；`MainWindow` 隐藏 scripts 导航项、启用 editor 项并接线。GUI 只做界面，下发经 worker 调后端，不碰协议。

**Tech Stack:** Python 3.13、PySide6 6.11.1、qtawesome、pytest-qt。Windows，解释器用 `python`。

## Global Constraints

- Python 3.13；Windows；解释器一律用 `python`（非 python3）。
- GUI 层只做界面，所有设备操作经 `DeployWorker` 调 `DeviceDeployer`，不直接碰协议/串口写。
- 后端信号签名固定：`progress(int, int)`、`log(str)`、`state_changed(str)`、`error(str)`。
- 深色主题：颜色/圆角一律取 `theme.*` 常量，禁止硬编码色值（圆形按钮圆角为特例）。
- state→颜色/文字映射沿用固件页：idle/compiling/connecting/entering_upgrade/reconnecting/transfering/done/error。
- 编辑器基于 `QPlainTextEdit` 自实现（QScintilla 绑定 PyQt，与 PySide6 不兼容，不用）。
- 测试用 pytest-qt + 手动 emit / qtbot 真实事件，**不碰真串口**；GUI 测试按文件单独跑，容忍多 QThread 同进程 teardown 段错误（以断言结果为准）。
- Qt 事件处理器中先 `super()` 再 `emit`（避免 use-after-delete）。
- 保存目录 = `profile.script_dirs` 的 **key**（write 目录）；保存文件名 `<slot>.py`。
- `templates_dir` 推导 = `firmware_dir.parent / "templates"`（即 `./products/<产品名>/templates`）。
- max_slot：NEW-AI=19、SPARK-AI=9、NEXT-AI=0。

---

## File Structure

- Create `src/lbs_firmware_studio/gui/widgets/code_editor.py` — `CodeEditor` + `PythonHighlighter`（纯 UI 控件）。
- Create `src/lbs_firmware_studio/gui/pages/script_editor_page.py` — `ScriptEditorPage`（页面，界面 + 校验，不碰协议）。
- Modify `src/lbs_firmware_studio/backend/profile.py` — 加 `max_slot`、`templates_dir` 字段 + load 推导。
- Modify `products.yaml` — 三产品加 `max_slot`。
- Modify `src/lbs_firmware_studio/gui/worker.py` — 加 `run_script` 槽 + `set_job` 扩展。
- Modify `src/lbs_firmware_studio/gui/main_window.py` — 隐藏 scripts 项、启用 editor 项、接 `ScriptEditorPage`、脚本下发接线。
- Create `tests/gui/test_code_editor.py`、`tests/gui/test_script_editor_page.py`。
- Modify `tests/test_profile.py`（max_slot/templates_dir）、`tests/test_worker.py`（run_script）、`tests/gui/test_main_window.py`（导航项变更）。

---

## Task 1: DeviceProfile 加 max_slot + templates_dir

**Files:**
- Modify: `src/lbs_firmware_studio/backend/profile.py`
- Modify: `products.yaml`
- Test: `tests/test_profile.py`

**Interfaces:**
- Produces: `DeviceProfile.max_slot: int`（默认 0）、`DeviceProfile.templates_dir: Path`（load 时推导 `firmware_dir.parent / "templates"`，直接构造 DeviceProfile 未显式给时默认 `Path("./templates")`）。

- [ ] **Step 1: 写失败测试**

在 `tests/test_profile.py` 末尾追加：

```python
def test_max_slot_and_templates_dir(tmp_path):
    import textwrap as _tw
    from pathlib import Path
    yaml_text = _tw.dedent("""
        compiler_path: ./tools/rust-msc-latest-win10.exe
        products:
          NEW-AI:
            protocol: custom_frame
            firmware_dir: ./products/NEW-AI/fwlib
            max_slot: 19
          NEXT-AI:
            protocol: ymodem
            firmware_dir: ./products/NEXT-AI/fwlib
    """)
    p = tmp_path / "products.yaml"; p.write_text(yaml_text)
    profiles = load_profiles(p)
    assert profiles["NEW-AI"].max_slot == 19
    assert profiles["NEXT-AI"].max_slot == 0   # 未配置默认 0
    # templates_dir 推导为 firmware_dir 的父目录下的 templates
    assert profiles["NEW-AI"].templates_dir == Path("./products/NEW-AI") / "templates"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_profile.py::test_max_slot_and_templates_dir -q`
Expected: FAIL（`AttributeError: 'DeviceProfile' object has no attribute 'max_slot'`）

- [ ] **Step 3: 加字段与推导**

在 `src/lbs_firmware_studio/backend/profile.py` 的 `DeviceProfile` 数据类字段区（`display_ports` 之后）加：

```python
    max_slot: int = 0                       # 脚本槽位上限（0..max_slot），按产品配置
    templates_dir: Path = Path("./templates")  # 预加载模板目录，load 时按产品根推导
```

在 `load_profiles` 的 `DeviceProfile(...)` 构造里（`display_ports=...` 之后）加两行：

```python
            max_slot=cfg.get("max_slot", 0),
            templates_dir=Path(cfg.get("firmware_dir", ".")).parent / "templates",
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_profile.py -q`
Expected: PASS（全部，含原有用例）

- [ ] **Step 5: products.yaml 加 max_slot**

在 `products.yaml` 对应产品下加（缩进对齐同级键）：
- NEW-AI 块内加一行：`    max_slot: 19`
- SPARK-AI 块内加一行：`    max_slot: 9`
- NEXT-AI 块内加一行：`    max_slot: 0`

- [ ] **Step 6: 冒烟验证 yaml 加载**

Run: `python -c "from pathlib import Path; from lbs_firmware_studio.backend.profile import load_profiles; p=load_profiles(Path('products.yaml')); print(p['NEW-AI'].max_slot, p['SPARK-AI'].max_slot, p['NEXT-AI'].max_slot, p['NEW-AI'].templates_dir)"`
Expected: `19 9 0 products\NEW-AI\templates`（templates 路径分隔符随平台）

- [ ] **Step 7: Commit**

```bash
git add src/lbs_firmware_studio/backend/profile.py products.yaml tests/test_profile.py
git commit -m "feat(backend): add max_slot + templates_dir to DeviceProfile"
```

---

## Task 2: CodeEditor 控件（行号 + Tab 缩进）

**Files:**
- Create: `src/lbs_firmware_studio/gui/widgets/code_editor.py`
- Test: `tests/gui/test_code_editor.py`

**Interfaces:**
- Produces: `CodeEditor(QPlainTextEdit)`，方法 `line_number_area_width() -> int`（随行数增长）、`set_text(str)`、`text() -> str`；Tab 键插入 4 个空格。（高亮器在 Task 3 加，本任务先不接。）

- [ ] **Step 1: 写失败测试**

Create `tests/gui/test_code_editor.py`：

```python
from lbs_firmware_studio.gui.widgets.code_editor import CodeEditor
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QKeyEvent
from PySide6.QtCore import QEvent


def test_line_number_width_grows_with_lines(qtbot):
    ed = CodeEditor(); qtbot.addWidget(ed)
    w1 = ed.line_number_area_width()
    ed.set_text("\n".join(f"line {i}" for i in range(200)))
    w2 = ed.line_number_area_width()
    assert w2 > w1  # 3 位行号比 1 位宽


def test_tab_inserts_spaces(qtbot):
    ed = CodeEditor(); qtbot.addWidget(ed)
    ed.set_text("")
    ev = QKeyEvent(QEvent.KeyPress, Qt.Key_Tab, Qt.NoModifier)
    ed.keyPressEvent(ev)
    assert ed.text() == "    "  # 4 空格，不是制表符


def test_set_get_text_roundtrip(qtbot):
    ed = CodeEditor(); qtbot.addWidget(ed)
    ed.set_text("import time\nx = 1\n")
    assert ed.text() == "import time\nx = 1\n"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/gui/test_code_editor.py -q`
Expected: FAIL（`ModuleNotFoundError` 或 `ImportError: cannot import name 'CodeEditor'`）

- [ ] **Step 3: 实现 CodeEditor（不含高亮）**

Create `src/lbs_firmware_studio/gui/widgets/code_editor.py`：

```python
"""自制代码编辑器：QPlainTextEdit + 行号边栏 + 当前行高亮 + Tab→4 空格。

QScintilla 绑定 PyQt 与 PySide6 不兼容，故基于 QPlainTextEdit 自实现。
Python 语法高亮由本模块的 PythonHighlighter 提供（Task 3 接入）。
"""
from __future__ import annotations
from PySide6.QtWidgets import QPlainTextEdit, QWidget, QTextEdit
from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QColor, QPainter, QTextFormat
from .. import theme

_INDENT = "    "  # 4 空格


class _LineNumberArea(QWidget):
    def __init__(self, editor: "CodeEditor"):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self._editor.paint_line_numbers(event)


class CodeEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lna = _LineNumberArea(self)
        self.blockCountChanged.connect(self._update_lna_width)
        self.updateRequest.connect(self._update_lna)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self._update_lna_width(0)
        self._highlight_current_line()

    # --- 行号 ---
    def line_number_area_width(self) -> int:
        digits = max(1, len(str(self.blockCount())))
        return 12 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_lna_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_lna(self, rect, dy):
        if dy:
            self._lna.scroll(0, dy)
        else:
            self._lna.update(0, rect.y(), self._lna.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_lna_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._lna.setGeometry(QRect(cr.left(), cr.top(),
                                    self.line_number_area_width(), cr.height()))

    def paint_line_numbers(self, event):
        painter = QPainter(self._lna)
        painter.fillRect(event.rect(), QColor(theme.BG_SIDEBAR))
        block = self.firstVisibleBlock()
        num = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        painter.setPen(QColor(theme.TEXT_DISABLED))
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.drawText(0, top, self._lna.width() - 4,
                                 self.fontMetrics().height(),
                                 Qt.AlignRight, str(num + 1))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            num += 1

    # --- 当前行高亮 ---
    def _highlight_current_line(self):
        sel = QTextEdit.ExtraSelection()
        sel.format.setBackground(QColor(theme.BG_HOVER))
        sel.format.setProperty(QTextFormat.FullWidthSelection, True)
        sel.cursor = self.textCursor()
        sel.cursor.clearSelection()
        self.setExtraSelections([sel])

    # --- Tab → 空格 ---
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Tab:
            self.insertPlainText(_INDENT)
            return
        super().keyPressEvent(event)

    # --- 便捷读写 ---
    def set_text(self, text: str) -> None:
        self.setPlainText(text)

    def text(self) -> str:
        return self.toPlainText()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/gui/test_code_editor.py -q`
Expected: PASS（3 个）

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/gui/widgets/code_editor.py tests/gui/test_code_editor.py
git commit -m "feat(gui): CodeEditor widget with line numbers + tab indent"
```

---

## Task 3: PythonHighlighter 语法高亮

**Files:**
- Modify: `src/lbs_firmware_studio/gui/widgets/code_editor.py`
- Test: `tests/gui/test_code_editor.py`

**Interfaces:**
- Consumes: `CodeEditor`（Task 2）。
- Produces: `PythonHighlighter(QSyntaxHighlighter)`；`CodeEditor.__init__` 内实例化并绑定到 document。方法 `formats_at(block_text, index) -> QTextCharFormat | None` 不提供——测试改用高亮后计算的格式区间断言（见下）。

- [ ] **Step 1: 写失败测试**

在 `tests/gui/test_code_editor.py` 末尾追加：

```python
def _has_colored_run(ed):
    # 高亮器把格式写进 document 的 layout additionalFormats；
    # 断言首个 block 至少有一段非默认前景色（即高亮生效）。
    block = ed.document().firstBlock()
    fmts = block.layout().formats() if block.layout() else []
    return any(f.format.foreground().color().name() != "#000000" for f in fmts) or bool(fmts)


def test_highlighter_colors_keywords(qtbot):
    ed = CodeEditor(); qtbot.addWidget(ed)
    ed.set_text("import time  # comment")
    # 触发一次布局
    ed.document().firstBlock().layout()
    assert _has_colored_run(ed)


def test_highlighter_instance_attached(qtbot):
    from lbs_firmware_studio.gui.widgets.code_editor import PythonHighlighter
    ed = CodeEditor(); qtbot.addWidget(ed)
    assert isinstance(ed._highlighter, PythonHighlighter)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/gui/test_code_editor.py::test_highlighter_instance_attached -q`
Expected: FAIL（`AttributeError: 'CodeEditor' object has no attribute '_highlighter'`）

- [ ] **Step 3: 实现高亮器并接入**

在 `code_editor.py` 顶部 import 增补：

```python
from PySide6.QtGui import QColor, QPainter, QTextFormat, QSyntaxHighlighter, QTextCharFormat, QFont
import re
import keyword
```

在文件末尾（`CodeEditor` 类之后）加高亮器类：

```python
def _fmt(color: str, *, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.Bold)
    if italic:
        f.setFontItalic(True)
    return f


class PythonHighlighter(QSyntaxHighlighter):
    """Python 语法高亮：关键字/字符串/注释/数字/装饰器，配色取 theme.*。"""

    def __init__(self, document):
        super().__init__(document)
        kw = _fmt(theme.ACCENT, bold=True)
        self._rules = []
        for word in keyword.kwlist:
            self._rules.append((re.compile(rf"\b{word}\b"), kw))
        self._rules.append((re.compile(r"@\w+"), _fmt(theme.WARNING)))          # 装饰器
        self._rules.append((re.compile(r"\b[0-9]+\.?[0-9]*\b"), _fmt(theme.WARNING)))  # 数字
        self._str_fmt = _fmt(theme.SUCCESS)
        self._comment_fmt = _fmt(theme.TEXT_DISABLED, italic=True)

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in self._rules:
            for m in pattern.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)
        # 字符串（单/双引号，简单单行匹配）
        for m in re.finditer(r"('[^']*'|\"[^\"]*\")", text):
            self.setFormat(m.start(), m.end() - m.start(), self._str_fmt)
        # 注释（# 到行尾），放最后覆盖前面的匹配
        hash_idx = text.find("#")
        if hash_idx >= 0:
            self.setFormat(hash_idx, len(text) - hash_idx, self._comment_fmt)
```

在 `CodeEditor.__init__` 末尾（`self._highlight_current_line()` 之前）加：

```python
        self._highlighter = PythonHighlighter(self.document())
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/gui/test_code_editor.py -q`
Expected: PASS（5 个）

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/gui/widgets/code_editor.py tests/gui/test_code_editor.py
git commit -m "feat(gui): Python syntax highlighter for CodeEditor"
```

---

## Task 4: DeployWorker 加 run_script 槽

**Files:**
- Modify: `src/lbs_firmware_studio/gui/worker.py`
- Test: `tests/test_worker.py`

**Interfaces:**
- Consumes: `DeviceDeployer.deploy_script(profile, port, py_path: Path, slot: int)`（已存在）。
- Produces: `DeployWorker.set_job(profile, port, py_path=None, slot=0)`（扩展签名，向后兼容旧调用）；`DeployWorker.run_script()`（@Slot，子线程执行 open→start_rx→deploy_script→close→finished）。

- [ ] **Step 1: 写失败测试**

在 `tests/test_worker.py` 末尾追加（复用文件已有的 imports 与 `_profile`）：

```python
def test_worker_runs_script_and_emits_finished(qtbot, monkeypatch):
    host_ser, dev_ser = make_fake_serial_pair()
    sim = DeviceSimulator(dev_ser, protocol="custom_frame"); sim.start()
    t = SerialTransport(host_ser); t.start_rx()
    try:
        with tempfile.TemporaryDirectory() as d:
            py = pathlib.Path(d) / "0.py"; py.write_text("x = 1\n")
            dep = DeviceDeployer(t)
            # mock 编译：把 <slot>.o 造出来，避免调真编译器
            def fake_compile(profile, py_path, slot):
                out = pathlib.Path(d) / f"{slot}.o"
                out.write_bytes(b"script bytecode")
                return out
            dep._compile_to_slot = fake_compile
            worker = DeployWorker(t, dep)
            states = []
            dep.state_changed.connect(lambda s: states.append(s))
            with qtbot.waitSignal(worker.finished, timeout=5000):
                worker.set_job(_profile(d), "COM_FAKE", py_path=py, slot=0)
                worker.run_script()
            assert "done" in states
            assert sim.received_files.get("0.o") == b"script bytecode"
    finally:
        t.stop_rx(); sim.stop()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_worker.py::test_worker_runs_script_and_emits_finished -q`
Expected: FAIL（`TypeError: set_job() got an unexpected keyword argument 'py_path'` 或 `AttributeError: run_script`）

- [ ] **Step 3: 扩展 worker**

在 `src/lbs_firmware_studio/gui/worker.py`：

`__init__` 里 `self._port = None` 之后加：

```python
        self._py_path = None
        self._slot = 0
```

替换 `set_job`：

```python
    def set_job(self, profile, port: str, py_path=None, slot: int = 0) -> None:
        """预存本次任务参数。固件更新只需 profile/port；脚本下发另带 py_path/slot。"""
        self._profile = profile
        self._port = port
        self._py_path = py_path
        self._slot = slot
```

在 `run_firmware` 之后加对称的 `run_script`：

```python
    @Slot()
    def run_script(self) -> None:
        profile, port = self._profile, self._port
        try:
            self._transport.open(port, profile.baud)
            self._transport.start_rx()
            self._deployer.deploy_script(profile, port, self._py_path, self._slot)
        except Exception as e:
            try:
                self._deployer.error.emit(f"打开串口失败: {e}")
                self._deployer.state_changed.emit("error")
            except Exception:
                pass
        finally:
            try:
                self._transport.close()
            except Exception:
                pass
            self.finished.emit()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_worker.py -q`
Expected: PASS（含原有固件用例，验证 set_job 向后兼容）

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/gui/worker.py tests/test_worker.py
git commit -m "feat(gui): DeployWorker.run_script slot + set_job py_path/slot"
```

---

## Task 5: ScriptEditorPage 骨架（模板下拉 + 编辑器 + 保存）

**Files:**
- Create: `src/lbs_firmware_studio/gui/pages/script_editor_page.py`
- Test: `tests/gui/test_script_editor_page.py`

**Interfaces:**
- Consumes: `CodeEditor`（Task 2/3）、`LogView`、`theme`、`DeviceProfile`（含 `templates_dir`、`script_dirs`、`max_slot`）。
- Produces: `ScriptEditorPage(QWidget)`，信号 `deploy_requested(Path, int)`（下发时发 write 目录下 `<slot>.py` 路径 + slot）；方法 `set_profile(profile)`、`current_slot() -> int`、`is_dirty() -> bool`、`save() -> bool`、测试访问器 `template_names() -> list[str]`、`editor_text() -> str`、`log_text() -> str`。本任务先做模板/编辑/保存；槽位按钮与下发在 Task 6。

- [ ] **Step 1: 写失败测试**

Create `tests/gui/test_script_editor_page.py`：

```python
from pathlib import Path
from lbs_firmware_studio.gui.pages.script_editor_page import ScriptEditorPage
from lbs_firmware_studio.backend.profile import DeviceProfile


def _profile(tmp_path):
    tpl = tmp_path / "templates"; tpl.mkdir()
    (tpl / "blink.py").write_text("led.on()\n", encoding="utf-8")
    write = tmp_path / "write"; write.mkdir()
    return DeviceProfile(name="NEW-AI", protocol="custom_frame",
                         script_dirs={write: tmp_path / "app"},
                         templates_dir=tpl, max_slot=19)


def test_templates_listed(qtbot, tmp_path):
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    names = page.template_names()
    assert "(空白)" == names[0]
    assert "blink.py" in names


def test_select_template_loads_content(qtbot, tmp_path):
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    page.select_template("blink.py")
    assert page.editor_text() == "led.on()\n"
    assert page.is_dirty() is False   # 加载后为 clean


def test_select_blank_clears(qtbot, tmp_path):
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    page.select_template("blink.py")
    page.select_template("(空白)")
    assert page.editor_text() == ""


def test_edit_marks_dirty(qtbot, tmp_path):
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    page._editor.set_text("changed")
    assert page.is_dirty() is True


def test_save_writes_slot_py(qtbot, tmp_path):
    prof = _profile(tmp_path)
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(prof)
    page._editor.set_text("y = 2\n")
    page._set_slot(3)
    assert page.save() is True
    write_dir = next(iter(prof.script_dirs))   # key 是 write 目录
    saved = write_dir / "3.py"
    assert saved.read_text(encoding="utf-8") == "y = 2\n"
    assert page.is_dirty() is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/gui/test_script_editor_page.py -q`
Expected: FAIL（`ImportError: cannot import name 'ScriptEditorPage'`）

- [ ] **Step 3: 实现页面骨架**

Create `src/lbs_firmware_studio/gui/pages/script_editor_page.py`：

```python
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/gui/test_script_editor_page.py -q`
Expected: PASS（5 个）

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/gui/pages/script_editor_page.py tests/gui/test_script_editor_page.py
git commit -m "feat(gui): ScriptEditorPage skeleton (templates + editor + save)"
```

---

## Task 6: 槽位/下发圆形按钮 + 下发校验

**Files:**
- Modify: `src/lbs_firmware_studio/gui/pages/script_editor_page.py`
- Test: `tests/gui/test_script_editor_page.py`

**Interfaces:**
- Consumes: `ScriptEditorPage`（Task 5）、`deploy_requested` 信号。
- Produces: 两个浮动圆形按钮 `_slot_btn`、`_deploy_btn`（编辑器内部右上角）；`slot_menu_values() -> list[int]`（0..max_slot）；下发校验方法 `_on_deploy()`（未选串口/空内容/未保存→拦截提示；通过→emit deploy_requested）。串口有无由外部注入的回调 `set_port_getter(fn)` 提供。

- [ ] **Step 1: 写失败测试**

在 `tests/gui/test_script_editor_page.py` 末尾追加：

```python
from PySide6.QtCore import Qt


def test_slot_menu_range_follows_max_slot(qtbot, tmp_path):
    prof = _profile(tmp_path)   # max_slot=19
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(prof)
    assert page.slot_menu_values() == list(range(0, 20))


def test_slot_menu_single_when_max_slot_zero(qtbot, tmp_path):
    prof = _profile(tmp_path); prof.max_slot = 0
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(prof)
    assert page.slot_menu_values() == [0]


def test_deploy_blocked_when_no_port(qtbot, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    page.set_port_getter(lambda: None)   # 无串口
    page._editor.set_text("z = 3\n"); page.save()
    fired = []
    page.deploy_requested.connect(lambda p, s: fired.append((p, s)))
    page._on_deploy()
    assert fired == []   # 被拦截，未发下发信号


def test_deploy_blocked_when_dirty(qtbot, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    page.set_port_getter(lambda: "COM3")
    page._editor.set_text("dirty content")   # 未保存
    fired = []
    page.deploy_requested.connect(lambda p, s: fired.append((p, s)))
    page._on_deploy()
    assert fired == []   # 未保存被拦截


def test_deploy_emits_when_valid(qtbot, tmp_path, monkeypatch):
    prof = _profile(tmp_path)
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(prof)
    page.set_port_getter(lambda: "COM3")
    page._set_slot(2)
    page._editor.set_text("w = 4\n"); page.save()
    fired = []
    page.deploy_requested.connect(lambda p, s: fired.append((p, s)))
    page._on_deploy()
    write_dir = next(iter(prof.script_dirs))
    assert fired == [(write_dir / "2.py", 2)]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/gui/test_script_editor_page.py::test_slot_menu_range_follows_max_slot -q`
Expected: FAIL（`AttributeError: 'ScriptEditorPage' object has no attribute 'slot_menu_values'`）

- [ ] **Step 3: 加浮动按钮 + 校验**

在 `script_editor_page.py` 的 import 增补 qtawesome 与 theme：

```python
import qtawesome as qta
from .. import theme
```

`__init__` 里 `self._dirty = False` 之后加：

```python
        self._port_getter = lambda: None
```

`__init__` 里创建 `self._editor` 之后、加入布局之前，加两个浮动按钮（以编辑器为父，绝对定位）：

```python
        self._slot_btn = QPushButton("槽位 0", self._editor)
        self._slot_btn.setObjectName("floatbtn")
        self._slot_btn.clicked.connect(self._open_slot_menu)
        self._deploy_btn = QPushButton(self._editor)
        self._deploy_btn.setObjectName("floatbtn")
        self._deploy_btn.setIcon(qta.icon("fa5s.upload", color=theme.TEXT_ON_ACCENT))
        self._deploy_btn.setToolTip("下发到设备")
        self._deploy_btn.clicked.connect(self._on_deploy)
        for b in (self._slot_btn, self._deploy_btn):
            b.setFixedHeight(32)
            b.setStyleSheet(
                f"QPushButton#floatbtn {{ background: {theme.BG_INPUT}; color: {theme.TEXT_PRIMARY};"
                f" border: 1px solid {theme.BORDER}; border-radius: 16px; padding: 4px 12px; }}"
                f"QPushButton#floatbtn:hover {{ background: {theme.BG_HOVER}; }}"
                f"QPushButton#floatbtn:pressed {{ background: {theme.BG_SELECTED}; }}")
        self._editor.installEventFilter(self)
```

加 resize 时重定位按钮的事件过滤器（放到类方法区）：

```python
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
        dx = w - margin - self._deploy_btn.width()
        self._deploy_btn.move(dx, margin)
        self._slot_btn.move(dx - self._slot_btn.width() - 8, margin)
```

加槽位菜单与设置：

```python
    def slot_menu_values(self) -> list[int]:
        max_slot = getattr(self._profile, "max_slot", 0) if self._profile else 0
        return list(range(0, max_slot + 1))

    def _open_slot_menu(self):
        menu = QMenu(self)
        for s in self.slot_menu_values():
            act = menu.addAction(str(s))
            act.triggered.connect(lambda _=False, v=s: self._set_slot(v))
        menu.exec(self._slot_btn.mapToGlobal(self._slot_btn.rect().bottomLeft()))
```

改写 `_set_slot` 以更新按钮文字：

```python
    def _set_slot(self, slot: int) -> None:
        self._slot = slot
        self._slot_btn.setText(f"槽位 {slot}")
```

加串口注入与下发校验：

```python
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
        self.deploy_requested.emit(path, self._slot)
```

在 `set_profile` 末尾（`self._reload_templates()` 之后）加，确保槽位按钮文字与初始 slot 同步：

```python
        self._set_slot(0)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/gui/test_script_editor_page.py -q`
Expected: PASS（10 个）

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/gui/pages/script_editor_page.py tests/gui/test_script_editor_page.py
git commit -m "feat(gui): slot/deploy float buttons + deploy validation"
```

---

## Task 7: 页面进度/状态/日志回调

**Files:**
- Modify: `src/lbs_firmware_studio/gui/pages/script_editor_page.py`
- Test: `tests/gui/test_script_editor_page.py`

**Interfaces:**
- Produces: `ScriptEditorPage.on_progress(done, total)`、`on_state(state)`、`on_log(msg)`、`set_busy(busy)`；测试访问器 `stage_text()`、`progress_value()`。与固件页同构。

- [ ] **Step 1: 写失败测试**

在 `tests/gui/test_script_editor_page.py` 末尾追加：

```python
def test_progress_and_state_and_log(qtbot, tmp_path):
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    page.on_progress(50, 100)
    assert page.progress_value() == 50
    page.on_state("transfering")
    assert "传输" in page.stage_text()
    page.on_log("compile 0.py -> 0.o")
    assert "0.o" in page.log_text()


def test_set_busy_disables_controls(qtbot, tmp_path):
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    page.set_busy(True)
    assert page._deploy_btn.isEnabled() is False
    assert page._save_btn.isEnabled() is False
    page.set_busy(False)
    assert page._deploy_btn.isEnabled() is True
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/gui/test_script_editor_page.py::test_progress_and_state_and_log -q`
Expected: FAIL（`AttributeError: 'ScriptEditorPage' object has no attribute 'on_progress'`）

- [ ] **Step 3: 加回调**

在 `script_editor_page.py` 类方法区加：

```python
    def on_progress(self, done: int, total: int) -> None:
        pct = int(done * 100 / total) if total else 0
        self._bar.setValue(pct)

    def on_state(self, state: str) -> None:
        self._stage.setText(_STAGE_TEXT.get(state, state))

    def on_log(self, msg: str) -> None:
        level = "error" if ("失败" in msg or "错误" in msg) else "info"
        self._log.append(msg, level=level)

    def set_busy(self, busy: bool) -> None:
        self._deploy_btn.setEnabled(not busy)
        self._save_btn.setEnabled(not busy)
        self._slot_btn.setEnabled(not busy)
        self._tpl_combo.setEnabled(not busy)

    def progress_value(self) -> int:
        return self._bar.value()

    def stage_text(self) -> str:
        return self._stage.text()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/gui/test_script_editor_page.py -q`
Expected: PASS（12 个）

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/gui/pages/script_editor_page.py tests/gui/test_script_editor_page.py
git commit -m "feat(gui): ScriptEditorPage progress/state/log callbacks + busy lock"
```

---

## Task 8: MainWindow 接线（隐藏 scripts、启用 editor、脚本下发线程）

**Files:**
- Modify: `src/lbs_firmware_studio/gui/main_window.py`
- Test: `tests/gui/test_main_window.py`

**Interfaces:**
- Consumes: `ScriptEditorPage`（Task 5-7）、`DeployWorker.run_script`（Task 4）、`deploy_requested(Path, int)` 信号。
- Produces: `_NAV` 移除 scripts 项；editor 项启用并接 `ScriptEditorPage`；`_start_script(py_path, slot)` 启动脚本下发线程（结构同 `_start_firmware`）。抽出 `_run_deploy(run_slot_name)` 复用接线。

- [ ] **Step 1: 改现有测试（导航项变更）**

`tests/gui/test_main_window.py` 的 `test_nav_items_present_and_locked` 改为：

```python
def test_nav_items_present_and_locked(qtbot, tmp_path):
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    labels = w.nav_labels()
    assert "固件更新" in labels and "代码编辑" in labels and "设置" in labels
    assert "脚本下发" not in labels          # scripts 项已隐藏（合并进代码编辑页）
    assert w.is_nav_enabled("固件更新") is True
    assert w.is_nav_enabled("代码编辑") is True   # editor 现已启用
```

- [ ] **Step 2: 加脚本下发线程测试**

在 `tests/gui/test_main_window.py` 末尾追加：

```python
def test_navigate_to_editor_page(qtbot, tmp_path):
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w.navigate("代码编辑")
    assert w.current_page_name() == "代码编辑"


def test_start_script_no_port_returns_early(qtbot, tmp_path, monkeypatch):
    from pathlib import Path as _P
    from PySide6.QtWidgets import QMessageBox
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(w._port, "selected_port", lambda: None)
    w._start_script(_P("x/0.py"), 0)   # 无串口 -> 提前返回，不进入 busy
    assert w.is_busy() is False
    assert w._thread is None


def test_start_script_reentrancy_guard(qtbot, tmp_path):
    from pathlib import Path as _P
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w._on_state("transfering")   # 模拟忙
    w._start_script(_P("x/0.py"), 0)
    assert w._thread is None      # 忙时不建第二个线程
```

- [ ] **Step 3: 运行测试确认失败**

Run: `python -m pytest tests/gui/test_main_window.py -q`
Expected: FAIL（`脚本下发` 断言变更 + `AttributeError: _start_script`）

- [ ] **Step 4: 改 MainWindow**

在 `src/lbs_firmware_studio/gui/main_window.py`：

顶部 import 增补：

```python
from pathlib import Path
from .pages.script_editor_page import ScriptEditorPage
```

`_NAV` 改为（移除 scripts 行，editor 置 True）：

```python
_NAV = [
    ("firmware", "固件更新", "fa5s.download", True),
    ("editor", "代码编辑", "fa5s.code", True),
    ("monitor", "数据监控", "fa5s.chart-line", False),
    ("settings", "设置", "fa5s.cog", True),
]
```

`_make_page` 增加 editor 分支：

```python
    def _make_page(self, key):
        if key == "firmware":
            self._firmware = FirmwarePage(); return self._firmware
        if key == "editor":
            self._editor_page = ScriptEditorPage(); return self._editor_page
        if key == "settings":
            return SettingsPage(self._raw, self._path)
        return PlaceholderPage(_KEY2LABEL[key])
```

`__init__` 末尾（固件页接线之后）加编辑页接线：

```python
        # 脚本编辑/下发页接线
        self._editor_page.set_profile(profile)
        self._editor_page.set_port_getter(self._port.selected_port)
        self._editor_page.deploy_requested.connect(self._start_script)
```

加脚本下发启动方法（放在 `_start_firmware` 之后）。为 DRY，抽公共接线：

```python
    def _start_script(self, py_path: Path, slot: int):
        if self._busy or (self._thread is not None and self._thread.isRunning()):
            return
        port = self._port.selected_port()
        if not port:
            QMessageBox.warning(self, "提示", "未选择串口"); return
        self._busy = True
        self._editor_page.set_busy(True)
        self._transport = SerialTransport()
        self._deployer = DeviceDeployer(self._transport)
        self._deployer.progress.connect(self._editor_page.on_progress)
        self._deployer.state_changed.connect(self._on_state)
        self._deployer.log.connect(self._editor_page.on_log)
        self._deployer.error.connect(self._on_error)
        self._thread = QThread()
        self._worker = DeployWorker(self._transport, self._deployer)
        self._worker.set_job(self._profile, port, py_path=py_path, slot=slot)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run_script)   # 直连子线程槽，勿 lambda
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._on_finished)
        self._status.set_connection(port, self._profile.baud)
        self._thread.start()
```

`_on_state` 里对固件页的调用需兼容编辑页。将现有：

```python
    def _on_state(self, state: str):
        self._firmware.on_state(state)
        self._status.set_state(state)
        self._busy = state in _BUSY_STATES
        self._firmware.set_busy(self._busy)
        self._port.setEnabled(not self._busy)
        self._switch_btn.setEnabled(not self._busy)
        self._activity.set_locked(self._busy)
```

改为同时更新两页（编辑页有 on_state/set_busy，同构，安全）：

```python
    def _on_state(self, state: str):
        self._firmware.on_state(state)
        self._editor_page.on_state(state)
        self._status.set_state(state)
        self._busy = state in _BUSY_STATES
        self._firmware.set_busy(self._busy)
        self._editor_page.set_busy(self._busy)
        self._port.setEnabled(not self._busy)
        self._switch_btn.setEnabled(not self._busy)
        self._activity.set_locked(self._busy)
```

`_on_finished` 同理加编辑页解锁：

```python
    def _on_finished(self):
        self._busy = False
        self._firmware.set_busy(False)
        self._editor_page.set_busy(False)
        self._port.setEnabled(True)
        self._switch_btn.setEnabled(True)
        self._activity.set_locked(False)
        self._status.set_connection(None, None)
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/gui/test_main_window.py -q`
Expected: PASS（含新增与修改用例）

- [ ] **Step 6: Commit**

```bash
git add src/lbs_firmware_studio/gui/main_window.py tests/gui/test_main_window.py
git commit -m "feat(gui): wire ScriptEditorPage into MainWindow, hide scripts nav, script deploy thread"
```

---

## Task 9: 集成验证（冒烟导入 + 全 GUI 测试 + 后端零影响）

**Files:**
- 无新增，仅验证。

- [ ] **Step 1: 冒烟导入所有 GUI 模块**

Run:
```bash
python -c "from lbs_firmware_studio.gui import app, main_window, startup_window, theme; from lbs_firmware_studio.gui.widgets import activity_bar, status_bar, port_selector, log_view, code_editor; from lbs_firmware_studio.gui.pages import firmware_page, settings_page, placeholder_page, script_editor_page; print('all import ok')"
```
Expected: `all import ok`

- [ ] **Step 2: 按文件跑全部 GUI 测试**

Run（逐文件确认 passed，规避多 QThread 同进程 teardown 段错误）：
```bash
for f in theme activity_bar status_bar startup_window main_window firmware_page settings_page port_selector log_view placeholder_page code_editor script_editor_page; do echo "=== $f ==="; python -m pytest tests/gui/test_$f.py -q 2>&1 | tail -2; done
```
Expected: 每个文件都 `passed`（个别文件末尾可能因 QThread teardown 打印段错误，断言全过即可）。

- [ ] **Step 3: 跑后端 + worker 测试确认零影响**

Run: `python -m pytest tests/ --ignore=tests/gui -q`
Expected: 全部 passed（含 test_profile、test_worker 新增用例）。

- [ ] **Step 4: 手动启动验证（非自动化，人工确认）**

Run: `python -m lbs_firmware_studio.gui.app`
人工确认：进入产品 → 点左侧「代码编辑」图标 → 顶部模板下拉可选、选中加载内容 → 编辑器有行号+语法高亮+Tab 缩进 → 编辑器右上角两个圆形按钮（槽位 N / 上传图标）→ 点槽位弹 0..max_slot 菜单 → 保存写 write 目录 `<slot>.py` → 未保存点下发提示"请先保存" → 保存后下发走进度/日志/状态栏。

- [ ] **Step 5: Commit（若手动验证有微调）**

```bash
git add -A
git commit -m "test: integration verify script editor + deploy + slot"
```

---

## Self-Review 记录

- **Spec 覆盖**：
  - 架构组件 → Task 2/3（CodeEditor+Highlighter）、Task 5/6/7（ScriptEditorPage）、Task 1（profile 字段）、Task 4（worker）、Task 8（MainWindow）。
  - 数据流「选模板→编辑→保存→选槽→下发」→ Task 5（模板/保存）、Task 6（选槽/下发校验）、Task 8（下发线程）。
  - 未保存中止下发 → Task 6 `test_deploy_blocked_when_dirty`。
  - 保存到 write 目录 `<slot>.py` → Task 5 `test_save_writes_slot_py`。
  - max_slot 每产品（19/9/0）→ Task 1；NEXT-AI max_slot=0 单选 → Task 6 `test_slot_menu_single_when_max_slot_zero`。
  - templates_dir 推导 → Task 1；模板下拉扫描 → Task 5。
  - scripts 导航项隐藏 → Task 8。
  - 圆形按钮编辑器内部右上角 → Task 6（浮动 + eventFilter 重定位）。
  - 忙碌锁定 / 错误弹窗 → Task 7 + Task 8（复用 `_on_state`/`_on_error`/`set_locked`）。
  - 语法高亮取 theme 令牌 → Task 3。
- **占位扫描**：无 TBD/TODO；每步含完整代码或确切命令。
- **类型/命名一致性**：`set_job(profile, port, py_path=None, slot=0)`、`run_script()`、`deploy_requested(Path,int)`、`_start_script(py_path, slot)`、`slot_menu_values()`、`_set_slot()`、`set_port_getter()`、`on_progress/on_state/on_log/set_busy` 在定义任务与消费任务间一致。
- **已知风险**：
  - 高亮测试 `_has_colored_run` 依赖 block layout 的 formats()，若 PySide6 未即时布局可能为空——已用"触发 layout"缓解；若仍不稳，改断言 `highlightBlock` 被调用（可在高亮器加计数）。
  - 浮动按钮定位依赖 eventFilter Resize，首次显示前坐标可能未更新——不影响测试（测试不校验坐标，仅校验菜单/信号）。
  - `_on_state` 现同时驱动固件页与编辑页；两页均实现 on_state/set_busy，接口同构，安全。
