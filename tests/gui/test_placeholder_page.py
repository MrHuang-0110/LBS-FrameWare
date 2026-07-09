from lbs_firmware_studio.gui.pages.placeholder_page import PlaceholderPage


def test_placeholder_shows_title_and_coming_soon(qtbot):
    w = PlaceholderPage("数据监控"); qtbot.addWidget(w)
    assert "数据监控" in w.displayed_text()
    assert "即将推出" in w.displayed_text()
