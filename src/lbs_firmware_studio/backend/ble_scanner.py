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
    # return_adv=True: 返回 dict[address -> (BLEDevice, AdvertisementData)]，
    # 才能拿到真实 name(adv.local_name) 与 rssi(adv.rssi)。
    return await BleakScanner.discover(timeout=timeout, return_adv=True)


def scan(timeout: float = 5.0,
         discover: "Callable[[float], object] | None" = None,
         raise_on_error: bool = False) -> list[BleDevice]:
    """扫描并返回 BleDevice 列表；扫描异常(如适配器关闭)时默认返回空列表。

    raise_on_error=True（GUI 扫描路径）：异常上抛，由上层把「扫描失败」可见化
    （状态点/提示），否则用户只看到空下拉不知道原因（用户反馈：蓝牙扫描不了东西）。

    兼容两种 discover 返回形态：
    - dict[address -> (BLEDevice, AdvertisementData)]（return_adv=True，生产路径）；
    - 设备对象列表（旧接口/测试注入），对象含 name/address/rssi。
    """
    disc = discover or _bleak_discover
    try:
        devices = asyncio.run(disc(timeout))
    except Exception:
        if raise_on_error:
            raise
        return []
    out: list[BleDevice] = []
    if isinstance(devices, dict):
        for dev, adv in devices.values():
            name = getattr(adv, "local_name", None) or getattr(dev, "name", None) or ""
            rssi = getattr(adv, "rssi", None)
            out.append(BleDevice(
                name=name,
                address=dev.address,
                rssi=int(rssi if rssi is not None else 0),
            ))
    else:
        for d in devices:
            out.append(BleDevice(
                name=getattr(d, "name", None) or "",
                address=d.address,
                rssi=int(getattr(d, "rssi", 0) or 0),
            ))
    return out
