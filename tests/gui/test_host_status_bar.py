from lbs_firmware_studio.gui.widgets.host_status_bar import HostStatusBar


def test_flat_field(qtbot):
    b = HostStatusBar(); qtbot.addWidget(b)
    b.set_fields([("版本", "version")])
    b.update_from({"version": 317})
    assert b.field_text("版本") == "317"


def test_nested_path_field(qtbot):
    b = HostStatusBar(); qtbot.addWidget(b)
    b.set_fields([("电量", "adc.bat")])
    b.update_from({"adc": {"bat": "82%"}})
    assert b.field_text("电量") == "82%"


def test_missing_shows_dashes(qtbot):
    b = HostStatusBar(); qtbot.addWidget(b)
    b.set_fields([("电量", "adc.bat")])
    b.update_from({"adc": {}})
    assert b.field_text("电量") == "--"


def test_imu_dict_combined(qtbot):
    b = HostStatusBar(); qtbot.addWidget(b)
    b.set_fields([("IMU", "mem")])
    b.update_from({"mem": {"yaw": "60.31", "pitch": "179.39", "roll": "-0.34"}})
    assert b.field_text("IMU") == "60.31/179.39/-0.34"
