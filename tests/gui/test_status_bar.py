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
    w = StatusBar(); qtbot.addWidget(w)
    w.set_product("NEW-AI")
    assert "NEW-AI" in w.state_text() or "NEW-AI" in w._product_lbl.text()
