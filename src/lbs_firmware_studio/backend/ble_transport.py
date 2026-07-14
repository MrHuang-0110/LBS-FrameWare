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
        # 链路层按协商 MTU 分片（与协议层 chunk_size 正交）
        for i in range(0, len(data), self._mtu):
            await self._client.write_gatt_char(
                self._write_uuid, data[i:i + self._mtu], response=False)

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
