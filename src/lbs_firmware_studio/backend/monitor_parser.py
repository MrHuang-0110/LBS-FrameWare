"""设备流式监控解析：字节流按行切分 + JSON 解析。纯函数，零 IO/零 GUI。

设备端持续 USB_printf("%s\r\n", json)。RX 后台线程按 chunk 喂 feed()，
本类维护缓冲处理跨 chunk 的半行；坏行静默丢弃；缓冲超上限清空防膨胀。
"""
from __future__ import annotations
import json


class MonitorParser:
    MAX_BUFFER = 64 * 1024

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, data: bytes) -> list[dict]:
        self._buf.extend(data)
        out: list[dict] = []
        while b"\n" in self._buf:
            line, _, rest = self._buf.partition(b"\n")
            self._buf = bytearray(rest)
            obj = self._parse_line(bytes(line))
            if obj is not None:
                out.append(obj)
        # 缓冲超上限 -> 兜底截断：切行后残留仍超限（极端超长行/异常流）时强制清空，
        # 统一上限守卫（不再要求"完全无换行"），保证缓冲永不撑破 MAX_BUFFER
        if len(self._buf) > self.MAX_BUFFER:
            self._buf.clear()
        return out

    @staticmethod
    def _parse_line(line: bytes) -> "dict | None":
        text = line.strip()          # 去掉 \r 及首尾空白
        if not text:
            return None
        try:
            obj = json.loads(text)
        except (ValueError, UnicodeDecodeError):
            return None
        return obj if isinstance(obj, dict) else None
