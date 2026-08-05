"""AppController 冒烟测试：启动直入主窗，默认产品 NEW-AI，无 startup 流转。"""
from pathlib import Path
from lbs_firmware_studio.gui.app import AppController
from lbs_firmware_studio.backend.profile import DeviceProfile


def _profiles():
    return {
        "NEW-AI": DeviceProfile(name="NEW-AI", protocol="custom_frame", display_ports=8,
                                folders=["app"], firmware_dir=Path("./x")),
        "SPARK-AI": DeviceProfile(name="SPARK-AI", protocol="custom_frame", display_ports=4,
                                  folders=["app"], firmware_dir=Path("./x")),
    }


def test_launch_opens_main_window(qtbot):
    """launch() 直入主窗；current_window_kind() 反映主窗态；默认产品为 NEW-AI。"""
    ctl = AppController(_profiles(), {"products": {}}, Path("products.yaml"))
    ctl.launch()
    qtbot.addWidget(ctl._main)
    assert ctl.current_window_kind() == "main"
    assert ctl._main.header_text() == "NEW-AI"


def test_no_startup_state(qtbot):
    """AppController 不再有 startup 流转：未 launch 时无窗口，且无 _startup 状态。"""
    ctl = AppController(_profiles(), {"products": {}}, Path("products.yaml"))
    assert ctl.current_window_kind() is None
    assert not hasattr(ctl, "_startup")
