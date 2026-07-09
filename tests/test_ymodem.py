import struct
from lbs_firmware_studio.backend.ymodem import (
    SOH, STX, EOT, ACK, NAK, CAN, CRC_C, crc16_xmodem, make_packet,
)

def test_crc16_known_vector():
    # XMODEM CRC of "123456789" is 0x31C3
    assert crc16_xmodem(b"123456789") == 0x31C3

def test_crc16_empty_is_zero():
    assert crc16_xmodem(b"") == 0

def test_make_packet_1024_pads_and_marks_stx():
    payload = b"\xAB" * 10
    pkt = make_packet(1, payload, 1024)
    assert pkt[0] == STX
    assert pkt[1] == 1 and pkt[2] == (~1) & 0xFF
    body = pkt[3:-2]
    assert len(body) == 1024
    assert body[:10] == payload and body[10:] == b"\x1a" * (1024 - 10)
    assert pkt[-2:] == struct.pack(">H", crc16_xmodem(body))

def test_make_packet_128_uses_soh():
    pkt = make_packet(0, b"header", 128)
    assert pkt[0] == SOH
    assert pkt[1] == 0 and pkt[2] == 0xFF
    assert len(pkt) == 3 + 128 + 2

def test_make_packet_seq_wrap_complement():
    pkt = make_packet(255, b"x", 128)
    assert pkt[1] == 0xFF and pkt[2] == (~255) & 0xFF == 0x00

def test_make_packet_rejects_oversized():
    import pytest
    with pytest.raises(ValueError):
        make_packet(1, b"x" * 200, 128)

def test_constants():
    assert SOH == 0x01 and STX == 0x02 and EOT == 0x04
    assert ACK == 0x06 and NAK == 0x15 and CAN == 0x18 and CRC_C == 0x43
