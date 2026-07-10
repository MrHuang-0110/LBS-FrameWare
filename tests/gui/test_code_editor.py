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
