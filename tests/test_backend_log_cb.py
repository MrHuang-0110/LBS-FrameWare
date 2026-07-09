import pathlib, tempfile
from lbs_firmware_studio.backend.serial_transport import SerialTransport
from lbs_firmware_studio.backend.transfer_protocol import CustomFrameProtocol, YmodemProtocol
from tests.fakes import make_fake_serial_pair
from tests.simulator import DeviceSimulator


def test_custom_frame_log_cb_reports_filename():
    host_ser, dev_ser = make_fake_serial_pair()
    sim = DeviceSimulator(dev_ser, protocol="custom_frame"); sim.start()
    t = SerialTransport(host_ser); t.start_rx()
    logs = []
    try:
        proto = CustomFrameProtocol(chunk_size=248, ack_timeout=2.0,
                                    last_frame_ack="wait_2s", log_cb=logs.append)
        with tempfile.NamedTemporaryFile(suffix=".o", delete=False) as f:
            f.write(b"hello"); path = pathlib.Path(f.name)
        proto.send_file(t, path, lambda d, n: None, firmware=False)
        assert any(path.name in m for m in logs)
    finally:
        t.stop_rx(); sim.stop()


def test_log_cb_defaults_none_no_crash():
    # log_cb 默认 None 时不报错（协议保持纯净）
    proto = CustomFrameProtocol()
    assert proto.log_cb is None
    proto2 = YmodemProtocol()
    assert proto2.log_cb is None
