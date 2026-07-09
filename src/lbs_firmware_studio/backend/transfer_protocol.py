"""传输协议层：统一接口契约，不统一协议细节。"""
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable
import time

from . import protocol_frame as pf
from . import ymodem as ym
from .serial_transport import SerialTransport

ProgressCb = Callable[[int, int], None]


class TransferProtocol(ABC):
    @abstractmethod
    def enter_upgrade_mode(self, t: SerialTransport, *, firmware: bool, enter_cmd: bytes | None = None) -> None: ...
    @abstractmethod
    def send_file(self, t: SerialTransport, path: Path, on_progress: ProgressCb, *, firmware: bool) -> None: ...
    @abstractmethod
    def finish_session(self, t: SerialTransport, *, firmware: bool) -> None: ...


class CustomFrameProtocol(TransferProtocol):
    def __init__(self, chunk_size: int = 248, ack_timeout: float = 2.0,
                 last_frame_ack: str = "wait_2s", max_retries: int = 3,
                 filename_encoding: str = "gbk"):
        self.chunk_size = min(chunk_size, pf.MAX_DATA_LEN)
        self.ack_timeout = ack_timeout
        self.last_frame_ack = last_frame_ack
        self.max_retries = max_retries
        self.filename_encoding = filename_encoding

    def enter_upgrade_mode(self, t: SerialTransport, *, firmware: bool, enter_cmd: bytes | None = None) -> None:
        cmd = enter_cmd if enter_cmd else b"RESET_FWLIB"
        t.write(pf.build_frame(pf.CMD_RESET, cmd))

    def send_file(self, t: SerialTransport, path: Path, on_progress: ProgressCb, *, firmware: bool) -> None:
        self._send_file_with_cmd(t, path, pf.CMD_FILE_START, on_progress)

    def send_folder(self, t: SerialTransport, folder: Path, folder_name: str, on_progress: ProgressCb) -> None:
        cmd = pf.FOLDER_CMD_MAP[folder_name]
        for f in sorted(folder.iterdir()):
            if f.is_file():
                self._send_file_with_cmd(t, f, cmd, on_progress)

    def _send_file_with_cmd(self, t, path, cmd, on_progress):
        name = path.name.encode(self.filename_encoding)
        data = path.read_bytes()
        self._send_and_wait(t, pf.build_frame(cmd, name))
        time.sleep(0.05)
        total = len(data); sent = 0
        while sent < total:
            chunk = data[sent:sent + self.chunk_size]
            is_last = sent + len(chunk) >= total
            c = pf.CMD_FILE_END if is_last else pf.CMD_FILE_DATA
            self._send_and_wait(t, pf.build_frame(c, chunk), is_last=is_last)
            sent += len(chunk)
            on_progress(sent, total)

    def finish_session(self, t: SerialTransport, *, firmware: bool) -> None:
        pass  # 设备自行重启

    def _send_and_wait(self, t: SerialTransport, frame: bytes, *, is_last: bool = False) -> None:
        timeout = self._last_frame_timeout() if is_last else self.ack_timeout
        for attempt in range(self.max_retries):
            t.write(frame)
            if self._wait_ack(t, timeout, is_last=is_last):
                return
        raise TimeoutError(f"no ACK after {self.max_retries} retries")

    def _wait_ack(self, t: SerialTransport, timeout: float, *, is_last: bool) -> bool:
        """末帧：超时也视为成功（设备写 Flash 可能不回 ACK，按需求文档等 2s）；非末帧：必须收到 ACK 否则返回 False 触发重传。

        按帧长动态读取，不假设固定长度：找到帧头 0x5A 后读固定 4 字节(src/dst/len/cmd)，
        据 len 读 data，再读 checksum+footer。真机 ACK 带 1 字节 data(共 8 字节)，
        且 src/dst 顺序与主机发出的帧相反，故仅凭 cmd==0xFD 判定，不校验 src/dst。
        """
        deadline = time.monotonic() + timeout

        def _remaining() -> float:
            return max(0.0, deadline - time.monotonic())

        while time.monotonic() < deadline:
            b = t.read_byte(timeout=max(0.05, _remaining()))
            if b is None:
                return True if is_last else False
            if b != pf.HEADER:
                continue  # 丢弃噪声，继续找帧头
            # 读固定部分 src/dst/len/cmd
            fixed = []
            for _ in range(4):
                nb = t.read_byte(timeout=max(0.05, _remaining()))
                if nb is None:
                    break
                fixed.append(nb)
            if len(fixed) != 4:
                continue
            data_len = fixed[2]
            cmd = fixed[3]
            # 读 data + checksum + footer
            rest_needed = data_len + 2
            rest = []
            for _ in range(rest_needed):
                nb = t.read_byte(timeout=max(0.05, _remaining()))
                if nb is None:
                    break
                rest.append(nb)
            if len(rest) != rest_needed:
                continue
            if rest[-1] != pf.FOOTER:
                continue  # 帧尾不符，重新找帧头
            # 校验和：sum(HEADER..data) & 0xFF
            frame_wo_tail = bytes([pf.HEADER] + fixed + rest[:data_len])
            if rest[-2] != pf.calculate_checksum(frame_wo_tail):
                continue
            if cmd == pf.CMD_ACK:
                return True
            # 其它功能码(如 0xFC 失败/0xFE 错误)：非 ACK，继续等到超时
        return True if is_last else False

    def _last_frame_timeout(self) -> float:
        return {"wait_2s": 2.0, "wait_30s": 30.0, "skip": 0.5}[self.last_frame_ack]


class YmodemProtocol(TransferProtocol):
    def __init__(self, block_size: int = 1024, ack_timeout: float = 12.0,
                 crc_wait: float = 120.0, max_retries: int = 3,
                 usb_quick_exit: bool = True):
        self.block_size = block_size
        self.ack_timeout = ack_timeout
        self.crc_wait = crc_wait
        self.max_retries = max_retries
        self.usb_quick_exit = usb_quick_exit

    def enter_upgrade_mode(self, t: SerialTransport, *, firmware: bool, enter_cmd: bytes | None = None) -> None:
        if enter_cmd:
            cmd = enter_cmd
        else:
            cmd = b"ymodem update fmware\r\n" if firmware else b"ymodem\r\n"
        t.write(cmd)

    def send_file(self, t: SerialTransport, path: Path, on_progress: ProgressCb, *, firmware: bool) -> None:
        data = path.read_bytes()
        name = path.name.encode("ascii", errors="replace")
        header = name + b"\x00" + str(len(data)).encode("ascii") + b"\x00"
        if len(header) > 128:
            raise ValueError("filename too long")
        # 1. 等 'C'
        self._wait_control(t, ym.CRC_C, self.crc_wait, firmware=firmware)
        # 2. 文件头 (SOH/128, seq=0)
        self._send_packet_wait(t, ym.make_packet(0, header, 128), firmware=firmware)
        self._wait_control(t, ym.CRC_C, self.ack_timeout, firmware=firmware)
        # 3. 数据块
        seq = 1
        offset = 0
        total = len(data)
        while offset < total:
            chunk = data[offset:offset + self.block_size]
            self._send_packet_wait(t, ym.make_packet(seq, chunk, self.block_size), firmware=firmware)
            offset += self.block_size
            seq = seq + 1 if seq < 255 else 1
            on_progress(min(offset, total), total)
        # 4. 收尾 EOT 双发 + 空结束块
        self._finish(t, firmware)

    def finish_session(self, t: SerialTransport, *, firmware: bool) -> None:
        pass

    def _send_packet_wait(self, t: SerialTransport, pkt: bytes, *, firmware: bool) -> None:
        for attempt in range(self.max_retries):
            t.write(pkt)
            try:
                self._wait_control(t, ym.ACK, self.ack_timeout, firmware=firmware)
                return
            except TimeoutError:
                if attempt == self.max_retries - 1:
                    # 数据块必须真正收到 ACK；超时代表通信故障，不得静默视为成功
                    # （usb_quick_exit 只作用于 _finish/EOT 阶段，见 spec §5.2 step e）
                    raise

    def _finish(self, t: SerialTransport, firmware: bool) -> None:
        try:
            t.write(bytes([ym.EOT]))
            self._wait_control(t, ym.NAK, self.ack_timeout, firmware=firmware)
            t.write(bytes([ym.EOT]))
            self._wait_control(t, ym.ACK, self.ack_timeout, firmware=firmware)
            self._wait_control(t, ym.CRC_C, self.ack_timeout, firmware=firmware)
            t.write(ym.make_packet(0, b"", 128))  # 空结束块
            self._wait_control(t, ym.ACK, self.ack_timeout, firmware=firmware)
        except (TimeoutError, OSError):
            if firmware and self.usb_quick_exit:
                return  # USB 复位断线，视为完成
            raise

    def _wait_control(self, t: SerialTransport, expected: int, timeout: float, *, firmware: bool) -> None:
        """容错等待控制字节：跳过可打印字符（JSON 干扰），忽略杂散 'C'（除非期望 'C'）。"""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            b = t.read_byte(timeout=max(0.05, deadline - time.monotonic()))
            if b is None:
                continue
            if b == ym.CAN:
                raise RuntimeError("device cancelled (CAN)")
            if b == expected:
                return
            if b == ym.CRC_C and expected != ym.CRC_C:
                continue  # 忽略杂散 'C'
            if 0x20 <= b <= 0x7E:
                continue  # 跳过可打印 JSON 字符
            # 其它非期望控制字节：继续等
        raise TimeoutError(f"timeout waiting for 0x{expected:02X}")
