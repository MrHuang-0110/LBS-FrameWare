import pytest
from PySide6.QtWidgets import QApplication
from lbs_firmware_studio.backend.ble_scanner import BleDevice
from lbs_firmware_studio.gui.widgets.connection_selector import ConnectionSelector


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _FakePort:
    def __init__(self, device, desc):
        self.device = device; self.description = desc; self.vid = None; self.pid = None


def test_default_kind_serial_and_target(app):
    cs = ConnectionSelector(port_lister=lambda: [_FakePort("COM3", "LBS Serial")],
                            ble_scan=lambda timeout=5.0: [])
    # 串口枚举已异步化，测试用同步注入
    cs._port.inject_ports([_FakePort("COM3", "LBS Serial")])
    assert cs.selected_kind() == "serial"
    assert cs.selected_target() == "COM3"
    assert cs.selected_name() is None


def test_switch_to_ble_lists_devices_and_target(app, qtbot):
    cs = ConnectionSelector(
        port_lister=lambda: [],
        ble_scan=lambda timeout=5.0: [BleDevice("ECB02", "AA:BB", -40)])
    cs._port.inject_ports([])
    cs.set_kind("ble")
    cs.scan_ble()                        # 触发后台扫描
    qtbot.waitUntil(lambda: cs._ble_combo.count() > 0, timeout=2000)  # 等后台填充完成
    assert cs.selected_kind() == "ble"
    assert cs.selected_target() == "AA:BB"
    assert cs.selected_name() == "ECB02"


def test_make_transport_by_kind(app, qtbot):
    from lbs_firmware_studio.backend.serial_transport import SerialTransport
    from lbs_firmware_studio.backend.ble_transport import BleTransport
    cs = ConnectionSelector(port_lister=lambda: [_FakePort("COM3", "x")],
                            ble_scan=lambda timeout=5.0: [BleDevice("ECB02", "AA:BB", -40)])
    cs._port.inject_ports([_FakePort("COM3", "x")])
    assert isinstance(cs.make_transport(), SerialTransport)
    cs.set_kind("ble"); cs.scan_ble()
    qtbot.waitUntil(lambda: cs._ble_combo.count() > 0, timeout=2000)  # 等后台填充完成
    assert isinstance(cs.make_transport(), BleTransport)
