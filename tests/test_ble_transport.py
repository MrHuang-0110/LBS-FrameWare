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


def test_reconnect_queue_rebuild_no_byte_loss():
    """T2-B4 确定性回归：重连时 start_notify 订阅生效后、_try_connect 重建 _rx_queue
    之前（订阅→替换窗口）到达的 notify 字节不得因队列替换而丢失。
    fake 的 start_notify 在返回前同步触发回调注入窗口字节——修复前字节落入旧队列，
    随后被 _try_connect 整体替换丢弃(read_byte 读不到)；修复后订阅前清空且不重建
    队列，字节保留在同一队列实例中可读。同步注入，无 sleep 竞态。
    """
    from tests.fakes import make_fake_ble_pair
    client, dev = make_fake_ble_pair()

    injections = {}
    call_no = {"n": 0}
    orig_start_notify = client.start_notify

    async def injecting_start_notify(uuid, cb):
        call_no["n"] += 1
        await orig_start_notify(uuid, cb)
        payload = injections.get(call_no["n"])
        if payload:
            cb(None, bytearray(payload))   # 订阅生效后立即注入（窗口内字节）

    client.start_notify = injecting_start_notify

    t = BleTransport(client_factory=lambda addr: client)
    t.open("addr")                         # 第 1 次订阅：无注入
    try:
        assert t.is_open is True
        injections[2] = b"\xAA\xBB"        # 第 2 次订阅（重连）注入窗口字节
        ok = t.wait_for_reopen("addr", 0, retries=3, delay=0.02, disappear_timeout=0.1)
        assert ok is True
        assert call_no["n"] == 2, "应恰好发生两次订阅(open + 重连)"
        assert t.read_byte(timeout=1.0) == 0xAA
        assert t.read_byte(timeout=1.0) == 0xBB
    finally:
        t.close()


def test_disconnect_callback_marks_not_open():
    """T2-B1 确定性回归：设备侧断开（关机/超距）触发 bleak disconnected 回调后，
    is_open 必须反映真实链路状态。修复前 _connected 不随设备侧断开更新，
    is_open 仍返回 True，上层误判链路健康。
    """
    from tests.fakes import make_fake_ble_pair
    client, dev = make_fake_ble_pair()
    t = BleTransport(client_factory=lambda addr: client)
    t.open("addr")
    try:
        assert t.is_open is True
        client.simulate_disconnect()   # 设备侧断开 -> 触发 disconnected 回调
        assert t.is_open is False, "设备侧断开后 is_open 应为 False"
    finally:
        # 设备侧断开后 _connected 为 False，close() 守卫跳过 disconnect，fake pump 不会
        # 被取消 -> 事件循环 GC 时泄漏 asyncio 任务。先显式 disconnect 取消 pump 再 close。
        t._run(client.disconnect())
        t.close()


def test_disconnect_callback_invoked_on_device_side_disconnect():
    """I1：BLE 顶层 set_disconnected_callback 注册的回调在设备侧断开（关机/超距）时被调用
    ——ConnectionSelector 据此实时切回未连接（与 SerialTransport 对齐）。"""
    from tests.fakes import make_fake_ble_pair
    client, dev = make_fake_ble_pair()
    t = BleTransport(client_factory=lambda addr: client)
    called = []
    t.set_disconnected_callback(lambda: called.append(True))
    t.open("addr")
    try:
        client.simulate_disconnect()   # 设备侧断开 -> 触发断开回调
        assert called, "设备侧断开后未调用 set_disconnected_callback 注册的回调"
    finally:
        t._run(client.disconnect())
        t.close()


def test_write_failure_marks_not_open():
    """T2-B1：write 抛异常（如设备断连导致 GATT 写失败）时同步置 _connected=False，
    is_open 随之变 False，避免上层继续按健康链路写入。
    """
    import pytest
    from tests.fakes import make_fake_ble_pair
    client, dev = make_fake_ble_pair()

    async def boom(uuid, data, response=False):
        raise OSError("device gone")

    client.write_gatt_char = boom
    t = BleTransport(client_factory=lambda addr: client)
    t.open("addr")
    try:
        assert t.is_open is True
        with pytest.raises(OSError):
            t.write(b"data")
        assert t.is_open is False, "write 异常后 is_open 应为 False"
    finally:
        # 同上：write 异常已置 _connected=False，close() 不会走 disconnect，
        # 需先显式 disconnect 取消 fake pump，避免 asyncio 任务泄漏警告。
        t._run(client.disconnect())
        t.close()


def test_close_is_idempotent_and_fast():
    """T2-B2 确定性回归：close() 不得让主线程长时间阻塞。

    1) 设备无响应（disconnect 命令挂起）时，close 内部 _run(self._disconnect())
       等待上限必须短——修复前 10s（+join 2s），UI 冻结最多 12s；修复后约 2s。
       构造挂起 disconnect 断言 close 总耗时 < 3s。
    2) 已断开场景（simulate_disconnect 后 _connected=False）连续 close 两次：
       幂等、快速、不抛错（Task 18 守卫 + close 幂等守卫）。

    挂起的 disconnect 任务在测试末用驱动事件循环的方式显式完成，避免
    asyncio pending 任务泄漏警告（与 Task 18 的 finally 清理模式同源）。
    """
    import time as _t
    from tests.fakes import make_fake_ble_pair

    # ---- 场景 1：无响应设备，close 必须快速返回 ----
    client, dev = make_fake_ble_pair()
    hang = asyncio.Event()

    async def hanging_disconnect():
        await hang.wait()   # 设备无响应：断开命令永不返回

    client.disconnect = hanging_disconnect
    t1 = BleTransport(client_factory=lambda addr: client)
    t1.open("addr")
    loop1 = t1._loop
    start = _t.monotonic()
    t1.close()
    dt = _t.monotonic() - start
    assert dt < 3.0, f"无响应设备 close 阻塞 {dt:.2f}s，超过 3s 阈值"
    # 清理：放行并驱动已停止的事件循环完成挂起的 disconnect，避免 pending 泄漏。
    pump = threading.Thread(target=loop1.run_forever, daemon=True)
    pump.start()
    loop1.call_soon_threadsafe(hang.set)    # 在 loop 线程放行挂起的 disconnect
    loop1.call_soon_threadsafe(loop1.stop)  # 之后停止 loop，退出 run_forever
    pump.join(timeout=2.0)
    loop1.close()

    # ---- 场景 2：已断开场景连续 close 两次：幂等、快速、不抛错 ----
    client2, dev2 = make_fake_ble_pair()
    t2 = BleTransport(client_factory=lambda addr: client2)
    t2.open("addr")
    try:
        client2.simulate_disconnect()   # 设备侧断开 -> _connected=False
        t2._run(client2.disconnect())   # 取消 fake pump（Task 18 清理模式）
        start = _t.monotonic()
        t2.close()
        dt1 = _t.monotonic() - start
        assert dt1 < 3.0, f"第一次 close 阻塞 {dt1:.2f}s，超过 3s 阈值"
    finally:
        t2.close()   # 幂等：已关闭后再次 close 不抛错
        assert t2._loop is None and t2._loop_thread is None


def test_handler_exception_does_not_interrupt_notify():
    """T2-B9：_on_notify 里 data_handler 抛异常不得中断后续 notify 处理。
    修复前异常从 fake pump 的 cb 调用冒泡 -> pump 的 asyncio 任务终止 ->
    后续设备字节不再回调（静默丢失）。"""
    import time as _t
    from tests.fakes import make_fake_ble_pair
    client, dev = make_fake_ble_pair()
    t = BleTransport(client_factory=lambda addr: client)
    received = []
    calls = {"n": 0}

    def flaky_handler(data):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("handler boom")
        received.append(data)

    t.open("addr")
    t.set_data_handler(flaky_handler)
    t.start_rx()
    try:
        dev.write(b"\x00")   # 第一次 notify -> handler 抛异常
        deadline = _t.monotonic() + 1.0
        while calls["n"] < 1 and _t.monotonic() < deadline:
            _t.sleep(0.01)
        assert calls["n"] >= 1, "第一次 notify 应已处理"
        dev.write(b"\x01\x02\x03")   # 后续 notify：应继续被处理
        deadline = _t.monotonic() + 1.0
        while b"".join(received) != b"\x01\x02\x03" and _t.monotonic() < deadline:
            _t.sleep(0.01)
        assert calls["n"] >= 2, "notify 应至少处理两次(首次异常+后续正常)"
        assert b"".join(received) == b"\x01\x02\x03", "handler 异常后后续 notify 仍应被处理"
    finally:
        t.stop_rx()
        t.close()
