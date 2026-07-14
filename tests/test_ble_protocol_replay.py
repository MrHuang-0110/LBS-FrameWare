"""协议一致性复跑：协议层经 BleTransport 收发，字节须与串口版逐字一致。"""
from pathlib import Path
from lbs_firmware_studio.backend.ble_transport import BleTransport
from lbs_firmware_studio.backend.transfer_protocol import CustomFrameProtocol, YmodemProtocol
from tests.fakes import make_fake_ble_pair
from tests.simulator import DeviceSimulator


def _progress(done, total):
    pass


def test_custom_frame_script_send_over_ble(tmp_path):
    client, dev = make_fake_ble_pair(mtu_size=247)
    sim = DeviceSimulator(dev, protocol="custom_frame")
    sim.start()
    t = BleTransport(client_factory=lambda addr: client)
    t.open("addr")
    try:
        f = tmp_path / "0.o"; f.write_bytes(bytes(range(200)))
        proto = CustomFrameProtocol(chunk_size=248)
        # 脚本下发用 folder 命令码之一；这里直接用 send_folder 的单文件路径
        proto.send_folder(t, tmp_path, "app", _progress)
        import time; time.sleep(0.2)
        assert sim.received_files.get("0.o") == bytes(range(200))
    finally:
        sim.stop(); t.close()


def test_ymodem_send_over_ble(tmp_path):
    client, dev = make_fake_ble_pair(mtu_size=247)
    sim = DeviceSimulator(dev, protocol="ymodem")
    sim.start()
    t = BleTransport(client_factory=lambda addr: client)
    t.open("addr")
    try:
        f = tmp_path / "fw.bin"; f.write_bytes(bytes([0xAB]) * 300)
        proto = YmodemProtocol(block_size=1024)
        proto.enter_upgrade_mode(t, firmware=True, enter_cmd=b"ymodem update fmware\r\n")
        proto.send_file(t, f, _progress, firmware=True)
        import time; time.sleep(0.3)
        assert sim.received_files.get("fw.bin") == bytes([0xAB]) * 300
    finally:
        sim.stop(); t.close()
