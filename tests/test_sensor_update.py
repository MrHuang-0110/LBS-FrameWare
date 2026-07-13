import pytest
from lbs_firmware_studio.backend.sensor_update import (
    CMD_SENSOR_UPDATE, KEEP, DEV_ID_COLOR, DEV_ID_BIG_MOTOR,
    SENSOR_UPDATE_OPTIONS, build_sensor_update_frame,
)
from lbs_firmware_studio.backend.protocol_frame import (
    HEADER, SOURCE, DEST, FOOTER, calculate_checksum,
)


def test_all_keep_frame_matches_reference():
    # 全 0xFF 样例：5A 97 98 08 32 FF*8 BB A5（checksum=0xBB 已验证）
    frame = build_sensor_update_frame([KEEP] * 8)
    assert frame == bytes([0x5A, 0x97, 0x98, 0x08, 0x32] + [0xFF] * 8 + [0xBB, 0xA5])


def test_frame_structure_and_checksum():
    ids = [DEV_ID_COLOR, KEEP, DEV_ID_BIG_MOTOR, KEEP, KEEP, KEEP, KEEP, KEEP]
    frame = build_sensor_update_frame(ids)
    assert frame[0] == HEADER and frame[1] == SOURCE and frame[2] == DEST
    assert frame[3] == 8                       # len
    assert frame[4] == CMD_SENSOR_UPDATE       # 0x32
    assert list(frame[5:13]) == ids            # 8 数据字节
    assert frame[-1] == FOOTER
    assert frame[-2] == calculate_checksum(frame[:-2])


def test_rejects_wrong_length():
    with pytest.raises(ValueError):
        build_sensor_update_frame([KEEP] * 7)   # 必须正好 8


def test_options_first_is_keep():
    assert SENSOR_UPDATE_OPTIONS[0] == ("保持不动", KEEP)
    # 9 种设备 + 1 保持不动 = 10 项
    assert len(SENSOR_UPDATE_OPTIONS) == 10
    assert ("颜色", DEV_ID_COLOR) in SENSOR_UPDATE_OPTIONS
