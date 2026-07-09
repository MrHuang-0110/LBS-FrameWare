"""App Store 风格配色 + 全局 QSS。集中管理，便于统一调整。"""
from __future__ import annotations

BG = "#F5F5F7"
PANEL = "#FFFFFF"
ACCENT = "#0071E3"
SUCCESS = "#34C759"
AMBER = "#FF9F0A"
ERROR = "#FF3B30"
MUTED = "#86868B"
TEXT = "#1D1D1F"

_STATE_COLORS = {
    "idle": MUTED,
    "compiling": AMBER, "connecting": AMBER, "entering_upgrade": AMBER,
    "reconnecting": AMBER, "transfering": AMBER,
    "done": SUCCESS,
    "error": ERROR,
}


def state_color(state: str) -> str:
    return _STATE_COLORS.get(state, MUTED)


def app_qss() -> str:
    return f"""
    QWidget {{ background: {BG}; color: {TEXT};
        font-family: 'Segoe UI Variable', 'Segoe UI', 'Inter', sans-serif; font-size: 14px; }}
    QFrame#card, QFrame#panel {{ background: {PANEL}; border-radius: 12px; }}
    QPushButton#primary {{ background: {ACCENT}; color: white; border: none;
        border-radius: 8px; padding: 10px 20px; font-weight: 600; }}
    QPushButton#primary:disabled {{ background: {MUTED}; }}
    QPushButton {{ background: {PANEL}; border: 1px solid #D2D2D7; border-radius: 8px;
        padding: 6px 14px; }}
    QComboBox {{ background: {PANEL}; border: 1px solid #D2D2D7; border-radius: 8px; padding: 6px; }}
    QTextEdit, QPlainTextEdit {{ background: {PANEL}; border: 1px solid #D2D2D7;
        border-radius: 8px; font-family: 'Cascadia Code', 'JetBrains Mono', monospace; }}
    QProgressBar {{ border: none; border-radius: 6px; background: #E5E5EA; height: 12px; text-align: center; }}
    QProgressBar::chunk {{ background: {ACCENT}; border-radius: 6px; }}
    """
