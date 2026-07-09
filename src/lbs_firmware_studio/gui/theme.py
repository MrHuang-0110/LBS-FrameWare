"""VS Code Dark+ 深色主题：配色令牌 + 全局 QSS。集中管理。"""
from __future__ import annotations

# 背景分层
BG_EDITOR = "#1E1E1E"
BG_SIDEBAR = "#252526"
BG_BAR = "#333333"
BG_INPUT = "#3C3C3C"
BG_HOVER = "#2A2D2E"
BG_SELECTED = "#094771"
STATUSBAR = "#007ACC"
# 文字
TEXT_PRIMARY = "#CCCCCC"
TEXT_SECONDARY = "#9D9D9D"
TEXT_DISABLED = "#6A6A6A"
TEXT_ON_ACCENT = "#FFFFFF"
# 强调 / 语义
ACCENT = "#007ACC"
ACCENT_HOVER = "#1177BB"
SUCCESS = "#4EC9B0"
WARNING = "#CCA700"
ERROR = "#F14C4C"
BORDER = "#3E3E42"
ICON_IDLE = "#858585"
ICON_DISABLED = "#4A4A4A"

_STATE_COLORS = {
    "idle": ICON_IDLE,
    "compiling": WARNING, "connecting": WARNING, "entering_upgrade": WARNING,
    "reconnecting": WARNING, "transfering": WARNING,
    "done": SUCCESS,
    "error": ERROR,
}


def state_color(state: str) -> str:
    return _STATE_COLORS.get(state, ICON_IDLE)


def app_qss() -> str:
    return f"""
    QWidget {{ background: {BG_EDITOR}; color: {TEXT_PRIMARY};
        font-family: 'Segoe UI', 'Microsoft YaHei UI', sans-serif; font-size: 13px; }}
    QFrame#card {{ background: {BG_SIDEBAR}; border: 1px solid {BORDER}; border-radius: 2px; }}
    QLabel {{ background: transparent; }}
    QPushButton#primary {{ background: {ACCENT}; color: {TEXT_ON_ACCENT}; border: none;
        border-radius: 2px; padding: 6px 14px; }}
    QPushButton#primary:hover {{ background: {ACCENT_HOVER}; }}
    QPushButton#primary:disabled {{ background: {BG_INPUT}; color: {TEXT_DISABLED}; }}
    QPushButton {{ background: transparent; color: {TEXT_PRIMARY};
        border: 1px solid {BORDER}; border-radius: 2px; padding: 5px 12px; }}
    QPushButton:hover {{ background: {BG_HOVER}; }}
    QPushButton:disabled {{ color: {TEXT_DISABLED}; border-color: {BG_INPUT}; }}
    QComboBox {{ background: {BG_INPUT}; color: {TEXT_PRIMARY};
        border: 1px solid {BORDER}; border-radius: 2px; padding: 4px 8px; }}
    QComboBox QAbstractItemView {{ background: {BG_INPUT}; color: {TEXT_PRIMARY};
        selection-background-color: {BG_SELECTED}; }}
    QLineEdit {{ background: {BG_INPUT}; color: {TEXT_PRIMARY};
        border: 1px solid {BORDER}; border-radius: 2px; padding: 4px 8px; }}
    QPlainTextEdit, QTextEdit {{ background: {BG_EDITOR}; color: {TEXT_PRIMARY};
        border: 1px solid {BORDER}; border-radius: 2px;
        font-family: 'Cascadia Code', 'Consolas', monospace; }}
    QProgressBar {{ border: none; border-radius: 2px; background: {BG_INPUT};
        height: 6px; text-align: center; color: {TEXT_PRIMARY}; }}
    QProgressBar::chunk {{ background: {ACCENT}; border-radius: 2px; }}
    QToolTip {{ background: {BG_SIDEBAR}; color: {TEXT_PRIMARY}; border: 1px solid {BORDER}; }}
    """
