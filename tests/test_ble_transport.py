import asyncio
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
    notify, write = _find_transparent_chars(pairs)
    assert notify == "bbb"
    assert write == "ccc"


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
