"""VS Code Dark+ 深色主题：配色令牌 + 全局 QSS。集中管理。"""
from __future__ import annotations

# ── 背景分层 ──
BG_EDITOR = "#1E1E1E"       # 编辑器/页面内容底色（VS Code 标准）
BG_SIDEBAR = "#252526"      # 卡片/分组框/侧栏
BG_BAR = "#2D2D30"          # 顶栏 + ActivityBar（VS Code 活动栏标准色）
BG_INPUT = "#3C3C3C"        # 输入框/按钮底
BG_HOVER = "#37373D"        # hover 底（提亮一档，可辨识）
BG_SELECTED = "#094771"     # 列表选中底（VS Code list.activeSelectionBackground）
BG_RAISED = "#2D2D30"       # 弹层（ProductSelector 面板/菜单），与顶栏同族
BG_SUBTLE = "#262626"       # 提示条/chip 底色，语义浅色叠加位
STATUSBAR = "#007ACC"       # 底部状态栏（VS Code 标志蓝）

# ── 文字 ──
TEXT_PRIMARY = "#E0E0E0"    # 正文/标题
TEXT_SECONDARY = "#A8A8A8"  # 次级/说明/分组标题
TEXT_DISABLED = "#7A7A7A"   # 禁用态
TEXT_COMMENT = "#7A9A8A"    # 代码注释（深色 IDE 注释绿灰）
TEXT_ON_ACCENT = "#FFFFFF"  # 强调色/状态栏上的文字
STATUSBAR_ON = "#E8F1FA"        # 蓝底状态栏前景（常态）
STATUSBAR_ON_MUTED = "#B0D4F1"  # 蓝底状态栏前景（弱化/禁用态）

# ── 强调 / 语义 ──
ACCENT = "#007ACC"          # 主强调（品牌蓝）
ACCENT_HOVER = "#1A8AD4"    # 强调 hover
ACCENT_FOCUS = "#3FB6FF"    # 焦点环（全组件键盘焦点可见，a11y）
SUCCESS = "#4EC9B0"
WARNING = "#D7BA3F"
ERROR = "#F14C4C"
BORDER = "#45454A"
BORDER_STRONG = "#55555C"
ICON_IDLE = "#9BA3AF"
ICON_HOVER = "#CCCCCC"
ICON_DISABLED = "#5A5A5E"
PRODUCT_GREEN = SUCCESS     # 产品名高亮色 = SUCCESS（语义引用而非重复定义，设计走查 C3）

# ── 语义浅底色（提示条 / 状态 chip）──
# QSS 支持 rgba；若个别平台渲染异常，可退回近似不透明色方案：
# SUCCESS_BG→#1F3B36 / WARNING_BG→#3A351C / ERROR_BG→#3B2026（二选一，见设计 §3.1）。
SUCCESS_BG = "rgba(78, 201, 176, 28)"
WARNING_BG = "rgba(215, 186, 63, 24)"
ERROR_BG = "rgba(241, 76, 76, 24)"

# UI 字体：Inter（开源版 SF，接近 App Store 观感），回退到系统无衬线
UI_FONT = "'Inter', 'Segoe UI Variable', 'Segoe UI', 'Microsoft YaHei UI', sans-serif"
MONO_FONT = "'Cascadia Code', 'Consolas', monospace"

# ── 间距刻度（8px 节奏，供各页面统一 margins/spacing）──
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16
SPACE_XL = 24
SPACE_XXL = 32

# ── 字号刻度（层级：说明/正文/小标题/标题）──
FONT_CAPTION = 11   # 辅助说明、状态栏
FONT_BODY = 13      # 正文（全局默认）
FONT_SUBTITLE = 14  # 分组小标题
FONT_TITLE = 18     # 页面/产品标题
FONT_LG = 22        # 弹层大标题（备用）

# ── 字重刻度 ──
WEIGHT_REGULAR = 400
WEIGHT_MEDIUM = 500
WEIGHT_BOLD = 600

# ── 圆角刻度 ──
RADIUS_SM = 4
RADIUS_MD = 6
RADIUS_LG = 8
RADIUS_FULL = 16     # 药丸按钮（floatbtn/chip）
RADIUS_PANEL = 10    # 弹层/对话框

# ── 图标尺寸刻度 ──
ICON_XS = 10   # 状态栏状态点、行内状态灯
ICON_SM = 14   # 列表项前导图标
ICON_MD = 16   # 顶栏/按钮图标
ICON_LG = 20   # 页内大按钮图标（可选）
ICON_XL = 24   # ActivityBar 主图标

# 部署状态 -> 中文阶段文案（唯一来源，C4 根治；固件页/脚本页/状态栏共用）
STAGE_TEXT = {
    "idle": "就绪", "compiling": "编译中", "connecting": "连接中",
    "entering_upgrade": "进入升级模式", "reconnecting": "等待设备重连",
    "transfering": "传输中", "done": "完成", "error": "出错",
}

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
        font-family: {UI_FONT}; font-size: {FONT_BODY}px; }}
    QFrame#card {{ background: {BG_SIDEBAR}; border: 1px solid {BORDER}; border-radius: {RADIUS_LG}px; }}
    QLabel {{ background: transparent; }}
    QGroupBox {{ background: {BG_SIDEBAR}; border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px;
        margin-top: 16px; padding: {SPACE_MD}px; }}
    QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left;
        left: {SPACE_MD}px; padding: 0 {SPACE_XS}px; color: {TEXT_SECONDARY};
        font-size: {FONT_SUBTITLE}px; font-weight: {WEIGHT_BOLD}; }}
    QPushButton#primary {{ background: {ACCENT}; color: {TEXT_ON_ACCENT}; border: none;
        border-radius: {RADIUS_SM}px; padding: 7px 16px; font-weight: {WEIGHT_BOLD}; }}
    QPushButton#primary:hover {{ background: {ACCENT_HOVER}; }}
    QPushButton#primary:pressed {{ background: {BG_SELECTED}; }}
    QPushButton#primary:disabled {{ background: {BG_INPUT}; color: {TEXT_DISABLED}; }}
    QPushButton {{ background: {BG_INPUT}; color: {TEXT_PRIMARY};
        border: 1px solid {BORDER}; border-radius: {RADIUS_SM}px; padding: 5px 12px; }}
    QPushButton:hover {{ background: {BG_HOVER}; border-color: {ACCENT_HOVER}; }}
    QPushButton:pressed {{ background: {BG_SELECTED}; }}
    QPushButton:disabled {{ color: {TEXT_DISABLED}; border-color: {BG_INPUT}; }}
    QPushButton:focus {{ border: 1px solid {ACCENT_FOCUS}; }}
    QComboBox {{ background: {BG_INPUT}; color: {TEXT_PRIMARY};
        border: 1px solid {BORDER}; border-radius: {RADIUS_SM}px; padding: 4px 8px; }}
    QComboBox:focus {{ border-color: {ACCENT_FOCUS}; }}
    QComboBox QAbstractItemView {{ background: {BG_INPUT}; color: {TEXT_PRIMARY};
        selection-background-color: {BG_SELECTED}; }}
    QRadioButton {{ background: transparent; color: {TEXT_PRIMARY}; spacing: 6px; }}
    QRadioButton:disabled {{ color: {TEXT_DISABLED}; }}
    QRadioButton::indicator {{ width: {ICON_MD}px; height: {ICON_MD}px; border-radius: 8px;
        border: 1px solid {BORDER}; background: transparent; }}
    QRadioButton::indicator:hover {{ border-color: {SUCCESS}; }}
    QRadioButton::indicator:checked {{ border: 1px solid {SUCCESS}; background: {SUCCESS}; }}
    QRadioButton::indicator:disabled {{ border-color: {BG_INPUT}; background: {BG_INPUT}; }}
    QLineEdit {{ background: {BG_INPUT}; color: {TEXT_PRIMARY};
        border: 1px solid {BORDER}; border-radius: {RADIUS_SM}px; padding: 5px 8px; }}
    QLineEdit:focus {{ border-color: {ACCENT_FOCUS}; }}
    QLineEdit:read-only {{ color: {TEXT_SECONDARY}; }}
    QPlainTextEdit, QTextEdit {{ background: {BG_EDITOR}; color: {TEXT_PRIMARY};
        border: 1px solid {BORDER}; border-radius: {RADIUS_SM}px;
        font-family: {MONO_FONT}; }}
    QProgressBar {{ border: none; border-radius: 3px; background: {BG_INPUT};
        height: 6px; text-align: center; color: {TEXT_PRIMARY}; font-size: {FONT_CAPTION}px; }}
    QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}
    QToolTip {{ background: {BG_SIDEBAR}; color: {TEXT_PRIMARY}; border: 1px solid {BORDER};
        padding: 4px 8px; }}
    QToolButton:focus {{ border: 1px solid {ACCENT_FOCUS}; border-radius: {RADIUS_SM}px; }}
    QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: {BG_INPUT}; border-radius: 4px; min-height: 24px; }}
    QScrollBar::handle:vertical:hover {{ background: {BG_HOVER}; }}
    QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 0; }}
    QScrollBar::handle:horizontal {{ background: {BG_INPUT}; border-radius: 4px; min-width: 24px; }}
    QScrollBar::handle:horizontal:hover {{ background: {BG_HOVER}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
    QMenu {{ background: {BG_RAISED}; color: {TEXT_PRIMARY};
        border: 1px solid {BORDER}; border-radius: {RADIUS_PANEL}px; padding: 4px; }}
    QMenu::item {{ padding: 6px 24px; border-radius: {RADIUS_SM}px; }}
    QMenu::item:selected {{ background: {BG_SELECTED}; color: {TEXT_ON_ACCENT}; }}
    QMenu::item:disabled {{ color: {TEXT_DISABLED}; }}
    QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 8px; }}
    QDialog {{ background: {BG_EDITOR}; color: {TEXT_PRIMARY}; }}
    QMessageBox {{ background: {BG_EDITOR}; color: {TEXT_PRIMARY};
        border: 1px solid {BORDER}; border-radius: {RADIUS_PANEL}px; }}
    QListWidget {{ background: transparent; border: none; outline: none; color: {TEXT_PRIMARY}; }}
    QListWidget::item {{ padding: 6px 8px; border-radius: {RADIUS_SM}px; }}
    QListWidget::item:hover {{ background: {BG_HOVER}; }}
    QListWidget::item:selected {{ background: {BG_SELECTED}; color: {TEXT_ON_ACCENT}; }}
    """
