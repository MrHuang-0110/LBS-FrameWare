"""测试用虚拟串口：两个端点互连，模拟 pyserial 接口子集。"""
import queue


class FakeSerial:
    def __init__(self, rx_queue: queue.Queue, tx_queue: queue.Queue):
        self._rx = rx_queue
        self._tx = tx_queue
        self.is_open = True
        self.timeout = 1.0
        self.dtr = False
        self.rts = False
        self.write_timeout = 5.0

    def write(self, data: bytes) -> int:
        for b in data:
            self._tx.put(b)
        return len(data)

    def read(self, n: int = 1) -> bytes:
        try:
            first = self._rx.get(timeout=self.timeout)
        except queue.Empty:
            return b""
        out = bytearray([first])
        while len(out) < n:
            try:
                out.append(self._rx.get_nowait())
            except queue.Empty:
                break
        return bytes(out)

    @property
    def in_waiting(self) -> int:
        return self._rx.qsize()

    def reset_input_buffer(self) -> None:
        while True:
            try:
                self._rx.get_nowait()
            except queue.Empty:
                break

    def reset_output_buffer(self) -> None:
        pass

    def cancel_read(self) -> None:
        pass

    def close(self) -> None:
        self.is_open = False


def make_fake_serial_pair():
    a_rx: queue.Queue = queue.Queue()
    b_rx: queue.Queue = queue.Queue()
    a = FakeSerial(a_rx, b_rx)
    b = FakeSerial(b_rx, a_rx)
    return a, b


import asyncio


class FakeBleChar:
    """模拟 bleak 特征值：只需 uuid + properties 两个属性。"""
    def __init__(self, uuid: str, properties: list):
        self.uuid = uuid
        self.properties = properties


class FakeBleClient:
    """在 FakeSerial 上模拟 bleak 客户端：write_gatt_char->串口写，
    后台 asyncio pump 读设备回写字节->notify 回调。实现 BleTransport 依赖的客户端接口。"""
    def __init__(self, host_serial, mtu_size: int = 23,
                 notify_uuid: str = "ffe1", write_uuid: str = "ffe1"):
        self._ser = host_serial
        self._ser.timeout = 0.05
        self.mtu_size = mtu_size
        self.is_connected = False
        self._cb = None
        self._pump = None
        self.services = [
            FakeBleChar(notify_uuid, ["notify"]),
            FakeBleChar(write_uuid, ["write", "write-without-response"]),
        ]

    def get_characteristics(self):
        return [(ch.uuid, ch.properties) for ch in self.services]

    async def connect(self):
        self.is_connected = True

    async def disconnect(self):
        self.is_connected = False
        if self._pump is not None:
            self._pump.cancel()
            self._pump = None

    async def start_notify(self, uuid, cb):
        self._cb = cb
        self._pump = asyncio.ensure_future(self._run_pump())

    async def stop_notify(self, uuid):
        if self._pump is not None:
            self._pump.cancel()
            self._pump = None

    async def write_gatt_char(self, uuid, data, response: bool = False):
        self._ser.write(bytes(data))

    async def _run_pump(self):
        try:
            while True:
                n = self._ser.in_waiting
                if n:
                    data = self._ser.read(n)
                    if data and self._cb is not None:
                        self._cb(None, bytearray(data))
                await asyncio.sleep(0.005)
        except asyncio.CancelledError:
            pass


def make_fake_ble_pair(mtu_size: int = 23):
    """返回 (FakeBleClient, dev_serial)；dev_serial 交给 DeviceSimulator。"""
    host_ser, dev_ser = make_fake_serial_pair()
    return FakeBleClient(host_ser, mtu_size=mtu_size), dev_ser
