from lbs_firmware_studio.gui.widgets.sensor_card import SensorCard


def test_empty_state_title_no_rows(qtbot):
    c = SensorCard(3); qtbot.addWidget(c)
    c.update(None, {})
    assert c.title_text() == "端口 3"
    assert c.rows() == []


def test_empty_state_shows_no_device_hint(qtbot):
    c = SensorCard(3); qtbot.addWidget(c)
    c.update(None, {})
    assert c.empty_hint() == "无设备"


def test_no_device_hint_cleared_when_sensor_present(qtbot):
    c = SensorCard(0); qtbot.addWidget(c)
    c.update("color", {"r": 1})
    assert c.empty_hint() == ""


def test_sensor_title_uses_chinese_name(qtbot):
    c = SensorCard(2); qtbot.addWidget(c)
    c.update("color", {"r": 10, "g": 20, "b": 30, "lux": 1615})
    assert c.title_text() == "端口 2 · 颜色"


def test_sensor_fields_as_rows(qtbot):
    c = SensorCard(0); qtbot.addWidget(c)
    c.update("ultrasion", {"cm": "255"})
    assert ("cm", "255") in c.rows()


def test_update_replaces_previous_rows(qtbot):
    c = SensorCard(1); qtbot.addWidget(c)
    c.update("touch", {"state": 1})
    c.update(None, {})                 # 设备拔出 -> 回到空态
    assert c.title_text() == "端口 1"
    assert c.rows() == []


def test_all_field_values_stringified(qtbot):
    c = SensorCard(0); qtbot.addWidget(c)
    c.update("gray", {"1": 100, "b1": 0})
    assert ("1", "100") in c.rows()
    assert ("b1", "0") in c.rows()
