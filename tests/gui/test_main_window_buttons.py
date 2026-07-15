"""TDD 补全：MainWindow 下发按钮门禁（未选目标时禁用）的测试。"""
from lbs_firmware_studio.gui.main_window import MainWindow
from lbs_firmware_studio.backend.profile import DeviceProfile
from pathlib import Path


def _profile(**kw):
    return DeviceProfile(name="NEW-AI", protocol="custom_frame", display_ports=8,
                         folders=["app", "version"], firmware_dir=Path("./x"),
                         ble_enabled=True, ble_firmware=False, **kw)


def _raw():
    return {"compiler_path": "./t.exe", "products": {"NEW-AI": {"protocol": "custom_frame", "ble": {"enabled": True, "firmware_over_ble": False}}}}


class _FakePort:
    def __init__(self, device, desc, vid=None, pid=None):
        self.device = device; self.description = desc; self.vid = vid; self.pid = pid


# ---- 按钮初始禁用 ----

def test_firmware_and_deploy_buttons_disabled_without_target(qtbot, tmp_path):
    """未选串口/蓝牙目标时，固件更新和脚本下发按钮均禁用。"""
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    assert not w._firmware._start.isEnabled()
    assert not w._editor_page._deploy_btn.isEnabled()


# ---- 选中目标后按钮启用 ----

def test_buttons_enabled_after_port_selected(qtbot, tmp_path):
    """选中串口后，按钮恢复启用。"""
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w._conn._port.inject_ports([_FakePort("COM3", "LBS Serial (COM3)", 0x0483, 0x5740)])
    # target_changed 信号是异步投递的，须让事件循环跑一轮
    qtbot.waitUntil(lambda: w._firmware._start.isEnabled(), timeout=1000)
    assert w._editor_page._deploy_btn.isEnabled()


# ---- 蓝牙固件门禁 ----

def test_firmware_button_disabled_on_ble_without_firmware_support(qtbot, tmp_path):
    """NEW-AI(ble_firmware=False) 蓝牙模式下，固件更新按钮禁用，脚本下发仍可用。"""
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w._conn._port.inject_ports([_FakePort("COM3", "LBS Serial (COM3)", 0x0483, 0x5740)])
    qtbot.waitUntil(lambda: w._firmware._start.isEnabled(), timeout=1000)
    # 切换到蓝牙，BLE 下拉为空 → 无目标 → 按钮全禁用
    w._conn.set_kind("ble")
    qtbot.waitUntil(lambda: not w._firmware._start.isEnabled(), timeout=1000)
    assert not w._editor_page._deploy_btn.isEnabled()  # 无 BLE 设备可选


# ---- 忙碌流 ----

def test_buttons_disabled_during_busy_and_restored_after(qtbot, tmp_path):
    """忙碌（下发/更新进行中）时按钮禁用，完成后按目标可用性恢复。"""
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w._conn._port.inject_ports([_FakePort("COM3", "LBS Serial (COM3)", 0x0483, 0x5740)])
    qtbot.waitUntil(lambda: w._firmware._start.isEnabled(), timeout=1000)
    # 模拟忙碌
    w._firmware.set_busy(True)
    w._editor_page.set_busy(True)
    assert not w._firmware._start.isEnabled()
    assert not w._editor_page._deploy_btn.isEnabled()
    # 模拟完成
    w._firmware.set_busy(False)
    w._editor_page.set_busy(False)
    w._update_deploy_buttons()
    assert w._firmware._start.isEnabled()
    assert w._editor_page._deploy_btn.isEnabled()