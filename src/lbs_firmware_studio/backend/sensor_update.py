"""NEW-AI 传感器更新指令：为 8 端口指定目标设备类型 ID，组帧下发。

帧格式复用 protocol_frame：5A 97 98 08 32 [A..H] checksum A5。
每字节为该端口目标设备类型 ID，0xFF=保持不动。设备类型 ID 源码核实自
e:/LBS-NEW-AI/Drivers/DataFile/*。即发即忘，不等 ACK。
"""
from __future__ import annotations
from .protocol_frame import build_frame

CMD_SENSOR_UPDATE = 0x32
KEEP = 0xFF

DEV_ID_BIG_MOTOR = 0xA1
DEV_ID_SMALL_MOTOR = 0xA6
DEV_ID_COLOR = 0xA2
DEV_ID_ULTRASION = 0xA3
DEV_ID_TOUCH = 0xA4
DEV_ID_CAMER = 0xA7
DEV_ID_GRAY = 0xA9
DEV_ID_GRAY_V2 = 0xB0
DEV_ID_NFC = 0xB2

# 下拉框选项：(显示名, id 值)，首项为保持不动
SENSOR_UPDATE_OPTIONS: list[tuple[str, int]] = [
    ("保持不动", KEEP),
    ("大电机", DEV_ID_BIG_MOTOR),
    ("中电机", DEV_ID_SMALL_MOTOR),
    ("颜色", DEV_ID_COLOR),
    ("超声波", DEV_ID_ULTRASION),
    ("触摸", DEV_ID_TOUCH),
    ("摄像头", DEV_ID_CAMER),
    ("灰度", DEV_ID_GRAY),
    ("灰度V2", DEV_ID_GRAY_V2),
    ("NFC", DEV_ID_NFC),
]


def build_sensor_update_frame(port_ids: list[int]) -> bytes:
    """8 个端口目标设备类型 ID -> 完整指令帧。长度必须为 8。"""
    if len(port_ids) != 8:
        raise ValueError(f"port_ids 必须正好 8 个，收到 {len(port_ids)}")
    return build_frame(CMD_SENSOR_UPDATE, bytes(port_ids))
