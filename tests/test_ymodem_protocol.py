import pathlib, tempfile
import pytest
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


def test_seq_wraps_256_not_skip_0():
    """YMODEM seq 回绕必须对齐 mod-256：第 255 块之后 seq=0，不得跳到 1。

    发送 256 个 128B 块（32KB）跨越 255 边界；模拟器新增 seq 连续性校验
    （不匹配回 NAK 请求重发），修复前第 256 块发 seq=1（期望 0）会触发
    NAK→重发仍不匹配→超时，本测试因此失败。
    """
    host_ser, dev_ser = make_fake_serial_pair()
    sim = DeviceSimulator(dev_ser, protocol="ymodem")
    sim.start()
    t = SerialTransport(host_ser); t.start_rx()
    try:
        proto = YmodemProtocol(block_size=128, ack_timeout=0.3)
        proto.enter_upgrade_mode(t, firmware=True)
        data = b"\xAA" * (128 * 256)  # 32768B = 256 块，覆盖 seq 255→0 回绕
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(data); path = pathlib.Path(f.name)
        proto.send_file(t, path, lambda d, n: None, firmware=True)
        assert sim.received_files.get(path.name) == data
        assert len(sim.received_files[path.name]) == 128 * 256
    finally:
        t.stop_rx(); sim.stop()


def test_firmware_data_block_timeout_raises():
    """固件传输中数据块超时必须抛错，不得因 usb_quick_exit 静默视为成功。"""
    import threading
    from lbs_firmware_studio.backend import ymodem as ym
    host_ser, dev_ser = make_fake_serial_pair()

    stop = threading.Event()

    def stub_device():
        # 发 'C' 请求文件头
        dev_ser.write(bytes([ym.CRC_C]))
        # 读文件头包 (SOH=128 -> 3+128+2 字节)
        dev_ser.timeout = 5.0
        dev_ser.read(3 + 128 + 2)
        # ACK 文件头并再发 'C'，让主机进入数据阶段
        dev_ser.write(bytes([ym.ACK, ym.CRC_C]))
        # 之后对任何数据块都不回 ACK -> 触发超时
        while not stop.is_set():
            dev_ser.read(64)

    th = threading.Thread(target=stub_device, daemon=True); th.start()
    t = SerialTransport(host_ser); t.start_rx()
    try:
        proto = YmodemProtocol(block_size=1024, ack_timeout=0.2, max_retries=3, usb_quick_exit=True)
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(b"\xAA" * 2048); path = pathlib.Path(f.name)
        with pytest.raises(TimeoutError):
            proto.send_file(t, path, lambda d, n: None, firmware=True)
    finally:
        stop.set(); t.stop_rx(); th.join(timeout=2)
