from lbs_firmware_studio.gui.dialogs.sensor_update_dialog import SensorUpdateDialog
from lbs_firmware_studio.backend.sensor_update import (
    KEEP, DEV_ID_COLOR, DEV_ID_BIG_MOTOR, build_sensor_update_frame,
)


def test_default_all_keep(qtbot):
    d = SensorUpdateDialog(); qtbot.addWidget(d)
    assert d.selected_ids() == [KEEP] * 8


def test_set_selection_reflected(qtbot):
    d = SensorUpdateDialog(); qtbot.addWidget(d)
    d.set_port_selection(0, DEV_ID_COLOR)
    d.set_port_selection(2, DEV_ID_BIG_MOTOR)
    assert d.selected_ids() == [DEV_ID_COLOR, KEEP, DEV_ID_BIG_MOTOR,
                                KEEP, KEEP, KEEP, KEEP, KEEP]


def test_submit_emits_correct_frame(qtbot):
    d = SensorUpdateDialog(); qtbot.addWidget(d)
    d.set_port_selection(0, DEV_ID_COLOR)
    got = []
    d.frame_ready.connect(lambda f: got.append(bytes(f)))
    d._submit()
    ids = [DEV_ID_COLOR] + [KEEP] * 7
    assert got == [build_sensor_update_frame(ids)]
