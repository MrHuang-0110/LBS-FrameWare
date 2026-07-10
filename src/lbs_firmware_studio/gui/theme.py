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
PRODUCT_GREEN = "#4EC9B0"   # 产品名绿色（同 SUCCESS，语义化别名）

# UI 字体：Inter（开源版 SF，接近 App Store 观感），回退到系统无衬线
UI_FONT = "'Inter', 'Segoe UI Variable', 'Segoe UI', 'Microsoft YaHei UI', sans-serif"
MONO_FONT = "'Cascadia Code', 'Consolas', monospace"

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
        font-family: {UI_FONT}; font-size: 13px; }}
    QFrame#card {{ background: {BG_SIDEBAR}; border: 1px solid {BORDER}; border-radius: 10px; }}
    QLabel {{ background: transparent; }}
    QGroupBox {{ background: {BG_SIDEBAR}; border: 1px solid {BORDER}; border-radius: 8px;
        margin-top: 14px; padding: 12px; }}
    QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left;
        left: 12px; padding: 0 4px; color: {TEXT_SECONDARY}; }}
    QPushButton#primary {{ background: {ACCENT}; color: {TEXT_ON_ACCENT}; border: none;
        border-radius: 6px; padding: 6px 14px; }}
    QPushButton#primary:hover {{ background: {ACCENT_HOVER}; }}
    QPushButton#primary:pressed {{ background: {BG_SELECTED}; }}
    QPushButton#primary:disabled {{ background: {BG_INPUT}; color: {TEXT_DISABLED}; }}
    QPushButton {{ background: {BG_INPUT}; color: {TEXT_PRIMARY};
        border: 1px solid {BORDER}; border-radius: 6px; padding: 5px 12px; }}
    QPushButton:hover {{ background: {BG_HOVER}; }}
    QPushButton:pressed {{ background: {BG_SELECTED}; }}
    QPushButton:disabled {{ color: {TEXT_DISABLED}; border-color: {BG_INPUT}; }}
    QComboBox {{ background: {BG_INPUT}; color: {TEXT_PRIMARY};
        border: 1px solid {BORDER}; border-radius: 6px; padding: 4px 8px; }}
    QComboBox QAbstractItemView {{ background: {BG_INPUT}; color: {TEXT_PRIMARY};
        selection-background-color: {BG_SELECTED}; }}
    QLineEdit {{ background: {BG_INPUT}; color: {TEXT_PRIMARY};
        border: 1px solid {BORDER}; border-radius: 6px; padding: 4px 8px; }}
    QPlainTextEdit, QTextEdit {{ background: {BG_EDITOR}; color: {TEXT_PRIMARY};
        border: 1px solid {BORDER}; border-radius: 6px;
        font-family: {MONO_FONT}; }}
    QProgressBar {{ border: none; border-radius: 3px; background: {BG_INPUT};
        height: 6px; text-align: center; color: {TEXT_PRIMARY}; }}
    QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}
    QToolTip {{ background: {BG_SIDEBAR}; color: {TEXT_PRIMARY}; border: 1px solid {BORDER}; }}
    """
