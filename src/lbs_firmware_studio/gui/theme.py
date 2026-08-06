"""深色科技风主题（依据 doc/ui-redesign.md）：配色令牌 + 全局 QSS。集中管理。"""
from __future__ import annotations

# ── 背景分层 ──
BG_PAGE = "#0b1018"       # 页面底色（body bg）
BG_EDITOR = BG_PAGE       # 页面底（兼容旧名；原「编辑器/页面内容底色」语义）
BG_SIDEBAR = "#0e151f"      # 左侧侧栏底（aside）
BG_BAR = "#101722"          # 顶栏 + 底部状态栏底（header/statusbar）
BG_INPUT = "#1e293b"        # 输入框/按钮底（slate-800）
BG_HOVER = "#1f2b3d"        # hover 提亮（可辨识一档）
BG_SELECTED = "#1A22d3ee"    # 选中导航项底（bg-cyan-400/10；#AARRGGBB，alpha 26≈10%，QSS 与 QColor 均支持）
BG_RAISED = "#121b27"       # 弹层/浮窗/菜单底（安全连接卡）
BG_SUBTLE = "#0d141e"       # 统计块/浅底色
STATUSBAR = "#101722"       # 底部状态栏（深色，不再是蓝底）
BG_CARD = "#101722"         # 卡片/面板底（rounded-xl 卡片）
BG_CODE = "#0d131c"         # 编辑器主体底（editor）
BG_LOGS = "#0a0f16"         # 日志/代码深底（logs）

# ── 文字 ──
TEXT_PRIMARY = "#e2e8f0"    # 正文/标题（slate-200）
TEXT_SECONDARY = "#94a3b8"  # 次级/说明（slate-400）
TEXT_DISABLED = "#64748b"   # 禁用/弱化（slate-500）
TEXT_COMMENT = "#7c8ea0"    # 代码注释
TEXT_ON_ACCENT = "#020617"  # 强调色/状态栏上的文字（slate-950）
STATUSBAR_ON = "#e2e8f0"        # 状态栏前景（常态）
STATUSBAR_ON_MUTED = "#64748b"  # 状态栏前景（弱化/禁用态）

# ── 强调 / 语义 ──
ACCENT = "#22d3ee"          # 主强调（cyan-400）
ACCENT_HOVER = "#67e8f9"    # 强调 hover（cyan-300）
ACCENT_PRESSED = "#0e7490"  # 强调 pressed（cyan-700，保持深色文字可读）
ACCENT_FOCUS = "#67e8f9"    # 键盘焦点环（全组件键盘焦点可见，a11y）
SUCCESS = "#34d399"         # 成功（emerald-400）
WARNING = "#fbbf24"         # 警告（amber-400）
ERROR = "#f87171"           # 错误（red-400）
BORDER = "#1e293b"          # 普通边框（slate-800）
BORDER_STRONG = "#334155"   # 强调边框（slate-700）
ICON_IDLE = "#94a3b8"       # 图标常态（slate-400）
ICON_HOVER = "#e2e8f0"      # 图标 hover（slate-200）
ICON_DISABLED = "#475569"   # 图标禁用（slate-600）
PRODUCT_GREEN = SUCCESS     # 产品名高亮色 = SUCCESS（语义引用而非重复定义）

# ── 代码语法高亮（编辑器 PythonHighlighter / 语法着色，追加于「强调/语义」区块后）──
SYNTAX_KEYWORD = "#a78bfa"  # 关键字（violet）
SYNTAX_STRING = "#6ee7b7"   # 字符串（emerald）
SYNTAX_NUMBER = "#fcd34d"   # 数字（amber）
SYNTAX_FUNC = "#67e8f9"     # 函数名/装饰器（cyan）

# ── 语义浅底色（提示条 / 状态 chip）──
# QSS 支持 rgba；若个别平台渲染异常，可退回近似不透明色方案（见设计 §3.1）。
SUCCESS_BG = "rgba(52, 211, 153, 24)"
WARNING_BG = "rgba(251, 191, 36, 20)"
ERROR_BG = "rgba(248, 113, 113, 20)"

# 传感器端口色板（P1–P8，每端口一 accent 色；取 SENSOR_COLORS[port % 8]）
SENSOR_COLORS = [
    "#22d3ee",  # cyan
    "#a78bfa",  # violet
    "#e879f9",  # fuchsia
    "#38bdf8",  # sky
    "#fbbf24",  # amber
    "#fb7185",  # rose
    "#34d399",  # emerald
    "#a3e635",  # lime
]

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

# ── 布局常量（顶栏高 / 侧栏宽，供后续布局使用）──
HEADER_H = 56
SIDEBAR_WIDTH = 256

# ── 字号刻度（层级：说明/正文/小标题/标题）──
FONT_CAPTION = 11   # 辅助说明、状态栏
FONT_BODY = 13      # 正文（全局默认）
FONT_SUBTITLE = 14  # 分组小标题
FONT_TITLE = 24     # 页面/产品标题（text-2xl）
FONT_LG = 28        # 弹层大标题（备用）

# ── 字重刻度 ──
WEIGHT_REGULAR = 400
WEIGHT_MEDIUM = 500
WEIGHT_BOLD = 600

# ── 圆角刻度 ──
RADIUS_SM = 6
RADIUS_MD = 8
RADIUS_LG = 12
RADIUS_FULL = 16     # 药丸按钮（floatbtn/chip）
RADIUS_PANEL = 12    # 弹层/对话框

# ── 图标尺寸刻度 ──
ICON_XS = 10   # 状态栏状态点、行内状态灯
ICON_SM = 14   # 列表项前导图标
ICON_MD = 16   # 顶栏/按钮图标
ICON_LG = 20   # 页内大按钮图标（可选）
ICON_XL = 24   # ActivityBar 主图标

# 部署状态 -> 中文阶段文案（唯一来源，固件页/脚本页/状态栏共用）
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
    QFrame#card {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_LG}px; }}
    QFrame#hostBar {{ background: transparent; border: none; }}
    QLabel {{ background: transparent; }}
    QGroupBox {{ background: {BG_SIDEBAR}; border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px;
        margin-top: 16px; padding: {SPACE_MD}px; }}
    QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left;
        left: {SPACE_MD}px; padding: 0 {SPACE_XS}px; color: {TEXT_SECONDARY};
        font-size: {FONT_SUBTITLE}px; font-weight: {WEIGHT_BOLD}; }}
    QPushButton#primary {{ background: {ACCENT}; color: {TEXT_ON_ACCENT}; border: none;
        border-radius: {RADIUS_SM}px; padding: 7px 16px; font-weight: {WEIGHT_BOLD}; }}
    QPushButton#primary:hover {{ background: {ACCENT_HOVER}; }}
    QPushButton#primary:pressed {{ background: {ACCENT_PRESSED}; }}
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
    QPlainTextEdit, QTextEdit {{ background: {BG_LOGS}; color: {TEXT_PRIMARY};
        border: 1px solid {BORDER}; border-radius: {RADIUS_SM}px;
        font-family: {MONO_FONT}; }}
    QPlainTextEdit#codeEditor {{ background: {BG_CODE}; }}
    QProgressBar {{ border: none; border-radius: 3px; background: {BG_INPUT};
        height: 6px; text-align: center; color: {TEXT_PRIMARY}; font-size: {FONT_CAPTION}px; }}
    QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}
    QToolTip {{ background: {BG_RAISED}; color: {TEXT_PRIMARY}; border: 1px solid {BORDER};
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
    QMenu::item:selected {{ background: {BG_SELECTED}; color: {TEXT_PRIMARY}; }}
    QMenu::item:disabled {{ color: {TEXT_DISABLED}; }}
    QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 8px; }}
    QDialog {{ background: {BG_EDITOR}; color: {TEXT_PRIMARY}; }}
    QMessageBox {{ background: {BG_EDITOR}; color: {TEXT_PRIMARY};
        border: 1px solid {BORDER}; border-radius: {RADIUS_PANEL}px; }}
    QListWidget {{ background: transparent; border: none; outline: none; color: {TEXT_PRIMARY}; }}
    QListWidget::item {{ padding: 6px 8px; border-radius: {RADIUS_SM}px; }}
    QListWidget::item:hover {{ background: {BG_HOVER}; }}
    QListWidget::item:selected {{ background: {BG_SELECTED}; color: {TEXT_PRIMARY}; }}
    """
