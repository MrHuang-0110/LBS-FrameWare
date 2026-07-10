from pathlib import Path
from PySide6.QtCore import Qt
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


def test_real_double_click_does_not_crash(qtbot):
    # 回归：走真实 Qt 事件分发（不是 .emit() 捷径）。之前卡片在双击处理器里
    # 先 emit 后 super()，emit 触发切窗销毁了卡片，返回执行 super() 时命中
    # 已删除的 C++ 对象 -> RuntimeError。super() 先跑修复后此处应干净切窗。
    ctl = AppController(_profiles(), {"products": {}}, Path("products.yaml"))
    ctl.show_startup()
    qtbot.addWidget(ctl._startup)
    card = ctl._startup._cards["NEW-AI"]
    qtbot.mouseDClick(card, Qt.LeftButton)
    assert ctl.current_window_kind() == "main"
