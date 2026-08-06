"""自制代码编辑器：QPlainTextEdit + 行号边栏 + 当前行高亮 + Tab→4 空格。

QScintilla 绑定 PyQt 与 PySide6 不兼容，故基于 QPlainTextEdit 自实现。
Python 语法高亮由本模块的 PythonHighlighter 提供（Task 3 接入）。
"""
from __future__ import annotations
import re
import keyword

from PySide6.QtWidgets import QPlainTextEdit, QWidget, QTextEdit
from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QColor, QPainter, QTextFormat, QSyntaxHighlighter, QTextCharFormat, QFont
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
        self.setObjectName("codeEditor")   # 全局 QSS: QPlainTextEdit#codeEditor { background: BG_CODE; }
        self._lna = _LineNumberArea(self)
        self.blockCountChanged.connect(self._update_lna_width)
        self.updateRequest.connect(self._update_lna)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self._update_lna_width(0)
        self._highlighter = PythonHighlighter(self.document())
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
        painter.fillRect(event.rect(), QColor(theme.BG_EDITOR))
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
        kw = _fmt(theme.SYNTAX_KEYWORD, bold=True)   # 关键字（violet，bold 保留）
        self._rules = []
        for word in keyword.kwlist:
            self._rules.append((re.compile(rf"\b{word}\b"), kw))
        self._rules.append((re.compile(r"@\w+"), _fmt(theme.SYNTAX_FUNC)))          # 装饰器（cyan）
        self._rules.append((re.compile(r"\b[0-9]+\.?[0-9]*\b"), _fmt(theme.SYNTAX_NUMBER)))  # 数字（amber）
        self._str_fmt = _fmt(theme.SYNTAX_STRING)    # 字符串（emerald）
        self._comment_fmt = _fmt(theme.TEXT_COMMENT, italic=True)  # 注释（灰，italic 保留）

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
