from tests.fakes import make_fake_serial_pair
from tests.simulator import DeviceSimulator
from lbs_firmware_studio.backend import protocol_frame as pf


def test_simulator_acks_custom_frame_file():
    host_ser, dev_ser = make_fake_serial_pair()
    sim = DeviceSimulator(dev_ser, protocol="custom_frame")
    sim.start()
    try:
        # 发文件名帧 (app 文件夹)
        host_ser.write(pf.build_frame(pf.CMD_FILE_START, "demo.py.o".encode("gbk")))
        ack = pf.parse_frame(_read_frame(host_ser, timeout=2.0))
        assert ack is not None and ack[0] == pf.CMD_ACK
        # 发一帧数据 + 末帧
        host_ser.write(pf.build_frame(pf.CMD_FILE_DATA, b"hello"))
        assert pf.parse_frame(_read_frame(host_ser)) is not None
        host_ser.write(pf.build_frame(pf.CMD_FILE_END, b""))
        assert pf.parse_frame(_read_frame(host_ser)) is not None
        assert sim.received_files.get("demo.py.o") == b"hello"
    finally:
        sim.stop()


def _read_frame(host_ser, timeout=2.0):
    old = host_ser.timeout
    host_ser.timeout = timeout
    try:
        b = host_ser.read(1)
        while b and b[0] != pf.HEADER:
            b = host_ser.read(1)
        if not b:
            return b""
        fixed = host_ser.read(4)
        data_len = fixed[2] if len(fixed) == 4 else 0
        data = host_ser.read(data_len)
        tail = host_ser.read(2)
        return bytes([pf.HEADER]) + fixed + data + tail
    finally:
        host_ser.timeout = old
