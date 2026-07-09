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
    assert w.selected_port() == "COM9"


def test_no_lbs_device_none_selected(qtbot):
    ports = [_FakePort("COM3", "USB-SERIAL CH340")]
    w = PortSelector(lister=lambda: ports); qtbot.addWidget(w)
    # 无 LBS 设备：仍列出端口，但不强制选中 LBS（selected_port 返回第一个或 None 由实现定）
    assert w.selected_port() in ("COM3", None)


def test_refresh_updates_list(qtbot):
    state = {"ports": [_FakePort("COM3", "CH340")]}
    w = PortSelector(lister=lambda: state["ports"]); qtbot.addWidget(w)
    state["ports"] = [_FakePort("COM9", "LBS Serial (COM9)", vid=0x0483, pid=0x5740)]
    w.refresh()
    assert w.selected_port() == "COM9"


def test_empty_ports(qtbot):
    w = PortSelector(lister=lambda: []); qtbot.addWidget(w)
    assert w.selected_port() is None
