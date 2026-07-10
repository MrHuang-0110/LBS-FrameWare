from lbs_firmware_studio.gui.widgets.code_editor import CodeEditor
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
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


def _fg_at(ed, start, length):
    # 精确定位首个 block 中 [start, start+length) 这一段的字符格式；
    # 找不到返回 None（不做任何兜底放行）。
    # 返回 QTextCharFormat 的副本，避免底层 C++ 临时对象被回收。
    from PySide6.QtGui import QTextCharFormat
    block = ed.document().firstBlock()
    layout = block.layout()
    for r in (layout.formats() if layout else []):
        if r.start == start and r.length == length:
            return QTextCharFormat(r.format)
    return None


def test_highlighter_colors_keywords(qtbot):
    from lbs_firmware_studio.gui import theme
    from PySide6.QtGui import QFont
    ed = CodeEditor(); qtbot.addWidget(ed)
    ed.set_text("import time  # comment")
    ed.document().firstBlock().layout()

    # 关键字 span：'import' → ACCENT + Bold
    kw = _fg_at(ed, 0, len("import"))
    assert kw is not None, "关键字 'import' span 未定位到"
    assert kw.foreground().color().name().lower() == theme.ACCENT.lower()
    assert kw.fontWeight() == QFont.Bold

    # 注释 span：'# comment' 从第 13 列到行尾 → TEXT_DISABLED + Italic
    text = "import time  # comment"
    hash_idx = text.find("#")
    assert hash_idx == 13
    comment = _fg_at(ed, hash_idx, len(text) - hash_idx)
    assert comment is not None, "注释 span 未定位到"
    assert comment.foreground().color().name().lower() == theme.TEXT_DISABLED.lower()
    assert comment.fontItalic() is True


def test_highlighter_colors_strings(qtbot):
    from lbs_firmware_studio.gui import theme
    ed = CodeEditor(); qtbot.addWidget(ed)
    ed.set_text("s = 'hi'")            # 字符串 'hi' 从第 4 列，长度 4
    ed.document().firstBlock().layout()
    s = _fg_at(ed, 4, len("'hi'"))
    assert s is not None, "字符串 span 未定位到"
    assert s.foreground().color().name().lower() == theme.SUCCESS.lower()


def test_highlighter_colors_numbers(qtbot):
    from lbs_firmware_studio.gui import theme
    ed = CodeEditor(); qtbot.addWidget(ed)
    ed.set_text("x = 42")              # 数字 42 从第 4 列，长度 2
    ed.document().firstBlock().layout()
    n = _fg_at(ed, 4, len("42"))
    assert n is not None, "数字 span 未定位到"
    assert n.foreground().color().name().lower() == theme.WARNING.lower()


def test_highlighter_instance_attached(qtbot):
    from lbs_firmware_studio.gui.widgets.code_editor import PythonHighlighter
    ed = CodeEditor(); qtbot.addWidget(ed)
    assert isinstance(ed._highlighter, PythonHighlighter)
