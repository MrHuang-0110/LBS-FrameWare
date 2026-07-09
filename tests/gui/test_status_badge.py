from lbs_firmware_studio.gui.widgets.status_badge import StatusBadge
from lbs_firmware_studio.gui import theme


def test_badge_default_idle(qtbot):
    w = StatusBadge(); qtbot.addWidget(w)
    assert "空闲" in w.text()


def test_badge_set_state_updates_text_and_color(qtbot):
    w = StatusBadge(); qtbot.addWidget(w)
    w.set_state("transfering")
    assert "传输" in w.text() or "操作" in w.text()
    assert w.current_color() == theme.AMBER
    w.set_state("done")
    assert w.current_color() == theme.SUCCESS
    w.set_state("error")
    assert w.current_color() == theme.ERROR
