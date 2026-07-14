import pytest
from PySide6.QtWidgets import QApplication
from lbs_firmware_studio.backend.profile import DeviceProfile


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _profile(protocol, ble_firmware):
    return DeviceProfile(name="X", protocol=protocol, firmware_dir=".",
                         ble_enabled=True, ble_firmware=ble_firmware)


def test_firmware_blocked_on_ble_when_not_supported(app, monkeypatch):
    from lbs_firmware_studio.gui.main_window import MainWindow
    w = MainWindow(_profile("custom_frame", False), {}, "products.yaml")
    # 强制连接方式为蓝牙
    w._conn.set_kind("ble")
    blocked = {"warned": False}
    monkeypatch.setattr("lbs_firmware_studio.gui.main_window.QMessageBox.warning",
                        lambda *a, **k: blocked.__setitem__("warned", True))
    w._start_firmware()
    assert blocked["warned"] is True        # 弹了"蓝牙不支持固件更新"
    assert w._busy is False                  # 未进入忙碌/未起线程


def test_firmware_allowed_on_ble_for_next_ai(app):
    from lbs_firmware_studio.gui.main_window import MainWindow
    w = MainWindow(_profile("ymodem", True), {}, "products.yaml")
    w._conn.set_kind("ble")
    # 无目标设备时应因"未选择设备"中止，而非因能力门禁——验证门禁不误伤 NEXT-AI
    assert w._ble_firmware_blocked() is False
