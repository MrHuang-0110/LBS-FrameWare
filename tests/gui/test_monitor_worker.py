from lbs_firmware_studio.gui.monitor_worker import MonitorWorker
from lbs_firmware_studio.backend.serial_transport import SerialTransport
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fakes import make_fake_serial_pair


def test_on_data_emits_parsed_frame(qtbot):
    w = MonitorWorker()
    got = []
    w.frame_parsed.connect(lambda d: got.append(d))
    w._on_data(b'{"version": 317}\r\n')
    assert got == [{"version": 317}]


def test_on_data_half_line_buffers(qtbot):
    w = MonitorWorker()
    got = []
    w.frame_parsed.connect(lambda d: got.append(d))
    w._on_data(b'{"a": ')
    assert got == []
    w._on_data(b'1}\r\n')
    assert got == [{"a": 1}]


def test_send_frame_writes_to_transport(qtbot):
    dev, host = make_fake_serial_pair()
    transport = SerialTransport(serial_obj=host)
    transport.open("COMX", 115200)
    w = MonitorWorker(transport=transport)
    w.send_frame(bytes([0x5A, 0x97, 0x98]))
    # 对端 dev 应收到这些字节
    got = [dev.read(1)[0] for _ in range(3)]
    assert got == [0x5A, 0x97, 0x98]


def test_start_emits_connected(qtbot):
    dev, host = make_fake_serial_pair()
    transport = SerialTransport(serial_obj=host)
    w = MonitorWorker(transport=transport)
    states = []
    w.state_changed.connect(lambda s: states.append(s))
    w.start("COMX", 115200)
    assert "connected" in states
    w.stop()
    assert "disconnected" in states


def test_start_on_reuses_persistent_link_without_closing(qtbot):
    """start_on 复用外部已连接链路：不 open、不 close，仅挂/摘 data_handler。"""
    dev, host = make_fake_serial_pair()
    transport = SerialTransport(serial_obj=host)
    transport.open("COMX", 115200)      # 外部（顶栏）已建连
    w = MonitorWorker()
    states = []
    w.state_changed.connect(lambda s: states.append(s))
    w.start_on(transport)
    assert "connected" in states
    assert transport.is_open            # 复用，未被关闭
    got = []
    w.frame_parsed.connect(lambda d: got.append(d))
    dev.write(b'{"version": 42}\r\n')
    qtbot.waitUntil(lambda: got == [{"version": 42}], timeout=1000)
    w.stop()
    assert "disconnected" in states
    assert transport.is_open            # stop 归还链路，不断开
