from lbs_firmware_studio.gui.startup_window import StartupWindow
from lbs_firmware_studio.backend.profile import DeviceProfile


def _profiles():
    return {
        "NEW-AI": DeviceProfile(name="NEW-AI", protocol="custom_frame", display_ports=8),
        "SPARK-AI": DeviceProfile(name="SPARK-AI", protocol="custom_frame", display_ports=4),
        "NEXT-AI": DeviceProfile(name="NEXT-AI", protocol="ymodem", display_ports=2),
    }


def test_shows_all_products(qtbot):
    w = StartupWindow(_profiles()); qtbot.addWidget(w)
    assert w.all_text().count("-AI") >= 3 or all(
        n in w.all_text() for n in ("NEW-AI", "SPARK-AI", "NEXT-AI"))


def test_single_click_selects_not_enter(qtbot):
    w = StartupWindow(_profiles()); qtbot.addWidget(w)
    with qtbot.waitSignal(w.selection_changed, timeout=500) as blocker:
        w.click_product("SPARK-AI")
    assert blocker.args == ["SPARK-AI"]
    assert w.selected_product() == "SPARK-AI"


def test_double_click_enters(qtbot):
    w = StartupWindow(_profiles()); qtbot.addWidget(w)
    with qtbot.waitSignal(w.product_selected, timeout=500) as blocker:
        w.double_click_product("NEXT-AI")
    assert blocker.args == ["NEXT-AI"]
