import asyncio
import threading
from tests.fakes import make_fake_ble_pair


def test_fake_ble_client_bridges_write_and_notify():
    client, dev = make_fake_ble_pair()
    received = []

    async def scenario():
        await client.connect()
        await client.start_notify(client.services[0].uuid, lambda s, d: received.append(bytes(d)))
        # host 写 -> 设备端点收到
        await client.write_gatt_char(client.services[1].uuid, b"ping")
        await asyncio.sleep(0.05)
        assert dev.read(4) == b"ping"
        # 设备写 -> notify 回调收到
        dev.write(b"pong")
        await asyncio.sleep(0.05)
        await client.stop_notify(client.services[0].uuid)
        await client.disconnect()

    asyncio.run(scenario())
    assert b"".join(received) == b"pong"
    assert client.is_connected is False


from lbs_firmware_studio.backend.ble_transport import BleTransport, _find_transparent_chars


def test_find_transparent_chars_picks_notify_and_write():
    pairs = [("aaa", ["read"]), ("bbb", ["notify"]), ("ccc", ["write-without-response"])]
    notify, write, write_response = _find_transparent_chars(pairs)
    assert notify == "bbb"
    assert write == "ccc"
    assert write_response is False   # 仅 write-without-response -> 不用带响应写


def test_find_transparent_chars_prefers_response_write_when_supported():
    # 真机 ECB02：写特征值 fff2 支持 write/write-without-response -> 选带响应写做背压
    pairs = [("fff2", ["write", "write-without-response"]),
             ("fff1", ["notify", "write", "write-without-response", "read"])]
    notify, write, write_response = _find_transparent_chars(pairs)
    assert notify == "fff1"
    assert write == "fff2"
    assert write_response is True


def test_find_transparent_chars_raises_when_missing():
    import pytest
    with pytest.raises(RuntimeError):
        _find_transparent_chars([("aaa", ["read"])])


def test_open_then_read_byte_receives_device_bytes():
    from tests.fakes import make_fake_ble_pair
    client, dev = make_fake_ble_pair()
    t = BleTransport(client_factory=lambda addr: client)
    t.open("AA:BB:CC:DD:EE:FF")
    try:
        assert t.is_open is True
        dev.write(b"\x41")
        assert t.read_byte(timeout=1.0) == 0x41
    finally:
        t.close()


def test_read_byte_timeout_returns_none():
    from tests.fakes import make_fake_ble_pair
    client, _ = make_fake_ble_pair()
    t = BleTransport(client_factory=lambda addr: client)
    t.open("addr")
    try:
        assert t.read_byte(timeout=0.1) is None
    finally:
        t.close()


def test_write_chunks_by_mtu_and_preserves_bytes():
    from tests.fakes import make_fake_ble_pair
    # mtu_size=23 -> 有效分片 = 23-3 = 20
    client, dev = make_fake_ble_pair(mtu_size=23)
    calls = []
    orig = client.write_gatt_char

    async def spy(uuid, data, response=False):
        calls.append(len(data))
        await orig(uuid, data, response=response)

    client.write_gatt_char = spy
    t = BleTransport(client_factory=lambda addr: client)
    t.open("addr")
    try:
        payload = bytes(range(50))  # 50 字节 -> 20+20+10
        t.write(payload)
        import time as _t; _t.sleep(0.1)
        got = dev.read(50)
        assert got == payload
        assert calls == [20, 20, 10]   # 按 MTU-3 分片
    finally:
        t.close()


def test_set_data_handler_receives_bytes_and_read_byte_none():
    from tests.fakes import make_fake_ble_pair
    client, dev = make_fake_ble_pair()
    t = BleTransport(client_factory=lambda addr: client)
    received = []
    t.open("addr")
    t.set_data_handler(lambda d: received.append(d))
    t.start_rx()
    try:
        dev.write(b"\x01\x02\x03")
        import time as _t; _t.sleep(0.1)
        assert b"".join(received) == b"\x01\x02\x03"
        assert t.read_byte(timeout=0.1) is None   # handler 模式下 read_byte 无数据
    finally:
        t.stop_rx()
        t.close()


def test_close_stops_loop_thread():
    from tests.fakes import make_fake_ble_pair
    client, _ = make_fake_ble_pair()
    t = BleTransport(client_factory=lambda addr: client)
    t.open("addr")
    assert t._loop_thread is not None and t._loop_thread.is_alive()
    t.close()
    assert t.is_open is False
    assert t._loop_thread is None   # 已 join 清理，无悬挂线程


def test_wait_for_reopen_reconnects_same_address():
    from tests.fakes import make_fake_ble_pair
    client, dev = make_fake_ble_pair()
    t = BleTransport(client_factory=lambda addr: client)
    t.open("addr")
    try:
        ok = t.wait_for_reopen("addr", 0, retries=3, delay=0.02, disappear_timeout=0.1)
        assert ok is True
        dev.write(b"\x42")
        assert t.read_byte(timeout=1.0) == 0x42   # 重连后 notify 重新武装
    finally:
        t.close()


def test_wait_for_reopen_name_fallback_when_address_fails():
    from tests.fakes import make_fake_ble_pair
    from lbs_firmware_studio.backend.ble_scanner import BleDevice
    good_client, dev = make_fake_ble_pair()
    attempts = {"n": 0}

    def factory(addr):
        # 原地址"NEW"连接失败；兜底扫描给出的新地址"NEW2"成功
        if addr == "NEW2":
            return good_client
        attempts["n"] += 1
        raise RuntimeError("connect failed")

    def scanner(timeout):
        return [BleDevice(name="ECB02", address="NEW2", rssi=-40)]

    t = BleTransport(client_factory=factory, scanner=scanner, reconnect_name="ECB02")
    t._ensure_loop()
    ok = t.wait_for_reopen("NEW", 0, retries=2, delay=0.02, disappear_timeout=0.1)
    try:
        assert ok is True
        dev.write(b"\x43")
        assert t.read_byte(timeout=1.0) == 0x43
    finally:
        t.close()


def test_wait_for_reopen_returns_false_when_all_fail():
    def factory(addr):
        raise RuntimeError("connect failed")
    t = BleTransport(client_factory=factory)
    t._ensure_loop()
    ok = t.wait_for_reopen("addr", 0, retries=2, delay=0.02, disappear_timeout=0.1)
    assert ok is False
    t.close()


def test_connect_half_open_disconnects_client_on_failure():
    """连上但未发现透传特征值时，_connect 必须先 disconnect 再上抛，避免残留链路。"""
    import pytest

    class HalfOpenClient:
        def __init__(self):
            self.is_connected = False
            self.disconnect_called = False
            self.mtu_size = 23

        async def connect(self):
            self.is_connected = True

        async def disconnect(self):
            self.disconnect_called = True
            self.is_connected = False

        def get_characteristics(self):
            return [("aaa", ["read"])]  # 无 notify/write -> _find_transparent_chars 抛错

        async def start_notify(self, uuid, cb):
            pass

    client = HalfOpenClient()
    t = BleTransport(client_factory=lambda addr: client)
    with pytest.raises(RuntimeError):
        t.open("addr")
    assert t.is_open is False
    assert client.disconnect_called is True   # 半开链路已清理
    t.close()


def test_handler_switch_racing_notify_no_stranded_bytes():
    """T2-B3 确定性回归：notify 线程(此处直接调 _on_notify)读到 queue 模式并入队，
    与主线程 set_data_handler 切换（写 handler + 清空队列）交错时，切换完成后
    队列必须保持干净，切换瞬间的字节不得滞留队列（handler 收不到、下次切换才被丢）：
    - 修复前(无锁)：字节在 handler 已切换后仍入队滞留，qsize>0 —— 错路字节丢失
    - 修复后(锁串行化)：要么先入队随后被整体清空(切换前数据)，要么读到新 handler 直达收集器
    用 gated put 强制交错，确定性断言，无 sleep 竞态。
    """
    from tests.fakes import make_fake_ble_pair
    client, dev = make_fake_ble_pair()
    t = BleTransport(client_factory=lambda addr: client)
    t.open("addr")
    t.set_data_handler(None)   # queue 模式

    put_entered = threading.Event()
    release_put = threading.Event()
    orig_put = t._rx_queue.put

    def gated_put(item):
        put_entered.set()
        release_put.wait(timeout=5.0)
        return orig_put(item)

    t._rx_queue.put = gated_put   # 只 gate 本实例的入队

    errs = []

    def notifier():
        try:
            t._on_notify(None, bytearray(b"\x41\x42"))
        except Exception as e:
            errs.append(e)

    th = threading.Thread(target=notifier, daemon=True)
    th.start()
    assert put_entered.wait(timeout=5.0), "notify 应已进入入队路径"

    collected = []
    switched = threading.Event()

    def do_switch():
        try:
            t.set_data_handler(collected.append)
        except Exception as e:
            errs.append(e)
        finally:
            switched.set()

    sw = threading.Thread(target=do_switch, daemon=True)
    sw.start()
    release_put.set()   # 放行入队，制造「入队 <-> 清空队列」交错
    th.join(timeout=5.0)
    sw.join(timeout=5.0)

    assert not errs, f"不应抛异常: {errs}"
    assert switched.is_set(), "set_data_handler 必须完成"
    assert t._rx_queue.qsize() == 0, \
        f"handler 模式下队列不应滞留字节，实际 qsize={t._rx_queue.qsize()}"
    t.close()


def test_concurrent_notify_and_set_handler_no_corruption():
    """并发压力：真实链路上写线程持续触发 notify，主线程反复切换 handler。
    不抛异常；handler 模式下队列不滞留（切换瞬间无错路字节）；handler 收到的数据块完整。"""
    from tests.fakes import make_fake_ble_pair
    client, dev = make_fake_ble_pair()
    t = BleTransport(client_factory=lambda addr: client)
    received = []
    stop = threading.Event()
    errors = []

    def writer():
        try:
            while not stop.is_set():
                dev.write(b"\xAB" * 8)
        except Exception as e:
            errors.append(e)

    t.open("addr")
    t.set_data_handler(received.append)
    w = threading.Thread(target=writer, daemon=True)
    w.start()
    try:
        for _ in range(50):
            t.set_data_handler(None)              # 切回 queue 模式
            t.set_data_handler(received.append)   # 再挂 handler（清空残留）
        stop.set()
        w.join(timeout=5.0)
        import time as _t
        _t.sleep(0.2)   # 等泵把已写入的字节全部吐出
        assert t._rx_queue.qsize() == 0, \
            f"handler 模式下队列不应滞留字节，实际 qsize={t._rx_queue.qsize()}"
        assert received, "handler 应收到数据"
        assert all(b == b"\xAB" * len(b) for b in received), "数据块应完整无损坏"
    finally:
        stop.set()
        t.close()
    assert not errors, f"线程不应抛异常: {errors}"
