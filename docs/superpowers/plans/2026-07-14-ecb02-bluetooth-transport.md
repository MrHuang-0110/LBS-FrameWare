# ECB02 蓝牙(BLE)传输通道 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 LBS Firmware Studio 增加通过 ECB02 蓝牙芯片(BLE/GATT)连接设备的传输通道，与串口等价，用于脚本下发/数据监控(全产品)与固件更新(仅 NEXT-AI)。

**Architecture:** 新建 `BleTransport`，方法签名与现有 `SerialTransport` 逐一对等（鸭子类型），协议层/编排层零改动。BLE 的异步特性(bleak/asyncio)封装在 transport 内部的专用事件循环线程里，notify 回调把字节推入与 SerialTransport 相同的队列/回调模型。GUI 通过统一的 `ConnectionSelector` 构造串口或蓝牙 transport。

**Tech Stack:** Python 3.13、bleak(BLE)、PySide6、pytest、pytest-qt。平台 Windows，解释器一律用 `python`。

## Global Constraints

- 平台 Windows + Python 3.13，测试用 `python -m pytest`（**非** python3）。
- 协议字节必须与真机逐字一致：自定义帧头 `0x5A`/checksum、YMODEM CRC16-XMODEM，保留 `"ymodem update fmware"` 拼写。
- 协议层/编排层**零改动**：`transfer_protocol.py`、`deployer.py`、`protocol_frame.py`、`ymodem.py`、`serial_transport.py` 不得修改。
- 绝不碰真硬件（串口/蓝牙）做测试；BLE 测试用 `FakeBleClient` + 复用 `tests/simulator.py` 的 `DeviceSimulator`。
- GUI 层只做界面，绝不直接拼协议帧/读写链路；设备操作经 worker → deployer。
- 深色主题禁硬编码色值，取 `theme.*`。
- GUI 测试**按文件单独跑**：`python -m pytest tests/gui/test_X.py -q`；多 QThread 在同进程 teardown 可能段错误(exit 9)，断言全过即视为通过。
- 能力约束**配置驱动**：custom_frame(NEW-AI/SPARK-AI) 蓝牙 `firmware_over_ble: false`；NEXT-AI `true`。

---

## File Structure

**新增文件：**
- `src/lbs_firmware_studio/backend/ble_transport.py` — BleTransport + RealBleakClient 包装 + 特征值发现。
- `src/lbs_firmware_studio/backend/ble_scanner.py` — BleDevice 数据类 + scan()。
- `src/lbs_firmware_studio/gui/widgets/connection_selector.py` — 串口/蓝牙统一入口控件。
- `tests/test_ble_transport.py`、`tests/test_ble_scanner.py`、`tests/test_ble_protocol_replay.py`、`tests/gui/test_connection_selector.py`。

**修改文件：**
- `tests/fakes.py` — 加 `FakeBleClient` + `FakeBleChar` + `make_fake_ble_pair`。
- `pyproject.toml` — 加 `bleak` 依赖。
- `src/lbs_firmware_studio/backend/profile.py` — DeviceProfile 加 `ble_enabled`/`ble_firmware` + 加载。
- `products.yaml` — 各产品加 `ble` 段。
- `src/lbs_firmware_studio/gui/main_window.py` — transport 由 ConnectionSelector 构造 + 固件能力门禁。
- `tests/test_profile.py` — ble 字段测试。
- `LBS-Firmware-Studio.spec` — bleak hiddenimports。

**客户端接口契约（BleTransport 依赖的 duck-typed client；RealBleakClient 与 FakeBleClient 都实现）：**
```
async connect()
async disconnect()
async start_notify(uuid: str, cb)          # cb(sender, data: bytearray)
async stop_notify(uuid: str)
async write_gatt_char(uuid: str, data: bytes, response: bool = False)
get_characteristics() -> list[tuple[str, list[str]]]   # (uuid, properties)
mtu_size: int
is_connected: bool
```

---

## Task 1: 添加 bleak 依赖

**Files:**
- Modify: `pyproject.toml:5`

**Interfaces:**
- Produces: 运行时依赖 `bleak`，供后续 Task 3/7 的默认客户端与扫描器使用。

- [ ] **Step 1: 修改 pyproject.toml 依赖列表**

把第 5 行的 dependencies 加入 bleak：
```toml
dependencies = ["pyserial>=3.5", "PyYAML>=6.0", "qtawesome>=1.3", "PySide6>=6.11", "bleak>=0.22"]
```

- [ ] **Step 2: 安装依赖**

Run: `python -m pip install -e .`
Expected: 成功安装 bleak 及其 Windows 后端(winrt-*)，无报错。

- [ ] **Step 3: 验证可导入**

Run: `python -c "import bleak; print(bleak.__version__)"`
Expected: 打印版本号（如 `0.22.x`），无异常。

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: 添加 bleak 依赖(BLE 传输通道)"
```

---

## Task 2: FakeBleClient 测试基础设施

FakeBleClient 复用 `make_fake_serial_pair()` 桥接到 `DeviceSimulator`：host 侧 `write_gatt_char` 把字节写给设备串口端点，一个 asyncio 轮询 pump 读设备回写的字节并触发 notify 回调。多个后续任务(3/4/5/9)消费它。

**Files:**
- Modify: `tests/fakes.py`
- Test: `tests/test_ble_transport.py`（本任务只加一个自检测试）

**Interfaces:**
- Consumes: 现有 `make_fake_serial_pair()`。
- Produces:
  - `class FakeBleChar` — 属性 `uuid: str`、`properties: list[str]`。
  - `class FakeBleClient(host_serial, mtu_size=23, notify_uuid="ffe1", write_uuid="ffe1")` — 实现上文客户端接口契约。
  - `make_fake_ble_pair(mtu_size=23) -> (FakeBleClient, dev_serial)` — dev_serial 交给 `DeviceSimulator`。

- [ ] **Step 1: 写失败测试**

在 `tests/test_ble_transport.py` 新建：
```python
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
```

- [ ] **Step 2: 运行验证失败**

Run: `python -m pytest tests/test_ble_transport.py::test_fake_ble_client_bridges_write_and_notify -v`
Expected: FAIL，`ImportError: cannot import name 'make_fake_ble_pair'`。

- [ ] **Step 3: 实现 FakeBleClient**

在 `tests/fakes.py` 末尾追加：
```python
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
```

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/test_ble_transport.py::test_fake_ble_client_bridges_write_and_notify -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add tests/fakes.py tests/test_ble_transport.py
git commit -m "test: FakeBleClient 桥接 DeviceSimulator 的测试基础设施"
```

---

## Task 3: BleTransport — 连接、特征值发现、read_byte(队列模式)

**Files:**
- Create: `src/lbs_firmware_studio/backend/ble_transport.py`
- Test: `tests/test_ble_transport.py`

**Interfaces:**
- Consumes: `FakeBleClient`(Task 2)、上文客户端接口契约。
- Produces:
  - `class BleTransport(client_factory=None, scanner=None, reconnect_name=None)`
  - `open(port, baud=0)` — port=BLE 地址；连接 + 发现透传特征值 + 订阅 notify。
  - `read_byte(timeout) -> int | None` — 从 `_rx_queue` 取（与 SerialTransport 一致）。
  - `write(data) -> int`（Task 4 完善分片）、`is_open` 属性。
  - `_find_transparent_chars(pairs) -> (notify_uuid, write_uuid)` 模块函数。
  - `client_factory(address) -> client`；缺省用 bleak（本任务给出带 import guard 的缺省）。

- [ ] **Step 1: 写失败测试**

在 `tests/test_ble_transport.py` 追加：
```python
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
```

- [ ] **Step 2: 运行验证失败**

Run: `python -m pytest tests/test_ble_transport.py -k "find_transparent or read_byte or open_then" -v`
Expected: FAIL，`ModuleNotFoundError: ble_transport`。

- [ ] **Step 3: 实现 BleTransport 骨架**

创建 `src/lbs_firmware_studio/backend/ble_transport.py`：
```python
"""蓝牙(BLE)传输层：方法签名与 SerialTransport 对等（鸭子类型），
把 bleak(asyncio) 封装进专用事件循环线程，notify 回调推入队列/回调，
使协议层 read_byte 拉取逻辑零改动。"""
from __future__ import annotations
import asyncio
import queue
import threading
import time
from typing import Callable

try:
    from bleak import BleakClient
except ImportError:  # 未安装 bleak：串口功能不受影响，选蓝牙时才报错
    BleakClient = None


def _find_transparent_chars(pairs) -> tuple[str, str]:
    """从 [(uuid, properties)] 里挑一个 notify(收) + 一个 write(发) 特征值。"""
    notify_uuid = write_uuid = None
    for uuid, props in pairs:
        if notify_uuid is None and ("notify" in props or "indicate" in props):
            notify_uuid = uuid
        if write_uuid is None and ("write" in props or "write-without-response" in props):
            write_uuid = uuid
    if notify_uuid is None or write_uuid is None:
        raise RuntimeError("未发现可透传特征值")
    return notify_uuid, write_uuid


class _RealBleakClient:
    """生产用：包装 bleak.BleakClient，实现 BleTransport 依赖的客户端接口。"""
    def __init__(self, address: str):
        self._c = BleakClient(address)

    @property
    def is_connected(self) -> bool:
        return self._c.is_connected

    @property
    def mtu_size(self) -> int:
        return getattr(self._c, "mtu_size", 23)

    async def connect(self):
        await self._c.connect()

    async def disconnect(self):
        await self._c.disconnect()

    async def start_notify(self, uuid, cb):
        await self._c.start_notify(uuid, cb)

    async def stop_notify(self, uuid):
        await self._c.stop_notify(uuid)

    async def write_gatt_char(self, uuid, data, response: bool = False):
        await self._c.write_gatt_char(uuid, data, response=response)

    def get_characteristics(self):
        pairs = []
        for svc in self._c.services:
            for ch in svc.characteristics:
                pairs.append((ch.uuid, list(ch.properties)))
        return pairs


def _default_client_factory(address: str):
    if BleakClient is None:
        raise RuntimeError("未安装蓝牙支持(bleak)")
    return _RealBleakClient(address)


class BleTransport:
    def __init__(self, client_factory: "Callable[[str], object] | None" = None,
                 scanner: "Callable[[float], list] | None" = None,
                 reconnect_name: "str | None" = None):
        self._client_factory = client_factory or _default_client_factory
        self._scanner = scanner
        self._reconnect_name = reconnect_name
        self._address: str | None = None
        self._client = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None
        self._rx_queue: queue.Queue[int] = queue.Queue()
        self._data_handler: Callable[[bytes], None] | None = None
        self._notify_uuid: str | None = None
        self._write_uuid: str | None = None
        self._mtu = 20
        self._connected = False

    # ---- 事件循环线程 ----
    def _ensure_loop(self) -> None:
        if self._loop is not None and self._loop_thread and self._loop_thread.is_alive():
            return
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._loop_thread.start()

    def _run(self, coro, timeout: float = 30.0):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout=timeout)

    # ---- 连接 ----
    def open(self, port: str, baud: int = 0) -> None:
        self._address = port
        self._ensure_loop()
        self._run(self._connect())

    async def _connect(self) -> None:
        self._client = self._client_factory(self._address)
        await self._client.connect()
        self._notify_uuid, self._write_uuid = _find_transparent_chars(
            self._client.get_characteristics())
        self._mtu = max(int(getattr(self._client, "mtu_size", 23)) - 3, 20)
        await self._client.start_notify(self._notify_uuid, self._on_notify)
        self._connected = True

    def _on_notify(self, sender, data) -> None:
        b = bytes(data)
        if self._data_handler is not None:
            self._data_handler(b)
        else:
            for byte in b:
                self._rx_queue.put(byte)

    @property
    def is_open(self) -> bool:
        return self._connected

    def read_byte(self, timeout: float) -> int | None:
        if self._data_handler is not None:
            return None
        try:
            return self._rx_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def write(self, data: bytes) -> int:
        if not self._connected:
            raise RuntimeError("ble not connected")
        self._run(self._write(bytes(data)))
        return len(data)

    async def _write(self, data: bytes) -> None:
        await self._client.write_gatt_char(self._write_uuid, data, response=False)

    def close(self) -> None:
        if self._client is not None and self._connected:
            try:
                self._run(self._disconnect(), timeout=10.0)
            except Exception:
                pass
        self._connected = False
        self._stop_loop()

    async def _disconnect(self) -> None:
        try:
            if self._notify_uuid:
                await self._client.stop_notify(self._notify_uuid)
        except Exception:
            pass
        await self._client.disconnect()

    def _stop_loop(self) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._loop_thread is not None:
            self._loop_thread.join(timeout=2)
        self._loop = None
        self._loop_thread = None
```

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/test_ble_transport.py -k "find_transparent or read_byte or open_then" -v`
Expected: PASS（4 项）。

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/backend/ble_transport.py tests/test_ble_transport.py
git commit -m "feat(ble): BleTransport 连接+特征值发现+read_byte 队列模式"
```

---

## Task 4: BleTransport.write MTU 分片

**Files:**
- Modify: `src/lbs_firmware_studio/backend/ble_transport.py`（`_write` 协程）
- Test: `tests/test_ble_transport.py`

**Interfaces:**
- Consumes: Task 3 的 `BleTransport.write`。
- Produces: `write` 按 `self._mtu` 分多次 `write_gatt_char`，字节顺序与完整性不变。

- [ ] **Step 1: 写失败测试**

追加：
```python
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
```

- [ ] **Step 2: 运行验证失败**

Run: `python -m pytest tests/test_ble_transport.py::test_write_chunks_by_mtu_and_preserves_bytes -v`
Expected: FAIL，`assert calls == [20, 20, 10]`（当前 `_write` 一次性写，calls==[50]）。

- [ ] **Step 3: 实现分片**

把 `ble_transport.py` 的 `_write` 改为：
```python
    async def _write(self, data: bytes) -> None:
        for i in range(0, len(data), self._mtu):
            await self._client.write_gatt_char(
                self._write_uuid, data[i:i + self._mtu], response=False)
```

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/test_ble_transport.py::test_write_chunks_by_mtu_and_preserves_bytes -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/backend/ble_transport.py tests/test_ble_transport.py
git commit -m "feat(ble): write 按 MTU 分片(链路层，与协议 chunk_size 正交)"
```

---

## Task 5: BleTransport — data_handler 模式 + 生命周期 + start_rx/stop_rx

**Files:**
- Modify: `src/lbs_firmware_studio/backend/ble_transport.py`
- Test: `tests/test_ble_transport.py`

**Interfaces:**
- Consumes: Task 3 的 BleTransport。
- Produces:
  - `set_data_handler(handler)` — 切回调模式（监控页用），设非 None 时清空队列。
  - `start_rx()`、`stop_rx()` — 与 SerialTransport 同名的鸭子方法（notify 已在 connect 时启动，二者为幂等/轻量）。
  - `close()` 干净停循环线程（无悬挂线程）。

- [ ] **Step 1: 写失败测试**

追加：
```python
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
```

- [ ] **Step 2: 运行验证失败**

Run: `python -m pytest tests/test_ble_transport.py -k "data_handler or close_stops" -v`
Expected: FAIL，`AttributeError: 'BleTransport' object has no attribute 'set_data_handler'`。

- [ ] **Step 3: 实现方法**

在 `ble_transport.py` 的 `read_byte` 之前插入：
```python
    def set_data_handler(self, handler: "Callable[[bytes], None] | None") -> None:
        self._data_handler = handler
        if handler is not None:
            while True:
                try:
                    self._rx_queue.get_nowait()
                except queue.Empty:
                    break

    def start_rx(self) -> None:
        # notify 在 _connect 时已订阅；此处仅为与 SerialTransport 对等的幂等钩子。
        pass

    def stop_rx(self) -> None:
        # 交付随 close() 的 stop_notify/disconnect 结束；对等钩子，无独立 RX 线程。
        pass
```

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/test_ble_transport.py -k "data_handler or close_stops" -v`
Expected: PASS。

- [ ] **Step 5: 运行全文件回归**

Run: `python -m pytest tests/test_ble_transport.py -q`
Expected: 全 PASS。

- [ ] **Step 6: Commit**

```bash
git add src/lbs_firmware_studio/backend/ble_transport.py tests/test_ble_transport.py
git commit -m "feat(ble): data_handler 回调模式 + start_rx/stop_rx 对等钩子 + close 生命周期"
```

---

## Task 6: BleTransport.wait_for_reopen — BLE 重连(地址优先，名字兜底)

仅 NEXT-AI 固件更新用到：发进入命令后设备复位、BLE 断开，按地址重连；地址找不到时用 `scanner` 按设备名兜底。

**Files:**
- Modify: `src/lbs_firmware_studio/backend/ble_transport.py`
- Test: `tests/test_ble_transport.py`

**Interfaces:**
- Consumes: Task 3 的 `_connect`、构造参数 `scanner`/`reconnect_name`。
- Produces: `wait_for_reopen(port, baud, retries, delay, post_delay=0.0, disappear_timeout=5.0) -> bool`，签名与 SerialTransport 对等；成功后清空 `_rx_queue`。

- [ ] **Step 1: 写失败测试**

追加：
```python
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
```

- [ ] **Step 2: 运行验证失败**

Run: `python -m pytest tests/test_ble_transport.py -k wait_for_reopen -v`
Expected: FAIL，`AttributeError: ... 'wait_for_reopen'`。

- [ ] **Step 3: 实现 wait_for_reopen**

在 `ble_transport.py` 的 `close()` 之前插入：
```python
    def wait_for_reopen(self, port: str, baud: int, retries: int, delay: float,
                        post_delay: float = 0.0, disappear_timeout: float = 5.0) -> bool:
        """BLE 版复位重连：断开当前连接 -> 按地址重连；地址失败则用 scanner 按名字兜底。
        成功后清空 RX 队列(对应 SerialTransport 的重新武装)。"""
        self._ensure_loop()
        try:
            if self._connected:
                self._run(self._disconnect(), timeout=10.0)
        except Exception:
            pass
        self._connected = False

        for attempt in range(retries):
            if attempt:
                time.sleep(delay)
            # 地址优先
            if self._try_connect(port):
                if post_delay > 0:
                    time.sleep(post_delay)
                return True
            # 名字兜底
            if self._scanner is not None and self._reconnect_name:
                try:
                    for dev in self._scanner(disappear_timeout):
                        if getattr(dev, "name", None) == self._reconnect_name:
                            if self._try_connect(dev.address):
                                if post_delay > 0:
                                    time.sleep(post_delay)
                                return True
                except Exception:
                    pass
        return False

    def _try_connect(self, address: str) -> bool:
        try:
            self._address = address
            self._run(self._connect())
            self._rx_queue = queue.Queue()
            return True
        except Exception:
            self._connected = False
            return False
```

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/test_ble_transport.py -k wait_for_reopen -v`
Expected: PASS（3 项）。注：此测试依赖 Task 7 的 `BleDevice`；若先做本任务，第二个测试会 ImportError——本计划中 Task 7 紧随其后，subagent 执行按序即可；如遇 ImportError 先跳过 name_fallback 测试，Task 7 完成后回跑。

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/backend/ble_transport.py tests/test_ble_transport.py
git commit -m "feat(ble): wait_for_reopen 重连(地址优先/名字兜底)"
```

---

## Task 7: BleScanner — 扫描附近全部设备

**Files:**
- Create: `src/lbs_firmware_studio/backend/ble_scanner.py`
- Test: `tests/test_ble_scanner.py`

**Interfaces:**
- Produces:
  - `@dataclass class BleDevice: name: str; address: str; rssi: int`
  - `scan(timeout=5.0, discover=None) -> list[BleDevice]` — `discover` 为可注入的 async callable(timeout)->可迭代设备对象(有 `name`/`address`/`rssi`)。缺省用 bleak，且 bleak 缺失时抛 `RuntimeError("未安装蓝牙支持(bleak)")`。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_ble_scanner.py`：
```python
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
        BleDevice(name="", address="CC:DD", rssi=-70),   # name=None 规整为空串
    ]


def test_scan_empty():
    async def fake_discover(timeout):
        return []
    assert scan(timeout=0.1, discover=fake_discover) == []


def test_scan_swallows_discover_error_returns_empty():
    async def boom(timeout):
        raise RuntimeError("adapter off")
    assert scan(timeout=0.1, discover=boom) == []
```

- [ ] **Step 2: 运行验证失败**

Run: `python -m pytest tests/test_ble_scanner.py -v`
Expected: FAIL，`ModuleNotFoundError: ble_scanner`。

- [ ] **Step 3: 实现 ble_scanner.py**

创建 `src/lbs_firmware_studio/backend/ble_scanner.py`：
```python
"""BLE 扫描：列出附近全部可连接设备(不做名称过滤)。"""
from __future__ import annotations
import asyncio
from dataclasses import dataclass
from typing import Callable

try:
    from bleak import BleakScanner
except ImportError:
    BleakScanner = None


@dataclass
class BleDevice:
    name: str
    address: str
    rssi: int


async def _bleak_discover(timeout: float):
    if BleakScanner is None:
        raise RuntimeError("未安装蓝牙支持(bleak)")
    return await BleakScanner.discover(timeout=timeout)


def scan(timeout: float = 5.0,
         discover: "Callable[[float], object] | None" = None) -> list[BleDevice]:
    """扫描并返回 BleDevice 列表；扫描异常(如适配器关闭)时返回空列表。"""
    disc = discover or _bleak_discover
    try:
        devices = asyncio.run(disc(timeout))
    except Exception:
        return []
    out: list[BleDevice] = []
    for d in devices:
        out.append(BleDevice(
            name=getattr(d, "name", None) or "",
            address=d.address,
            rssi=int(getattr(d, "rssi", 0) or 0),
        ))
    return out
```

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/test_ble_scanner.py -v`
Expected: PASS（3 项）。

- [ ] **Step 5: 回跑 Task 6 依赖 BleDevice 的测试**

Run: `python -m pytest tests/test_ble_transport.py -k wait_for_reopen -v`
Expected: PASS（3 项）。

- [ ] **Step 6: Commit**

```bash
git add src/lbs_firmware_studio/backend/ble_scanner.py tests/test_ble_scanner.py
git commit -m "feat(ble): BleScanner 扫描附近全部设备"
```

---

## Task 8: profile ble 字段 + products.yaml 配置

**Files:**
- Modify: `src/lbs_firmware_studio/backend/profile.py`（DeviceProfile 加字段 + load_profiles 加载）
- Modify: `products.yaml`
- Test: `tests/test_profile.py`

**Interfaces:**
- Consumes: 现有 `DeviceProfile` / `load_profiles`。
- Produces: `DeviceProfile.ble_enabled: bool`、`DeviceProfile.ble_firmware: bool`（来自 yaml 的 `ble.enabled` / `ble.firmware_over_ble`，缺省 False）。

- [ ] **Step 1: 写失败测试**

在 `tests/test_profile.py` 追加：
```python
def test_ble_fields_loaded(tmp_path):
    import textwrap as _tw
    yaml_text = _tw.dedent("""
        compiler_path: ./tools/rust-msc-latest-win10.exe
        products:
          NEW-AI:
            protocol: custom_frame
            firmware_dir: ./products/NEW-AI/fwlib
            ble:
              enabled: true
              firmware_over_ble: false
          NEXT-AI:
            protocol: ymodem
            firmware_dir: ./products/NEXT-AI/fwlib
            ble:
              enabled: true
              firmware_over_ble: true
          SPARK-AI:
            protocol: custom_frame
            firmware_dir: ./products/SPARK-AI/fwlib
    """)
    p = tmp_path / "products.yaml"; p.write_text(yaml_text)
    from lbs_firmware_studio.backend.profile import load_profiles
    profiles = load_profiles(p)
    assert profiles["NEW-AI"].ble_enabled is True
    assert profiles["NEW-AI"].ble_firmware is False
    assert profiles["NEXT-AI"].ble_firmware is True
    # 未配置 ble 段默认 False
    assert profiles["SPARK-AI"].ble_enabled is False
    assert profiles["SPARK-AI"].ble_firmware is False
```

- [ ] **Step 2: 运行验证失败**

Run: `python -m pytest tests/test_profile.py::test_ble_fields_loaded -v`
Expected: FAIL，`AttributeError: 'DeviceProfile' object has no attribute 'ble_enabled'`。

- [ ] **Step 3: DeviceProfile 加字段**

在 `profile.py` 的 DeviceProfile 里，`templates_dir` 行之后追加：
```python
    ble_enabled: bool = False                   # 该产品是否支持蓝牙通道
    ble_firmware: bool = False                  # 蓝牙是否支持固件更新(custom_frame=False)
```

- [ ] **Step 4: load_profiles 读取**

在 `profile.py` 的 `load_profiles` 里，构造 `DeviceProfile(...)` 之前加入解析，并在 `DeviceProfile(...)` 参数末尾（`templates_dir=templates_dir,` 之后）加两行：

解析（放在 `templates_dir` 计算之后、`out[name] = DeviceProfile(` 之前）：
```python
        ble_cfg = cfg.get("ble", {}) or {}
        ble_enabled = bool(ble_cfg.get("enabled", False))
        ble_firmware = bool(ble_cfg.get("firmware_over_ble", False))
```
构造参数追加：
```python
            templates_dir=templates_dir,
            ble_enabled=ble_enabled,
            ble_firmware=ble_firmware,
```

- [ ] **Step 5: 运行验证通过**

Run: `python -m pytest tests/test_profile.py -q`
Expected: 全 PASS。

- [ ] **Step 6: 更新 products.yaml**

给 `products.yaml` 三个产品各加 `ble` 段。NEW-AI 与 SPARK-AI（在各自 `disappear_timeout` 行之后）加：
```yaml
    ble:
      enabled: true
      firmware_over_ble: false
```
NEXT-AI（在其 `disappear_timeout` 行之后）加：
```yaml
    ble:
      enabled: true
      firmware_over_ble: true
```

- [ ] **Step 7: 验证真实配置加载**

Run: `python -c "from lbs_firmware_studio.backend.profile import load_profiles; p=load_profiles('products.yaml'); print({k:(v.ble_enabled,v.ble_firmware) for k,v in p.items()})"`
Expected: `{'NEW-AI': (True, False), 'SPARK-AI': (True, False), 'NEXT-AI': (True, True)}`

- [ ] **Step 8: Commit**

```bash
git add src/lbs_firmware_studio/backend/profile.py products.yaml tests/test_profile.py
git commit -m "feat(ble): profile ble_enabled/ble_firmware 字段 + products.yaml 配置"
```

---

## Task 9: 协议一致性复跑(custom_frame + YMODEM over BleTransport)

证明协议字节在 BLE 通道上与串口逐字一致：把 `DeviceSimulator` 接到 `BleTransport`，跑真实脚本下发/YMODEM 传输。

**Files:**
- Test: `tests/test_ble_protocol_replay.py`

**Interfaces:**
- Consumes: `BleTransport`(Task 3-5)、`FakeBleClient`(Task 2)、`DeviceSimulator`(现有)、`CustomFrameProtocol`/`YmodemProtocol`(现有)。

- [ ] **Step 1: 写测试(直接作为验收，无独立实现步)**

创建 `tests/test_ble_protocol_replay.py`：
```python
"""协议一致性复跑：协议层经 BleTransport 收发，字节须与串口版逐字一致。"""
from pathlib import Path
from lbs_firmware_studio.backend.ble_transport import BleTransport
from lbs_firmware_studio.backend.transfer_protocol import CustomFrameProtocol, YmodemProtocol
from tests.fakes import make_fake_ble_pair
from tests.simulator import DeviceSimulator


def _progress(done, total):
    pass


def test_custom_frame_script_send_over_ble(tmp_path):
    client, dev = make_fake_ble_pair(mtu_size=247)
    sim = DeviceSimulator(dev, protocol="custom_frame")
    sim.start()
    t = BleTransport(client_factory=lambda addr: client)
    t.open("addr")
    try:
        f = tmp_path / "0.o"; f.write_bytes(bytes(range(200)))
        proto = CustomFrameProtocol(chunk_size=248)
        # 脚本下发用 folder 命令码之一；这里直接用 send_folder 的单文件路径
        proto.send_folder(t, tmp_path, "app", _progress)
        import time; time.sleep(0.2)
        assert sim.received_files.get("0.o") == bytes(range(200))
    finally:
        sim.stop(); t.close()


def test_ymodem_send_over_ble(tmp_path):
    client, dev = make_fake_ble_pair(mtu_size=247)
    sim = DeviceSimulator(dev, protocol="ymodem")
    sim.start()
    t = BleTransport(client_factory=lambda addr: client)
    t.open("addr")
    try:
        f = tmp_path / "fw.bin"; f.write_bytes(bytes([0xAB]) * 300)
        proto = YmodemProtocol(block_size=1024)
        proto.enter_upgrade_mode(t, firmware=True, enter_cmd=b"ymodem update fmware\r\n")
        proto.send_file(t, f, _progress, firmware=True)
        import time; time.sleep(0.3)
        assert sim.received_files.get("fw.bin") == bytes([0xAB]) * 300
    finally:
        sim.stop(); t.close()
```

注：`send_folder` 用 `tmp_path` 作为 folder，需保证目录内只有 `0.o` 一个文件（测试用独立 tmp_path 满足）。`FOLDER_CMD_MAP` 需含 `"app"` 键（现有协议已定义）。

- [ ] **Step 2: 运行验证通过**

Run: `python -m pytest tests/test_ble_protocol_replay.py -v`
Expected: PASS（2 项）。若失败，检查是 transport 层问题（不得改协议层——那是零改动铁律）。

- [ ] **Step 3: Commit**

```bash
git add tests/test_ble_protocol_replay.py
git commit -m "test(ble): 协议一致性复跑(custom_frame+YMODEM over BleTransport)"
```

---

## Task 10: ConnectionSelector 控件

**Files:**
- Create: `src/lbs_firmware_studio/gui/widgets/connection_selector.py`
- Test: `tests/gui/test_connection_selector.py`

**Interfaces:**
- Consumes: 现有 `PortSelector`(gui/widgets/port_selector.py)、`SerialTransport`、`BleTransport`、`ble_scanner.scan`、`BleDevice`。
- Produces:
  - `class ConnectionSelector(QWidget)`，构造参数（均可注入以便测试）：`port_lister=None`、`ble_scan=None`、`serial_factory=SerialTransport`、`ble_factory=BleTransport`。
  - `selected_kind() -> "serial" | "ble"`
  - `selected_target() -> str | None`（串口 COM 名 / 蓝牙地址）
  - `selected_name() -> str | None`（蓝牙设备名，用于重连兜底；串口返 None）
  - `make_transport() -> object`（按 kind 造 SerialTransport 或 BleTransport(reconnect_name=名字, scanner=ble_scan)）
  - `set_kind(kind)`（供测试/程序切换）

- [ ] **Step 1: 写失败测试**

创建 `tests/gui/test_connection_selector.py`：
```python
import pytest
from PySide6.QtWidgets import QApplication
from lbs_firmware_studio.backend.ble_scanner import BleDevice
from lbs_firmware_studio.gui.widgets.connection_selector import ConnectionSelector


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _FakePort:
    def __init__(self, device, desc):
        self.device = device; self.description = desc; self.vid = None; self.pid = None


def test_default_kind_serial_and_target(app):
    cs = ConnectionSelector(port_lister=lambda: [_FakePort("COM3", "LBS Serial")],
                            ble_scan=lambda timeout=5.0: [])
    assert cs.selected_kind() == "serial"
    assert cs.selected_target() == "COM3"
    assert cs.selected_name() is None


def test_switch_to_ble_lists_devices_and_target(app):
    cs = ConnectionSelector(
        port_lister=lambda: [],
        ble_scan=lambda timeout=5.0: [BleDevice("ECB02", "AA:BB", -40)])
    cs.set_kind("ble")
    cs.scan_ble()                        # 触发扫描填充下拉
    assert cs.selected_kind() == "ble"
    assert cs.selected_target() == "AA:BB"
    assert cs.selected_name() == "ECB02"


def test_make_transport_by_kind(app):
    from lbs_firmware_studio.backend.serial_transport import SerialTransport
    from lbs_firmware_studio.backend.ble_transport import BleTransport
    cs = ConnectionSelector(port_lister=lambda: [_FakePort("COM3", "x")],
                            ble_scan=lambda timeout=5.0: [BleDevice("ECB02", "AA:BB", -40)])
    assert isinstance(cs.make_transport(), SerialTransport)
    cs.set_kind("ble"); cs.scan_ble()
    assert isinstance(cs.make_transport(), BleTransport)
```

- [ ] **Step 2: 运行验证失败**

Run: `python -m pytest tests/gui/test_connection_selector.py -q`
Expected: FAIL，`ModuleNotFoundError: connection_selector`。

- [ ] **Step 3: 实现 ConnectionSelector**

创建 `src/lbs_firmware_studio/gui/widgets/connection_selector.py`：
```python
"""连接方式统一入口：串口 / 蓝牙二选一，make_transport() 按 kind 造对等 transport。"""
from __future__ import annotations
from typing import Callable
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QRadioButton,
                               QButtonGroup, QStackedWidget, QComboBox, QPushButton)
from .port_selector import PortSelector
from ...backend.serial_transport import SerialTransport
from ...backend.ble_transport import BleTransport
from ...backend.ble_scanner import scan as ble_scan_default


class ConnectionSelector(QWidget):
    def __init__(self, port_lister: "Callable | None" = None,
                 ble_scan: "Callable | None" = None,
                 serial_factory=SerialTransport, ble_factory=BleTransport, parent=None):
        super().__init__(parent)
        self._ble_scan = ble_scan or (lambda timeout=5.0: ble_scan_default(timeout))
        self._serial_factory = serial_factory
        self._ble_factory = ble_factory

        self._rb_serial = QRadioButton("串口")
        self._rb_ble = QRadioButton("蓝牙")
        self._rb_serial.setChecked(True)
        self._group = QButtonGroup(self)
        self._group.addButton(self._rb_serial, 0)
        self._group.addButton(self._rb_ble, 1)
        row = QHBoxLayout(); row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self._rb_serial); row.addWidget(self._rb_ble); row.addStretch(1)

        self._port = PortSelector(lister=port_lister)
        ble_page = QWidget(); ble_lay = QHBoxLayout(ble_page); ble_lay.setContentsMargins(0, 0, 0, 0)
        self._ble_combo = QComboBox()
        self._ble_scan_btn = QPushButton("扫描")
        self._ble_scan_btn.clicked.connect(self.scan_ble)
        ble_lay.addWidget(self._ble_combo, 1); ble_lay.addWidget(self._ble_scan_btn)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._port)      # index 0 = serial
        self._stack.addWidget(ble_page)        # index 1 = ble

        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(row); lay.addWidget(self._stack)

        self._group.idToggled.connect(self._on_kind_toggled)

    def _on_kind_toggled(self, kind_id: int, checked: bool) -> None:
        if checked:
            self._stack.setCurrentIndex(kind_id)

    def set_kind(self, kind: str) -> None:
        (self._rb_ble if kind == "ble" else self._rb_serial).setChecked(True)
        self._stack.setCurrentIndex(1 if kind == "ble" else 0)

    def selected_kind(self) -> str:
        return "ble" if self._rb_ble.isChecked() else "serial"

    def scan_ble(self) -> None:
        self._ble_combo.clear()
        for d in self._ble_scan():
            label = f"{d.name or '(未命名)'} [{d.address}] {d.rssi}dBm"
            self._ble_combo.addItem(label, (d.address, d.name))

    def selected_target(self) -> "str | None":
        if self.selected_kind() == "serial":
            return self._port.selected_port()
        if self._ble_combo.count() == 0:
            return None
        return self._ble_combo.currentData()[0]

    def selected_name(self) -> "str | None":
        if self.selected_kind() == "serial" or self._ble_combo.count() == 0:
            return None
        return self._ble_combo.currentData()[1]

    def make_transport(self):
        if self.selected_kind() == "serial":
            return self._serial_factory()
        return self._ble_factory(scanner=lambda timeout: self._ble_scan(timeout),
                                 reconnect_name=self.selected_name())
```

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/gui/test_connection_selector.py -q`
Expected: PASS（3 项）。teardown 若报 exit 9 但断言全过，视为通过。

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/gui/widgets/connection_selector.py tests/gui/test_connection_selector.py
git commit -m "feat(ble): ConnectionSelector 串口/蓝牙统一入口"
```

---

## Task 11: main_window 接入 + 固件能力门禁

把写死的 `SerialTransport()` 换成 `ConnectionSelector.make_transport()`，并在蓝牙+custom_frame 时禁止固件更新。

**Files:**
- Modify: `src/lbs_firmware_studio/gui/main_window.py`
- Test: `tests/gui/test_main_window_ble_gate.py`

**Interfaces:**
- Consumes: `ConnectionSelector`(Task 10)、profile `ble_firmware`(Task 8)。
- Produces: MainWindow 用 `self._conn`(ConnectionSelector) 替代 `self._port`；`_run_deploy` 用 `self._conn.make_transport()`；固件路径在 `selected_kind()=="ble" and not profile.ble_firmware` 时警告并中止。

- [ ] **Step 1: 阅读现有接线**

Run: `python -c "print(open('src/lbs_firmware_studio/gui/main_window.py',encoding='utf-8').read())"`
确认 `self._port`(PortSelector) 的构造点、`_run_deploy` 里 `self._port.selected_port()`(line ~123) 与 `SerialTransport()`(line ~128) 的用法，以及 `_on_state` 里 `self._port.setEnabled(...)`(line ~152)。

- [ ] **Step 2: 写失败测试**

创建 `tests/gui/test_main_window_ble_gate.py`：
```python
import pytest
from PySide6.QtWidgets import QApplication
from lbs_firmware_studio.backend.profile import DeviceProfile


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _profile(protocol, ble_firmware):
    return DeviceProfile(name="X", protocol=protocol, firmware_dir=".",
                         ble_enabled=True, ble_firmware=ble_firmware)


def test_firmware_blocked_on_ble_when_not_supported(app, monkeypatch):
    from lbs_firmware_studio.gui.main_window import MainWindow
    w = MainWindow(_profile("custom_frame", False), {}, "products.yaml")
    # 强制连接方式为蓝牙
    w._conn.set_kind("ble")
    blocked = {"warned": False}
    monkeypatch.setattr("lbs_firmware_studio.gui.main_window.QMessageBox.warning",
                        lambda *a, **k: blocked.__setitem__("warned", True))
    w._start_firmware()
    assert blocked["warned"] is True        # 弹了"蓝牙不支持固件更新"
    assert w._busy is False                  # 未进入忙碌/未起线程


def test_firmware_allowed_on_ble_for_next_ai(app):
    from lbs_firmware_studio.gui.main_window import MainWindow
    w = MainWindow(_profile("ymodem", True), {}, "products.yaml")
    w._conn.set_kind("ble")
    # 无目标设备时应因"未选择设备"中止，而非因能力门禁——验证门禁不误伤 NEXT-AI
    assert w._ble_firmware_blocked() is False
```

- [ ] **Step 3: 运行验证失败**

Run: `python -m pytest tests/gui/test_main_window_ble_gate.py -q`
Expected: FAIL（`_conn`/`_ble_firmware_blocked` 不存在，或 MainWindow 仍用 `_port`）。

- [ ] **Step 4: 接入 ConnectionSelector**

在 `main_window.py`：
1. 顶部 import 追加：`from .widgets.connection_selector import ConnectionSelector`。
2. 构造处：把 `self._port = PortSelector(...)` 替换为 `self._conn = ConnectionSelector()`，并把布局中加入 `self._port` 的位置改为 `self._conn`（保持原布局槽位）。
3. `_run_deploy` 里：
   - `port = self._port.selected_port()` → `port = self._conn.selected_target()`
   - 未选提示文案 `"未选择串口"` → `"未选择连接目标"`
   - `self._transport = SerialTransport()` → `self._transport = self._conn.make_transport()`
4. `_on_state` 里 `self._port.setEnabled(not self._busy)` → `self._conn.setEnabled(not self._busy)`。
5. 保留 `from ..backend.serial_transport import SerialTransport` 导入可删（若无其他引用）。

- [ ] **Step 5: 加能力门禁方法**

在 `main_window.py` 的 `_start_firmware` 附近加：
```python
    def _ble_firmware_blocked(self) -> bool:
        """蓝牙通道 + 该产品不支持蓝牙固件更新(custom_frame) -> 阻止。"""
        return (self._conn.selected_kind() == "ble"
                and not getattr(self._profile, "ble_firmware", False))
```
并把 `_start_firmware` 改为：
```python
    def _start_firmware(self):
        if self._ble_firmware_blocked():
            QMessageBox.warning(self, "提示", "当前产品的蓝牙通道不支持固件更新，请改用串口")
            return
        self._run_deploy(self._firmware, "run_firmware")
```

- [ ] **Step 6: 运行验证通过**

Run: `python -m pytest tests/gui/test_main_window_ble_gate.py -q`
Expected: PASS（2 项）。teardown exit 9 但断言过即通过。

- [ ] **Step 7: 回归现有 main_window 测试**

Run: `python -m pytest tests/gui/ -q --co` 找出 main_window 相关测试文件，再逐个单独跑（例）：
`python -m pytest tests/gui/test_main_window.py -q`
Expected: 断言全过（若原测试引用 `self._port` 访问器需同步更新；`nav_labels()`/`header_text()` 等公开访问器签名不得改动）。若有引用 `_port` 的测试，改为 `_conn` 并保持行为。

- [ ] **Step 8: Commit**

```bash
git add src/lbs_firmware_studio/gui/main_window.py tests/gui/test_main_window_ble_gate.py
git commit -m "feat(ble): main_window 接入 ConnectionSelector + 固件能力门禁"
```

---

## Task 12: 打包 .spec bleak hiddenimports + 构建验证

**Files:**
- Modify: `LBS-Firmware-Studio.spec`
- Test: `tests/test_build_plan.py`

**Interfaces:**
- Consumes: 现有 `.spec`、`scripts/build.py`。

- [ ] **Step 1: 写失败测试**

在 `tests/test_build_plan.py` 的 `test_spec_file_has_key_settings` 追加断言（放在现有断言后）：
```python
    assert "bleak" in spec                     # BLE 后端隐藏导入
```

- [ ] **Step 2: 运行验证失败**

Run: `python -m pytest tests/test_build_plan.py::test_spec_file_has_key_settings -v`
Expected: FAIL，`assert 'bleak' in spec`。

- [ ] **Step 3: 修改 .spec**

把 `LBS-Firmware-Studio.spec` 的 `hiddenimports` 行改为：
```python
    hiddenimports=["serial.tools.list_ports", "bleak", "bleak.backends.winrt",
                   "bleak.backends.winrt.client", "bleak.backends.winrt.scanner"],
```
并在 `datas = collect_data_files("qtawesome")` 之后追加 bleak 数据收集：
```python
datas += collect_data_files("bleak")
```

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/test_build_plan.py -q`
Expected: 全 PASS。

- [ ] **Step 5: 重新打包并冒烟验证**

Run: `python scripts/build.py`
Expected: `Build complete`，`dist/LBS-Firmware-Studio/` 生成。
Run: `cd dist/LBS-Firmware-Studio && timeout 6 ./LBS-Firmware-Studio.exe 2>&1; cd ../..`
Expected: 无 traceback（exit 124 超时=GUI 正常运行）。若报 bleak 相关 ImportError，按报错补 hiddenimports。

- [ ] **Step 6: Commit**

```bash
git add LBS-Firmware-Studio.spec tests/test_build_plan.py
git commit -m "build(ble): .spec 收集 bleak hiddenimports+数据，构建验证"
```

---

## 最终验收

- [ ] **后端全量测试**

Run: `python -m pytest tests/ --ignore=tests/gui -q`
Expected: 全 PASS（含新增 ble_transport / ble_scanner / ble_protocol_replay / profile）。

- [ ] **GUI 测试按文件单独跑**

Run: `python -m pytest tests/gui/test_connection_selector.py -q` 与 `python -m pytest tests/gui/test_main_window_ble_gate.py -q`
Expected: 断言全过（teardown exit 9 可忽略）。

- [ ] **协议零改动确认**

Run: `git diff --name-only main -- src/lbs_firmware_studio/backend/transfer_protocol.py src/lbs_firmware_studio/backend/deployer.py src/lbs_firmware_studio/backend/protocol_frame.py src/lbs_firmware_studio/backend/ymodem.py src/lbs_firmware_studio/backend/serial_transport.py`
Expected: **空输出**（这五个文件未被修改，符合零改动铁律）。
