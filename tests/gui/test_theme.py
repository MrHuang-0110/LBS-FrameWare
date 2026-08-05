from lbs_firmware_studio.gui import theme


def test_dark_colors_defined():
    # 背景分层
    assert theme.BG_EDITOR == "#1E1E1E"
    assert theme.BG_SIDEBAR == "#252526"
    assert theme.BG_BAR == "#2D2D30"
    assert theme.BG_INPUT == "#3C3C3C"
    assert theme.BG_HOVER == "#37373D"
    assert theme.BG_SELECTED == "#094771"
    assert theme.STATUSBAR == "#007ACC"
    # 文字
    assert theme.TEXT_PRIMARY == "#E0E0E0"
    assert theme.TEXT_SECONDARY == "#A8A8A8"
    assert theme.TEXT_DISABLED == "#7A7A7A"
    assert theme.TEXT_ON_ACCENT == "#FFFFFF"
    # 强调 / 语义
    assert theme.ACCENT == "#007ACC"
    assert theme.ACCENT_HOVER == "#1A8AD4"
    assert theme.SUCCESS == "#4EC9B0"
    assert theme.WARNING == "#D7BA3F"
    assert theme.ERROR == "#F14C4C"
    assert theme.BORDER == "#45454A"
    assert theme.ICON_IDLE == "#9BA3AF"
    assert theme.ICON_DISABLED == "#5A5A5E"


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
    assert "#1E1E1E" in qss     # 深色底进了 QSS
    assert "#007ACC" in qss     # 强调蓝进了 QSS


def test_new_tokens_defined():
    # 新色令牌
    assert theme.ACCENT_FOCUS == "#3FB6FF"
    assert theme.BG_RAISED == "#2D2D30"
    assert theme.BG_SUBTLE == "#262626"
    assert theme.TEXT_COMMENT == "#7A9A8A"
    assert theme.BORDER_STRONG == "#55555C"
    assert theme.ICON_HOVER == "#CCCCCC"
    assert theme.STATUSBAR_ON == "#E8F1FA"
    # PRODUCT_GREEN 为 SUCCESS 的语义引用，而非重复值
    assert theme.PRODUCT_GREEN == theme.SUCCESS
    assert theme.PRODUCT_GREEN == "#4EC9B0"
    # 字号 / 圆角 / 间距
    assert theme.FONT_SUBTITLE == 14
    assert (theme.RADIUS_SM, theme.RADIUS_MD, theme.RADIUS_LG) == (4, 6, 8)
    assert theme.RADIUS_FULL == 16
    assert theme.RADIUS_PANEL == 10
    assert theme.SPACE_XXL == 32
    # 图标尺寸刻度
    assert (theme.ICON_XS, theme.ICON_SM, theme.ICON_MD) == (10, 14, 16)
    assert (theme.ICON_LG, theme.ICON_XL) == (20, 24)
    # 字重刻度
    assert (theme.WEIGHT_REGULAR, theme.WEIGHT_MEDIUM, theme.WEIGHT_BOLD) == (400, 500, 600)
    # 语义浅底色（rgba）
    assert theme.SUCCESS_BG == "rgba(78, 201, 176, 28)"
    assert theme.WARNING_BG == "rgba(215, 186, 63, 24)"
    assert theme.ERROR_BG == "rgba(241, 76, 76, 24)"


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
