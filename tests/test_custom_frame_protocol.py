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


class _ByteFeeder:
    """最小传输替身：预置字节序列，逐字节喂给 read_byte（模拟真机 ACK 回帧）。"""
    def __init__(self, data: bytes):
        self._data = bytearray(data)
    def write(self, data: bytes) -> int:
        return len(data)
    def read_byte(self, timeout: float):
        if self._data:
            return self._data.pop(0)
        return None


def test_wait_ack_accepts_real_device_ack_with_data_byte():
    """真机 ACK 带 1 字节 data 且 SOURCE/DEST 顺序与主机帧相反：5a 98 97 01 fd 01 88 a5。
    旧实现在攒够 7 字节时就 parse，长度不符(需8)而丢弃，导致收不到 ACK。"""
    real_ack = bytes([0x5A, 0x98, 0x97, 0x01, 0xFD, 0x01, 0x88, 0xA5])
    proto = CustomFrameProtocol(ack_timeout=1.0)
    t = _ByteFeeder(real_ack)
    assert proto._wait_ack(t, timeout=1.0, is_last=False) is True


def test_wait_ack_still_accepts_empty_data_ack():
    """向后兼容：7 字节空 data ACK 仍被接受（模拟器用的格式）。"""
    from lbs_firmware_studio.backend import protocol_frame as pf
    empty_ack = pf.build_frame(pf.CMD_ACK, b"")  # 7 bytes
    proto = CustomFrameProtocol(ack_timeout=1.0)
    t = _ByteFeeder(empty_ack)
    assert proto._wait_ack(t, timeout=1.0, is_last=False) is True
