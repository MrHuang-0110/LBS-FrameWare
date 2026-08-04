import pathlib, tempfile
import pytest
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


def test_ymodem_debug_no_stdout_pollution(capsys):
    """完整 Ymodem 会话（enter_upgrade + send_file）不应向 stdout 打印 [DEBUG]，应走 log_cb。"""
    host_ser, dev_ser = make_fake_serial_pair()
    sim = DeviceSimulator(dev_ser, protocol="ymodem")
    sim.start()
    t = SerialTransport(host_ser); t.start_rx()
    logs = []
    try:
        proto = YmodemProtocol(block_size=1024, ack_timeout=5.0, log_cb=logs.append)
        proto.enter_upgrade_mode(t, firmware=True)  # 触发 enter_upgrade 的调试输出
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(b"\xAA" * 2048); path = pathlib.Path(f.name)
        proto.send_file(t, path, lambda d, n: None, firmware=True)
        assert "[DEBUG]" not in capsys.readouterr().out
        assert sim.received_files.get(path.name) == b"\xAA" * 2048
        assert any("DEBUG" in m for m in logs)  # 调试信息改走 log_cb
    finally:
        t.stop_rx(); sim.stop()


def test_ymodem_debug_timeout_no_stdout(capsys):
    """数据块 ACK 超时路径（_wait_control timeout 分支）也不得向 stdout 打印 [DEBUG]。"""
    import threading
    from lbs_firmware_studio.backend import ymodem as ym
    host_ser, dev_ser = make_fake_serial_pair()
    stop = threading.Event()

    def stub_device():
        dev_ser.write(bytes([ym.CRC_C]))
        dev_ser.timeout = 5.0
        dev_ser.read(3 + 128 + 2)
        dev_ser.write(bytes([ym.ACK, ym.CRC_C]))
        while not stop.is_set():
            dev_ser.read(64)  # 对数据块不回 ACK -> 触发超时

    th = threading.Thread(target=stub_device, daemon=True); th.start()
    t = SerialTransport(host_ser); t.start_rx()
    logs = []
    try:
        proto = YmodemProtocol(block_size=1024, ack_timeout=0.2, max_retries=3, log_cb=logs.append)
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(b"\xAA" * 2048); path = pathlib.Path(f.name)
        with pytest.raises(TimeoutError):
            proto.send_file(t, path, lambda d, n: None, firmware=True)
        assert "[DEBUG]" not in capsys.readouterr().out
    finally:
        stop.set(); t.stop_rx(); th.join(timeout=2)
