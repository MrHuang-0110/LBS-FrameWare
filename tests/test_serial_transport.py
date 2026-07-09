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


def test_rx_loop_reads_available_not_fixed_64(monkeypatch):
    """RX 线程应读 in_waiting 可用字节，而非固定 read(64) 死等凑满/超时。
    锁定性能修复：8 字节 ACK 不应被 read(64) 的 timeout 拖延。"""
    import queue as _q
    calls = []

    class RecordingSerial:
        def __init__(self):
            self.is_open = True
            self.timeout = 0.1
            self._buf = bytearray([0x5A, 0x98, 0x97, 0x01, 0xFD, 0x01, 0x88, 0xA5])  # 8B ACK
        @property
        def in_waiting(self):
            return len(self._buf)
        def read(self, n=1):
            calls.append(n)
            out = bytes(self._buf[:n]); del self._buf[:n]
            return out

    ser = RecordingSerial()
    t = SerialTransport(ser)
    t.start_rx()
    try:
        import time
        got = []
        deadline = time.monotonic() + 1.0
        while len(got) < 8 and time.monotonic() < deadline:
            b = t.read_byte(timeout=0.2)
            if b is not None:
                got.append(b)
        assert got == [0x5A, 0x98, 0x97, 0x01, 0xFD, 0x01, 0x88, 0xA5]
        # 关键：读取时用的是 in_waiting 的字节数(8)，而不是固定 64
        assert 8 in calls
        assert 64 not in calls
    finally:
        t.stop_rx()


def test_wait_for_reopen_with_factory_rearms_rx():
    host_ser, dev_ser = make_fake_serial_pair()

    def reopen_factory(port, baud):
        host_ser.is_open = True  # 模拟同一 FakeSerial 重新枚举
        return host_ser

    # 端口始终存在(设备已在固件模式/不重枚举场景) -> 退化为直接打开
    t = SerialTransport(host_ser, reopen_factory=reopen_factory,
                        port_lister=lambda: {"COM_FAKE"})
    t.start_rx()
    try:
        ok = t.wait_for_reopen("COM_FAKE", 115200, retries=3, delay=0.05, disappear_timeout=0.2)
        assert ok is True
        # 重连后 RX 线程应已重新武装：对端写的字节能被 read_byte 收到
        dev_ser.write(b"\x42")
        assert t.read_byte(timeout=1.0) == 0x42
    finally:
        t.stop_rx()


def test_wait_for_reopen_waits_disappear_then_reappear():
    """真机场景：复位后端口先消失再重现，wait_for_reopen 必须等到重现后才打开。
    否则会打开即将失效的旧句柄 -> 首次写入 winerror 22。"""
    host_ser, _ = make_fake_serial_pair()
    # 模拟端口存在性时间线：前若干次探测=存在，中间=消失，之后=重现
    seq = iter([True, True, False, False, False, True, True, True, True, True])
    present = {"v": True}
    def lister():
        try:
            present["v"] = next(seq)
        except StopIteration:
            pass
        return {"COM_FAKE"} if present["v"] else set()
    opened_when = {"port_present_at_open": None}
    def reopen_factory(port, baud):
        opened_when["port_present_at_open"] = present["v"]  # 打开时端口应为「存在」
        host_ser.is_open = True
        return host_ser
    t = SerialTransport(host_ser, reopen_factory=reopen_factory, port_lister=lister)
    ok = t.wait_for_reopen("COM_FAKE", 115200, retries=5, delay=0.02, disappear_timeout=1.0)
    assert ok is True
    # 关键：打开发生在端口「重现(存在)」之后，而非消失窗口里
    assert opened_when["port_present_at_open"] is True


def test_wait_for_reopen_waits_post_delay(monkeypatch):
    """重开成功后必须等待 post_delay，让 USB CDC/设备初始化完成再返回（修 winerror 22）。"""
    import lbs_firmware_studio.backend.serial_transport as st
    host_ser, _ = make_fake_serial_pair()
    slept = []
    real_sleep = st.time.sleep
    monkeypatch.setattr(st.time, "sleep", lambda s: slept.append(s))

    def reopen_factory(port, baud):
        host_ser.is_open = True
        return host_ser

    t = SerialTransport(host_ser, reopen_factory=reopen_factory,
                        port_lister=lambda: {"COM_FAKE"})  # 端口常在->直接开
    ok = t.wait_for_reopen("COM_FAKE", 115200, retries=3, delay=2.0, post_delay=5.0,
                           disappear_timeout=0.0)
    assert ok is True
    # 成功那次的 5.0s 初始化等待必须发生在返回前
    assert 5.0 in slept


def test_wait_for_reopen_no_post_delay_when_zero(monkeypatch):
    """post_delay=0（如 YMODEM）时不额外等待。"""
    import lbs_firmware_studio.backend.serial_transport as st
    host_ser, _ = make_fake_serial_pair()
    slept = []
    monkeypatch.setattr(st.time, "sleep", lambda s: slept.append(s))

    def reopen_factory(port, baud):
        host_ser.is_open = True
        return host_ser

    t = SerialTransport(host_ser, reopen_factory=reopen_factory,
                        port_lister=lambda: {"COM_FAKE"})
    ok = t.wait_for_reopen("COM_FAKE", 115200, retries=3, delay=1.0, post_delay=0.0,
                           disappear_timeout=0.0)
    assert ok is True
    assert 0.0 not in slept  # post_delay=0 不触发额外 sleep(0)
