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
