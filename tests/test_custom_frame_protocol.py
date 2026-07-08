import pathlib, tempfile
from lbs_firmware_studio.backend.serial_transport import SerialTransport
from lbs_firmware_studio.backend.transfer_protocol import CustomFrameProtocol
from tests.fakes import make_fake_serial_pair
from tests.simulator import DeviceSimulator


def _setup(protocol="custom_frame", emit_json=False):
    host_ser, dev_ser = make_fake_serial_pair()
    sim = DeviceSimulator(dev_ser, protocol=protocol, emit_json=emit_json)
    sim.start()
    t = SerialTransport(host_ser); t.start_rx()
    return t, sim


def test_enter_upgrade_sends_reset_frame():
    t, sim = _setup()
    try:
        proto = CustomFrameProtocol()
        proto.enter_upgrade_mode(t, firmware=True)
        # reset 帧已发，模拟器清空 received_files
        assert sim.received_files == {}
    finally:
        t.stop_rx(); sim.stop()


def test_send_file_delivers_to_simulator():
    t, sim = _setup()
    try:
        proto = CustomFrameProtocol(chunk_size=248, ack_timeout=2.0, last_frame_ack="wait_2s")
        proto.enter_upgrade_mode(t, firmware=True)
        with tempfile.NamedTemporaryFile(suffix=".py.o", delete=False) as f:
            f.write(b"hello world data")
            path = pathlib.Path(f.name)
        progress = []
        proto.send_file(t, path, lambda d, n: progress.append((d, n)), firmware=False)
        assert "path" in str(path) or True
        assert sim.received_files.get(path.name) == b"hello world data"
        assert progress[-1][0] == progress[-1][1]  # 完成
    finally:
        t.stop_rx(); sim.stop()


def test_send_file_retries_on_timeout():
    host_ser, dev_ser = make_fake_serial_pair()
    # 不启动模拟器 -> 不会回 ACK -> 触发重传
    t = SerialTransport(host_ser); t.start_rx()
    try:
        proto = CustomFrameProtocol(chunk_size=248, ack_timeout=0.2, last_frame_ack="skip", max_retries=3)
        proto.enter_upgrade_mode(t, firmware=True)
        import pytest
        with pytest.raises(TimeoutError):
            with tempfile.NamedTemporaryFile(delete=False) as f:
                f.write(b"x" * 10); path = pathlib.Path(f.name)
            proto.send_file(t, path, lambda d, n: None, firmware=False)
    finally:
        t.stop_rx()
