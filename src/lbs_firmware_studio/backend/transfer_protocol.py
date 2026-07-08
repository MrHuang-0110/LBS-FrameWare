"""传输协议层：统一接口契约，不统一协议细节。"""
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable
import time

from . import protocol_frame as pf
from .serial_transport import SerialTransport

ProgressCb = Callable[[int, int], None]


class TransferProtocol(ABC):
    @abstractmethod
    def enter_upgrade_mode(self, t: SerialTransport, *, firmware: bool) -> None: ...
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

    def enter_upgrade_mode(self, t: SerialTransport, *, firmware: bool) -> None:
        t.write(pf.build_frame(pf.CMD_RESET, b"RESET_FWLIB"))

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
        """末帧：超时也视为成功（设备写 Flash 可能不回 ACK，按需求文档等 2s）；非末帧：必须收到 ACK 否则返回 False 触发重传。"""
        deadline = time.monotonic() + timeout
        buf = bytearray()
        while time.monotonic() < deadline:
            b = t.read_byte(timeout=max(0.05, deadline - time.monotonic()))
            if b is None:
                return True if is_last else False
            buf.append(b)
            if buf[0] != pf.HEADER:
                buf = bytearray()
                continue
            if len(buf) >= 7:
                parsed = pf.parse_frame(bytes(buf))
                if parsed and parsed[0] == pf.CMD_ACK:
                    return True
                buf = bytearray()
        return True if is_last else False

    def _last_frame_timeout(self) -> float:
        return {"wait_2s": 2.0, "wait_30s": 30.0, "skip": 0.5}[self.last_frame_ack]
