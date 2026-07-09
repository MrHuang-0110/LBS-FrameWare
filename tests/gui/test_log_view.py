from lbs_firmware_studio.gui.widgets.log_view import LogView


def test_append_shows_message(qtbot):
    w = LogView(); qtbot.addWidget(w)
    w.append("打开 COM9", level="success")
    assert "打开 COM9" in w.plain_text()


def test_append_multiple_lines(qtbot):
    w = LogView(); qtbot.addWidget(w)
    w.append("a"); w.append("b"); w.append("c")
    txt = w.plain_text()
    assert "a" in txt and "b" in txt and "c" in txt


def test_append_has_timestamp(qtbot):
    w = LogView(); qtbot.addWidget(w)
    w.append("hello")
    # 时间戳形如 HH:MM:SS，检查有冒号分隔的时间
    import re
    assert re.search(r"\d{2}:\d{2}:\d{2}", w.plain_text())
