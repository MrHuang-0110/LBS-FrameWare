"""自定义帧协议纯函数（零 IO）。帧格式: [0x5A][0x97][0x98][len][cmd][data...][checksum][0xA5]"""
from __future__ import annotations

HEADER = 0x5A
SOURCE = 0x97
DEST = 0x98
FOOTER = 0xA5

CMD_RESET = 0x6F
CMD_ACK = 0xFD
CMD_FILE_START = 0xDA   # app 文件夹
CMD_FILE_DATA = 0xAA
CMD_FILE_END = 0xBB
CMD_MUSIC = 0xEC
CMD_BOOT = 0xDB
CMD_CONFIG = 0xDC
CMD_VERSION = 0xDD

FOLDER_CMD_MAP = {
    "app": CMD_FILE_START, "music": CMD_MUSIC, "boot": CMD_BOOT,
    "config": CMD_CONFIG, "version": CMD_VERSION,
}

MAX_DATA_LEN = 248


def calculate_checksum(data: bytes) -> int:
    return sum(data) & 0xFF


def build_frame(cmd: int, data: bytes = b"") -> bytes:
    if len(data) > MAX_DATA_LEN:
        raise ValueError(f"data too long: {len(data)} > {MAX_DATA_LEN}")
    head = bytes([HEADER, SOURCE, DEST, len(data), cmd]) + data
    return head + bytes([calculate_checksum(head), FOOTER])


def parse_frame(raw: bytes) -> tuple[int, bytes] | None:
    if len(raw) < 7:
        return None
    if raw[0] != HEADER or raw[-1] != FOOTER:
        return None
    data_len = raw[3]
    if len(raw) != 7 + data_len:
        return None
    if raw[-2] != calculate_checksum(raw[:-2]):
        return None
    cmd = raw[4]
    data = raw[5:5 + data_len]
    return cmd, data
