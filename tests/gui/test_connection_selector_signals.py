"""TDD 补全：connection_selector 新增行为（target_changed 信号、持久链路）的测试。"""
from lbs_firmware_studio.backend.serial_transport import SerialTransport
from lbs_firmware_studio.backend.ble_transport import BleTransport
from lbs_firmware_studio.gui.widgets.connection_selector import ConnectionSelector


class _FakePort:
    def __init__(self, device, desc):
        self.device = device; self.description = desc; self.vid = None; self.pid = None


# ---- target_changed 信号 ----

def test_target_changed_fires_on_port_inject(qtbot):
    """串口注入时 target_changed 信号被发射。"""
    cs = ConnectionSelector(port_lister=lambda: [], ble_scan=lambda t: [])
    fired = []
    cs.target_changed.connect(lambda: fired.append(True))
    cs._port.inject_ports([_FakePort("COM3", "LBS Serial")])
    assert fired == [True]


def test_target_changed_fires_on_kind_toggle(qtbot):
    """串口↔蓝牙切换时 target_changed 信号被发射。"""
    cs = ConnectionSelector(port_lister=lambda: [_FakePort("COM3", "x")],
                            ble_scan=lambda t: [])
    cs._port.inject_ports([_FakePort("COM3", "x")])
    fired = []
    cs.target_changed.connect(lambda: fired.append(True))
    cs.set_kind("ble")
    assert fired == [True]
    cs.set_kind("serial")
    assert fired == [True, True]


# ---- 持久链路 / 连接状态 ----

def test_persistent_transport_none_when_not_connected(qtbot):
    """未连接时 persistent_transport() 返回 None。"""
    cs = ConnectionSelector(port_lister=lambda: [], ble_scan=lambda t: [])
    assert cs.persistent_transport() is None
    assert cs.is_connected() is False


def test_make_transport_returns_serial_when_serial_selected(qtbot):
    """串口模式 make_transport 返回 SerialTransport，link_kind='serial'。"""
    cs = ConnectionSelector(port_lister=lambda: [_FakePort("COM3", "x")],
                            ble_scan=lambda t: [])
    cs._port.inject_ports([_FakePort("COM3", "x")])
    t = cs.make_transport()
    assert isinstance(t, SerialTransport)
    assert getattr(t, "link_kind", None) == "serial"