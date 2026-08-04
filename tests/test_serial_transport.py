import pytest
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


def test_rx_loop_exits_on_persistent_read_error():
    """T2-S1：串口拔出后 in_waiting/read 持续抛错，RX 线程应在连续异常达上限后退出，
    而非无日志 50ms 忙循环空转。"""
    import time

    class UnpluggedSerial:
        """模拟串口已拔出：in_waiting 与 read 均持续抛 OSError。"""
        is_open = False
        timeout = 0.01
        dtr = False
        rts = False

        @property
        def in_waiting(self):
            raise OSError(22, "The device does not recognize the command")

        def read(self, n=1):
            raise OSError(22, "The device does not recognize the command")

    t = SerialTransport(UnpluggedSerial())
    t.start_rx()
    # 不依赖精确 sleep：短超时轮询线程存活状态（避免 flaky）
    deadline = time.monotonic() + 2.0
    while (t._thread is None or t._thread.is_alive()) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert t._thread is not None and not t._thread.is_alive(), "RX 线程在持续读错误下仍存活(忙循环)"


def test_rx_loop_recovers_after_transient_read_error():
    """偶发一次读取异常不应退出线程（连续计数重置），恢复后正常收字节。"""
    import time
    host_ser, dev_ser = make_fake_serial_pair()

    class FlakySerial:
        is_open = True
        timeout = 0.01

        def __init__(self):
            self._inner = host_ser
            self.fail_next = True

        @property
        def in_waiting(self):
            if self.fail_next:
                self.fail_next = False
                raise OSError("transient")
            return self._inner.in_waiting

        def read(self, n=1):
            return self._inner.read(n)

    t = SerialTransport(FlakySerial())
    t.start_rx()
    try:
        dev_ser.write(b"\x43")
        assert t.read_byte(timeout=1.0) == 0x43
        # 仅一次异常未达退出阈值：线程应仍存活
        assert t._thread is not None and t._thread.is_alive()
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


def test_handler_exception_does_not_kill_rx_thread():
    """T2-S3：data_handler 抛异常不得杀死 RX 线程（daemon），后续数据仍可达。
    修复前异常冒出 _rx_loop -> daemon RX 线程死亡 -> 无任何迹象、后续字节丢失。
    注意：handler 异常是「记日志继续」，不得计入 T2-S1 的 read 连续错误阈值。"""
    import time
    host_ser, dev_ser = make_fake_serial_pair()
    t = SerialTransport(host_ser)
    received = []
    calls = {"n": 0}

    def flaky_handler(data):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("handler boom")
        received.append(data)

    t.set_data_handler(flaky_handler)
    t.start_rx()
    try:
        dev_ser.write(b"\x00")   # 触发第一次 handler 调用 -> 抛异常
        deadline = time.monotonic() + 1.0
        while calls["n"] < 1 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert calls["n"] >= 1, "第一次 handler 调用应已发生"
        dev_ser.write(b"\x01\x02\x03")   # 后续数据：handler 应正常收集
        deadline = time.monotonic() + 1.0
        while b"".join(received) != b"\x01\x02\x03" and time.monotonic() < deadline:
            time.sleep(0.01)
        assert calls["n"] >= 2, "handler 应至少被调用两次(首抛异常+后续正常)"
        assert b"".join(received) == b"\x01\x02\x03", "handler 异常后后续数据仍应可达"
        assert t._thread is not None and t._thread.is_alive(), "handler 异常后 RX 线程应仍存活"
    finally:
        t.stop_rx()


def test_write_after_close_raises_clear_error():
    """T2-S4：write 前置检查必须含 is_open。close 后端口已关/拔出时 write 应抛
    清晰的 RuntimeError（含"未打开"提示），而不是把底层异常（winerror 22 等）
    冒给上层。修复前 write 只查 `_serial is None`，close 后仍直接调底层 write。"""
    host_ser, _ = make_fake_serial_pair()
    t = SerialTransport(host_ser)
    t.write(b"ok")      # 打开状态正常写入
    t.close()           # 关闭后 is_open=False
    with pytest.raises(RuntimeError, match="未打开"):
        t.write(b"ping")


def test_port_present_exception_contained():
    """T2-S5：端口枚举异常（comports/lister 抛错）不得冒出 wait_for_reopen，
    应按「端口不存在」处理、让 wait_for_reopen 走失败返回 False。
    修复前 _port_present 无 try/except，USB 枚举抛错直接冒出 wait_for_reopen。"""
    host_ser, _ = make_fake_serial_pair()
    probe_calls = {"n": 0}

    def boom_lister():
        probe_calls["n"] += 1
        raise OSError(123, "USB enumeration failed")

    def reopen_factory(port, baud):
        raise OSError("reopen failed")

    t = SerialTransport(host_ser, reopen_factory=reopen_factory, port_lister=boom_lister)
    ok = t.wait_for_reopen("COM_FAKE", 115200, retries=2, delay=0.01, disappear_timeout=0.1)
    assert ok is False          # 枚举异常被吞掉，按失败返回
    assert probe_calls["n"] >= 1  # 枚举确实被探测过（异常来自枚举）


def test_port_present_comports_exception_contained(monkeypatch):
    """T2-S5 的 comports() 分支：pyserial 枚举抛错时 _port_present 返回 False 不冒泡。"""
    import lbs_firmware_studio.backend.serial_transport as st
    if st.serial is None:
        pytest.skip("pyserial 未安装，跳过 comports() 分支")

    def boom():
        raise OSError(123, "USB enumeration failed")

    monkeypatch.setattr(st.serial.tools.list_ports, "comports", boom)
    t = SerialTransport()  # 不注入 port_lister，走 pyserial 探测路径
    assert t._port_present("COM_FAKE") is False
