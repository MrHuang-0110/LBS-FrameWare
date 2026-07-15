"""TDD 补全：PortSelector inject_ports + link_kind 标识的测试。"""
from lbs_firmware_studio.gui.widgets.port_selector import PortSelector
from lbs_firmware_studio.backend.serial_transport import SerialTransport
from lbs_firmware_studio.backend.ble_transport import BleTransport


class _FakePort:
    def __init__(self, device, description, vid=None, pid=None):
        self.device = device; self.description = description
        self.vid = vid; self.pid = pid


def test_empty_ports_inject(qtbot):
    """无可用串口时 inject_ports 注入空列表，selected_port 返回 None。"""
    w = PortSelector(lister=lambda: []); qtbot.addWidget(w)
    w.inject_ports([])
    assert w.selected_port() is None


def test_inject_ports_bypasses_async(qtbot):
    """inject_ports() 同步注入，绕过异步扫描。"""
    w = PortSelector(lister=lambda: []); qtbot.addWidget(w)
    w.inject_ports([_FakePort("COM9", "LBS Serial (COM9)", 0x0483, 0x5740)])
    assert w.selected_port() == "COM9"


def test_serial_transport_link_kind():
    assert SerialTransport.link_kind == "serial"


def test_ble_transport_link_kind():
    assert BleTransport.link_kind == "ble"