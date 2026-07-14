from lbs_firmware_studio.backend.ble_scanner import scan, BleDevice


class _FakeDev:
    def __init__(self, name, address, rssi):
        self.name = name; self.address = address; self.rssi = rssi


def test_scan_maps_devices():
    async def fake_discover(timeout):
        return [_FakeDev("ECB02", "AA:BB", -40), _FakeDev(None, "CC:DD", -70)]
    result = scan(timeout=0.1, discover=fake_discover)
    assert result == [
        BleDevice(name="ECB02", address="AA:BB", rssi=-40),
        BleDevice(name="", address="CC:DD", rssi=-70),
    ]


def test_scan_empty():
    async def fake_discover(timeout):
        return []
    assert scan(timeout=0.1, discover=fake_discover) == []


def test_scan_swallows_discover_error_returns_empty():
    async def boom(timeout):
        raise RuntimeError("adapter off")
    assert scan(timeout=0.1, discover=boom) == []
