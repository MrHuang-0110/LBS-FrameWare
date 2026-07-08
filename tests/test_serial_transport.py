from lbs_firmware_studio.backend.serial_transport import SerialTransport
from tests.fakes import make_fake_serial_pair


def test_read_byte_receives_written_byte():
    host_ser, dev_ser = make_fake_serial_pair()
    t = SerialTransport(host_ser)
    t.start_rx()
    try:
        dev_ser.write(b"\x41")
        assert t.read_byte(timeout=1.0) == 0x41
    finally:
        t.stop_rx()


def test_read_byte_returns_none_on_timeout():
    host_ser, _ = make_fake_serial_pair()
    t = SerialTransport(host_ser)
    t.start_rx()
    try:
        assert t.read_byte(timeout=0.1) is None
    finally:
        t.stop_rx()


def test_data_handler_receives_bytes():
    host_ser, dev_ser = make_fake_serial_pair()
    t = SerialTransport(host_ser)
    received = []
    t.set_data_handler(lambda data: received.append(data))
    t.start_rx()
    try:
        dev_ser.write(b"\x01\x02\x03")
        import time; time.sleep(0.2)
        assert b"".join(received) == b"\x01\x02\x03"
        # handler 模式下 read_byte 无数据
        assert t.read_byte(timeout=0.1) is None
    finally:
        t.stop_rx()


def test_write_sends_to_peer():
    host_ser, dev_ser = make_fake_serial_pair()
    t = SerialTransport(host_ser)
    try:
        t.write(b"ping")
        import time; time.sleep(0.1)
        assert dev_ser.read(4) == b"ping"
    finally:
        pass
