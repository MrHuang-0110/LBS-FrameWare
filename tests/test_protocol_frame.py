import pytest

from lbs_firmware_studio.backend.protocol_frame import (
    HEADER, SOURCE, DEST, FOOTER, CMD_RESET, CMD_ACK, CMD_FILE_START,
    FOLDER_CMD_MAP, calculate_checksum, build_frame, parse_frame,
    CMD_RUN_TOGGLE,
)

def test_checksum_is_sum_low8():
    assert calculate_checksum(bytes([0x5A, 0x97, 0x98, 0x01, 0x6F])) == (0x5A+0x97+0x98+0x01+0x6F) & 0xFF

def test_build_frame_reset_with_reset_fwlib():
    frame = build_frame(CMD_RESET, b"RESET_FWLIB")
    assert frame[0] == HEADER and frame[1] == SOURCE and frame[2] == DEST
    assert frame[3] == len(b"RESET_FWLIB")
    assert frame[4] == CMD_RESET
    assert frame[5:5+11] == b"RESET_FWLIB"
    assert frame[-1] == FOOTER
    assert frame[-2] == calculate_checksum(frame[:-2])

def test_build_parse_roundtrip_with_data():
    data = bytes(range(248))
    frame = build_frame(CMD_FILE_START, data)
    parsed = parse_frame(frame)
    assert parsed == (CMD_FILE_START, data)

def test_parse_rejects_bad_header():
    bad = bytearray(build_frame(CMD_ACK, b"x"))
    bad[0] = 0x00
    assert parse_frame(bytes(bad)) is None

def test_parse_rejects_bad_checksum():
    bad = bytearray(build_frame(CMD_ACK, b"x"))
    bad[-2] ^= 0xFF
    assert parse_frame(bytes(bad)) is None

def test_parse_rejects_bad_footer():
    bad = bytearray(build_frame(CMD_ACK, b"x"))
    bad[-1] = 0x00
    assert parse_frame(bytes(bad)) is None

def test_folder_cmd_map():
    assert FOLDER_CMD_MAP["app"] == CMD_FILE_START
    assert FOLDER_CMD_MAP["version"] == 0xDD


def test_run_toggle_frame_matches_device_protocol():
    """验证 0xB6 帧与真机协议逐字节一致：5A 97 98 01 B6 01 41 A5"""
    frame = build_frame(CMD_RUN_TOGGLE, b"\x01")
    expected = bytes([0x5A, 0x97, 0x98, 0x01, 0xB6, 0x01, 0x41, 0xA5])
    assert frame == expected
    assert len(frame) == 8


def test_run_toggle_cmd_value():
    assert CMD_RUN_TOGGLE == 0xB6


def test_build_frame_rejects_str_data():
    with pytest.raises(TypeError, match="必须是 bytes"):
        build_frame(0x01, "hello")
