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
    txt = w.all_text()
    assert "NEW-AI" in txt and "SPARK-AI" in txt and "NEXT-AI" in txt


def test_card_click_emits_product(qtbot):
    w = StartupWindow(_profiles()); qtbot.addWidget(w)
    with qtbot.waitSignal(w.product_selected, timeout=500) as blocker:
        w.click_product("SPARK-AI")
    assert blocker.args == ["SPARK-AI"]
