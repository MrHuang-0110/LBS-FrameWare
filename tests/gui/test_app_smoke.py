from pathlib import Path
from lbs_firmware_studio.gui.app import AppController
from lbs_firmware_studio.backend.profile import DeviceProfile


def _profiles():
    return {"NEW-AI": DeviceProfile(name="NEW-AI", protocol="custom_frame", display_ports=8,
                                    folders=["app"], firmware_dir=Path("./x"))}


def test_controller_starts_on_startup_window(qtbot):
    ctl = AppController(_profiles(), {"products": {}}, Path("products.yaml"))
    ctl.show_startup()
    assert ctl.current_window_kind() == "startup"


def test_controller_switches_to_main_on_select(qtbot):
    ctl = AppController(_profiles(), {"products": {}}, Path("products.yaml"))
    ctl.show_startup()
    ctl.on_product_selected("NEW-AI")
    assert ctl.current_window_kind() == "main"


def test_controller_back_to_startup_on_switch(qtbot):
    ctl = AppController(_profiles(), {"products": {}}, Path("products.yaml"))
    ctl.show_startup()
    ctl.on_product_selected("NEW-AI")
    ctl.on_switch_product()
    assert ctl.current_window_kind() == "startup"
