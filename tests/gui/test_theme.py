from lbs_firmware_studio.gui import theme


def test_colors_defined():
    assert theme.ACCENT == "#0071E3"
    assert theme.BG == "#F5F5F7"
    assert theme.SUCCESS == "#34C759"
    assert theme.ERROR == "#FF3B30"


def test_state_color_mapping():
    assert theme.state_color("idle") == theme.MUTED
    assert theme.state_color("transfering") == theme.AMBER
    assert theme.state_color("reconnecting") == theme.AMBER
    assert theme.state_color("done") == theme.SUCCESS
    assert theme.state_color("error") == theme.ERROR
    assert theme.state_color("unknown_state") == theme.MUTED  # 未知态回退灰


def test_app_qss_is_str():
    qss = theme.app_qss()
    assert isinstance(qss, str) and len(qss) > 0
    assert theme.ACCENT in qss  # 强调色进了 QSS
