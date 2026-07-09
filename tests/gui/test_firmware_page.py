from lbs_firmware_studio.gui.pages.firmware_page import FirmwarePage
from lbs_firmware_studio.backend.profile import DeviceProfile
from pathlib import Path


def _profile():
    return DeviceProfile(name="NEW-AI", protocol="custom_frame",
                         folders=["app", "music", "boot", "config", "version"],
                         firmware_dir=Path("./products/NEW-AI/fwlib"))


def test_set_profile_shows_folders_and_dir(qtbot):
    w = FirmwarePage(); qtbot.addWidget(w)
    w.set_profile(_profile())
    txt = w.summary_text()
    assert "app" in txt and "music" in txt
    assert "NEW-AI/fwlib" in w.firmware_dir_text().replace("\\", "/")


def test_start_button_emits_signal(qtbot):
    w = FirmwarePage(); qtbot.addWidget(w)
    w.set_profile(_profile())
    with qtbot.waitSignal(w.start_requested, timeout=500):
        w.start_button().click()


def test_set_busy_disables_start(qtbot):
    w = FirmwarePage(); qtbot.addWidget(w)
    w.set_profile(_profile())
    w.set_busy(True)
    assert not w.start_button().isEnabled()
    w.set_busy(False)
    assert w.start_button().isEnabled()


def test_on_progress_updates_bar(qtbot):
    w = FirmwarePage(); qtbot.addWidget(w)
    w.on_progress(50, 100)
    assert w.progress_value() == 50


def test_on_state_updates_stage_text(qtbot):
    w = FirmwarePage(); qtbot.addWidget(w)
    w.on_state("transfering")
    assert "传输" in w.stage_text()


def test_on_log_appends(qtbot):
    w = FirmwarePage(); qtbot.addWidget(w)
    w.on_log("发送 A.wav")
    assert "A.wav" in w.log_text()
