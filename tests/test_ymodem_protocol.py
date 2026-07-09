import pathlib, tempfile
from lbs_firmware_studio.backend.serial_transport import SerialTransport
from lbs_firmware_studio.backend.transfer_protocol import YmodemProtocol
from tests.fakes import make_fake_serial_pair
from tests.simulator import DeviceSimulator


def test_firmware_update_boot_ymodem():
    host_ser, dev_ser = make_fake_serial_pair()
    sim = DeviceSimulator(dev_ser, protocol="ymodem")
    sim.start()
    t = SerialTransport(host_ser); t.start_rx()
    try:
        proto = YmodemProtocol(block_size=1024, ack_timeout=5.0)
        proto.enter_upgrade_mode(t, firmware=True)  # 发 "ymodem update fmware\r\n"
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(b"\xAA" * 2048); path = pathlib.Path(f.name)
        progress = []
        proto.send_file(t, path, lambda d, n: progress.append((d, n)), firmware=True)
        assert sim.received_files.get(path.name) == b"\xAA" * 2048
    finally:
        t.stop_rx(); sim.stop()


def test_script_deploy_tolerates_json():
    host_ser, dev_ser = make_fake_serial_pair()
    sim = DeviceSimulator(dev_ser, protocol="ymodem", emit_json=True)
    sim.start()
    t = SerialTransport(host_ser); t.start_rx()
    try:
        proto = YmodemProtocol(block_size=1024, ack_timeout=5.0)
        proto.enter_upgrade_mode(t, firmware=False)  # 发 "ymodem\r\n"
        with tempfile.NamedTemporaryFile(suffix=".py.o", delete=False) as f:
            f.write(b"\xBB" * 500); path = pathlib.Path(f.name)
        proto.send_file(t, path, lambda d, n: None, firmware=False)
        assert sim.received_files.get(path.name) == b"\xBB" * 500
    finally:
        t.stop_rx(); sim.stop()
