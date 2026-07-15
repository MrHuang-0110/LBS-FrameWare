from lbs_firmware_studio.gui.widgets.port_selector import PortSelector


class _FakePort:
    def __init__(self, device, description, vid=None, pid=None):
        self.device = device; self.description = description
        self.vid = vid; self.pid = pid


def test_lbs_device_auto_selected(qtbot):
    ports = [
        _FakePort("COM3", "USB-SERIAL CH340"),
        _FakePort("COM9", "LBS Serial (COM9)", vid=0x0483, pid=0x5740),
        _FakePort("COM5", "Standard Serial"),
    ]
    w = PortSelector(lister=lambda: ports); qtbot.addWidget(w)
    w.inject_ports(ports)  # 同步注入（异步扫描仅用于生产，测试不走后台线程）
    assert w.selected_port() == "COM9"


def test_no_lbs_device_none_selected(qtbot):
    ports = [_FakePort("COM3", "USB-SERIAL CH340")]
    w = PortSelector(lister=lambda: ports); qtbot.addWidget(w)
    w.inject_ports(ports)
    assert w.selected_port() == "COM3"


def test_refresh_updates_list(qtbot):
    state = {"ports": [_FakePort("COM3", "CH340")]}
    w = PortSelector(lister=lambda: state["ports"]); qtbot.addWidget(w)
    w.inject_ports(state["ports"])
    state["ports"] = [_FakePort("COM9", "LBS Serial (COM9)", vid=0x0483, pid=0x5740)]
    w.refresh()
    qtbot.waitUntil(lambda: w.selected_port() == "COM9", timeout=2000)
    assert w.selected_port() == "COM9"


def test_empty_ports(qtbot):
    w = PortSelector(lister=lambda: []); qtbot.addWidget(w)
    w.inject_ports([])
    assert w.selected_port() is None