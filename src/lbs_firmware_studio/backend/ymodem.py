"""YMODEM 协议常量与纯函数。CRC16-XMODEM（多项式 0x1021，大端）。"""
from __future__ import annotations
import struct

SOH = 0x01
STX = 0x02
EOT = 0x04
ACK = 0x06
NAK = 0x15
CAN = 0x18
CRC_C = 0x43  # 'C'

BLOCK_128 = 128
BLOCK_1024 = 1024


def crc16_xmodem(data: bytes) -> int:
    crc = 0
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def make_packet(seq: int, payload: bytes, block_size: int) -> bytes:
    if block_size not in (BLOCK_128, BLOCK_1024):
        raise ValueError(f"block_size must be 128 or 1024, got {block_size}")
    if len(payload) > block_size:
        raise ValueError("payload too large")
    body = payload + bytes([0x1A]) * (block_size - len(payload))
    mark = SOH if block_size == BLOCK_128 else STX
    header = bytes([mark, seq & 0xFF, (~seq) & 0xFF])
    return header + body + struct.pack(">H", crc16_xmodem(body))
