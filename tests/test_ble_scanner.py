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


class _FakeAdv:
    def __init__(self, local_name, rssi):
        self.local_name = local_name; self.rssi = rssi


class _FakeBleakDev:
    """模拟 return_adv=True 时的 BLEDevice：name 可能 None。"""
    def __init__(self, name, address):
        self.name = name; self.address = address


def test_scan_maps_return_adv_dict():
    """return_adv=True 形态：dict[address -> (BLEDevice, AdvertisementData)]，
    name 优先 adv.local_name，rssi 取 adv.rssi。"""
    async def fake_discover(timeout):
        return {
            "AA:BB": (_FakeBleakDev(None, "AA:BB"), _FakeAdv("ECB02", -40)),
            "CC:DD": (_FakeBleakDev("DEVNAME", "CC:DD"), _FakeAdv(None, -70)),
        }
    result = scan(timeout=0.1, discover=fake_discover)
    assert BleDevice(name="ECB02", address="AA:BB", rssi=-40) in result
    # adv.local_name 为 None 时回退 dev.name
    assert BleDevice(name="DEVNAME", address="CC:DD", rssi=-70) in result
    assert len(result) == 2
