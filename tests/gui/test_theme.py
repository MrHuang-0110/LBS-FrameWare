from lbs_firmware_studio.gui import theme


def test_dark_colors_defined():
    # 背景分层
    assert theme.BG_EDITOR == "#0b1018"
    assert theme.BG_SIDEBAR == "#0e151f"
    assert theme.BG_BAR == "#101722"
    assert theme.BG_INPUT == "#1e293b"
    assert theme.BG_HOVER == "#1f2b3d"
    assert theme.BG_SELECTED == "#1A22d3ee"
    assert theme.STATUSBAR == "#101722"
    # 文字
    assert theme.TEXT_PRIMARY == "#e2e8f0"
    assert theme.TEXT_SECONDARY == "#94a3b8"
    assert theme.TEXT_DISABLED == "#64748b"
    assert theme.TEXT_ON_ACCENT == "#020617"
    # 强调 / 语义
    assert theme.ACCENT == "#22d3ee"
    assert theme.ACCENT_HOVER == "#67e8f9"
    assert theme.SUCCESS == "#34d399"
    assert theme.WARNING == "#fbbf24"
    assert theme.ERROR == "#f87171"
    assert theme.BORDER == "#1e293b"
    assert theme.ICON_IDLE == "#94a3b8"
    assert theme.ICON_DISABLED == "#475569"


def test_state_color_dark_mapping():
    assert theme.state_color("idle") == theme.ICON_IDLE
    assert theme.state_color("transfering") == theme.WARNING
    assert theme.state_color("reconnecting") == theme.WARNING
    assert theme.state_color("done") == theme.SUCCESS
    assert theme.state_color("error") == theme.ERROR
    assert theme.state_color("unknown_x") == theme.ICON_IDLE


def test_app_qss_is_dark():
    qss = theme.app_qss()
    assert isinstance(qss, str) and len(qss) > 0
    assert "#0b1018" in qss     # 页面深色底进了 QSS
    assert "#22d3ee" in qss     # 强调 cyan 进了 QSS
    assert "#0a0f16" in qss     # 日志区深底（QPlainTextEdit/QTextEdit）


def test_new_tokens_defined():
    # 新色令牌
    assert theme.ACCENT_FOCUS == "#67e8f9"
    assert theme.BG_RAISED == "#121b27"
    assert theme.BG_SUBTLE == "#0d141e"
    assert theme.TEXT_COMMENT == "#7c8ea0"
    assert theme.BORDER_STRONG == "#334155"
    assert theme.ICON_HOVER == "#e2e8f0"
    assert theme.STATUSBAR_ON == "#e2e8f0"
    assert theme.STATUSBAR_ON_MUTED == "#64748b"
    # PRODUCT_GREEN 为 SUCCESS 的语义引用，而非重复值
    assert theme.PRODUCT_GREEN == theme.SUCCESS
    assert theme.PRODUCT_GREEN == "#34d399"
    # 新增背景令牌 / 传感器端口色板 / 布局常量
    assert theme.BG_CARD == "#101722"
    assert theme.BG_CODE == "#0d131c"
    assert theme.BG_LOGS == "#0a0f16"
    assert len(theme.SENSOR_COLORS) == 8
    assert theme.SIDEBAR_WIDTH == 256
    assert theme.HEADER_H == 56
    # 字号 / 圆角 / 间距
    assert theme.FONT_TITLE == 24
    assert theme.FONT_SUBTITLE == 14
    assert (theme.RADIUS_SM, theme.RADIUS_MD, theme.RADIUS_LG) == (6, 8, 12)
    assert theme.RADIUS_FULL == 16
    assert theme.RADIUS_PANEL == 12
    assert theme.SPACE_XXL == 32
    # 图标尺寸刻度
    assert (theme.ICON_XS, theme.ICON_SM, theme.ICON_MD) == (10, 14, 16)
    assert (theme.ICON_LG, theme.ICON_XL) == (20, 24)
    # 字重刻度
    assert (theme.WEIGHT_REGULAR, theme.WEIGHT_MEDIUM, theme.WEIGHT_BOLD) == (400, 500, 600)
    # 语义浅底色（rgba）
    assert theme.SUCCESS_BG == "rgba(52, 211, 153, 24)"
    assert theme.WARNING_BG == "rgba(251, 191, 36, 20)"
    assert theme.ERROR_BG == "rgba(248, 113, 113, 20)"


def test_stage_text_single_source():
    expected = {
        "idle": "就绪",
        "compiling": "编译中",
        "connecting": "连接中",
        "entering_upgrade": "进入升级模式",
        "reconnecting": "等待设备重连",
        "transfering": "传输中",
        "done": "完成",
        "error": "出错",
    }
    assert theme.STAGE_TEXT == expected
