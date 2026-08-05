from lbs_firmware_studio.gui.widgets.status_bar import StatusBar
from lbs_firmware_studio.gui import theme


def test_default_disconnected(qtbot):
    w = StatusBar(); qtbot.addWidget(w)
    assert "未连接" in w.connection_text()


def test_set_connection(qtbot):
    w = StatusBar(); qtbot.addWidget(w)
    w.set_connection("COM9", 115200)
    txt = w.connection_text()
    assert "COM9" in txt and "115200" in txt


def test_set_connection_none_shows_disconnected(qtbot):
    w = StatusBar(); qtbot.addWidget(w)
    w.set_connection("COM9", 115200)
    w.set_connection(None, None)
    assert "未连接" in w.connection_text()


def test_state_text_and_color(qtbot):
    w = StatusBar(); qtbot.addWidget(w)
    w.set_state("transfering")
    assert "传输" in w.state_text()
    assert w.state_color() == theme.WARNING
    w.set_state("done")
    assert w.state_color() == theme.SUCCESS


def test_set_product(qtbot):
    """设计 B9/§4.1：状态栏不再显示产品名；set_product 兼容保留但 state_text 只含阶段文案。"""
    w = StatusBar(); qtbot.addWidget(w)
    w.set_product("NEW-AI")
    assert "NEW-AI" not in w.state_text()
    assert w.state_text() == theme.STAGE_TEXT["idle"]


def test_statusbar_on_colors(qtbot):
    """A7/§4.1：蓝底状态栏前景走 STATUSBAR_ON 组——
    阶段文案用 STATUSBAR_ON；未连接态连接文字用 STATUSBAR_ON_MUTED，连接后切回 STATUSBAR_ON。"""
    w = StatusBar(); qtbot.addWidget(w)
    assert theme.STATUSBAR_ON in w._stage_lbl.styleSheet()
    assert theme.STATUSBAR_ON_MUTED in w._conn.styleSheet()   # 未连接弱化
    w.set_connection("COM9", 115200)
    assert theme.STATUSBAR_ON in w._conn.styleSheet()          # 连接后常态
