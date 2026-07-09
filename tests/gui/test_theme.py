from lbs_firmware_studio.gui import theme


def test_dark_colors_defined():
    assert theme.BG_EDITOR == "#1E1E1E"
    assert theme.BG_BAR == "#333333"
    assert theme.STATUSBAR == "#007ACC"
    assert theme.ACCENT == "#007ACC"
    assert theme.TEXT_PRIMARY == "#CCCCCC"
    assert theme.BORDER == "#3E3E42"


def test_state_color_dark_mapping():
    assert theme.state_color("idle") == "#858585"
    assert theme.state_color("transfering") == "#CCA700"
    assert theme.state_color("reconnecting") == "#CCA700"
    assert theme.state_color("done") == "#4EC9B0"
    assert theme.state_color("error") == "#F14C4C"
    assert theme.state_color("unknown_x") == "#858585"


def test_app_qss_is_dark():
    qss = theme.app_qss()
    assert isinstance(qss, str) and len(qss) > 0
    assert "#1E1E1E" in qss     # 深色底进了 QSS
    assert "#007ACC" in qss     # 强调蓝进了 QSS
