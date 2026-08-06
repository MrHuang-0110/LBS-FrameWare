"""设备端模拟器：在 FakeSerial 上模拟三款产品的设备侧应答。"""
import threading
from lbs_firmware_studio.backend import protocol_frame as pf
from lbs_firmware_studio.backend import ymodem as ym

# 单字节控制码的 bytes 形态，避免反复 bytes([...]) 包装。
_EOT = bytes([ym.EOT])
_ACK = bytes([ym.ACK])
_NAK = bytes([ym.NAK])
_CRC_C = bytes([ym.CRC_C])


class DeviceSimulator:
    def __init__(self, serial_obj, protocol: str = "custom_frame", emit_json: bool = False):
        self.ser = serial_obj
        self.protocol = protocol
        self.emit_json = emit_json
        self.received_files: dict[str, bytes] = {}  # filename -> data
        self._cur_name = None
        self._cur_size = None
        self._cur_buf = bytearray()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)

    def _read_byte(self, timeout=1.0) -> int | None:
        old = self.ser.timeout
        self.ser.timeout = timeout
        try:
            b = self.ser.read(1)
        finally:
            self.ser.timeout = old
        return b[0] if b else None

    def _run(self) -> None:
        while not self._stop.is_set():
            if self.protocol == "custom_frame":
                self._custom_frame_step()
            else:
                self._ymodem_step()

    # ---- 自定义帧 ----
    def _custom_frame_step(self) -> None:
        b = self._read_byte(timeout=0.2)
        if b is None or b != pf.HEADER:
            return
        fixed = self.ser.read(4)
        if len(fixed) != 4:
            return
        data_len = fixed[2]
        data = self.ser.read(data_len) if data_len else b""
        tail = self.ser.read(2)
        if len(tail) != 2 or tail[1] != pf.FOOTER:
            return
        frame = bytes([pf.HEADER]) + fixed + data + tail
        parsed = pf.parse_frame(frame)
        if parsed is None:
            return
        cmd, d = parsed
        self._handle_custom_cmd(cmd, d)

    def _handle_custom_cmd(self, cmd: int, data: bytes) -> None:
        if cmd == pf.CMD_RESET:
            self.received_files.clear()
            self._cur_name = None
            self._cur_buf = bytearray()
            return  # 设备复位，不回 ACK（断开语义）
        if cmd in pf.FOLDER_CMD_MAP.values():
            self._cur_name = data.decode("gbk", errors="replace")
            self._cur_buf = bytearray()
            self._send_ack()
            return
        if cmd == pf.CMD_FILE_DATA:
            self._cur_buf.extend(data)
            self._send_ack()
            return
        if cmd == pf.CMD_FILE_END:
            self._cur_buf.extend(data)
            if self._cur_name:
                self.received_files[self._cur_name] = bytes(self._cur_buf)
            self._cur_name = None
            self._send_ack()
            return

    def _send_ack(self) -> None:
        # 真机 ACK 带 1 字节 data，且 src/dst 顺序与主机帧相反(5a 98 97 ...)。
        # 手工构造以贴近真机，让测试能覆盖「带 data 的变长 ACK」。
        body = bytes([pf.HEADER, pf.DEST, pf.SOURCE, 0x01, pf.CMD_ACK, 0x01])
        self.ser.write(body + bytes([pf.calculate_checksum(body), pf.FOOTER]))

    # ---- YMODEM ----
    def _ymodem_step(self) -> None:
        line = self._read_line(timeout=0.2)
        if line is None:
            return
        if b"ymodem" in line:
            self._do_ymodem_session(is_firmware=b"fmware" in line)

    def _read_line(self, timeout=1.0) -> bytes | None:
        old = self.ser.timeout
        self.ser.timeout = timeout
        buf = bytearray()
        try:
            while not self._stop.is_set():
                b = self.ser.read(1)
                if not b:
                    return buf if buf else None
                buf.extend(b)
                if buf.endswith(b"\r\n"):
                    return bytes(buf)
        finally:
            self.ser.timeout = old

    def _do_ymodem_session(self, is_firmware: bool) -> None:
        # 接收端在收到文件头前周期性重发 'C'：真机复位重连后主机才开始等 'C'，
        # 循环重发避免与“进入升级->复位重连”窗口错开导致握手丢失。
        hdr = None
        for _ in range(60):
            if self._stop.is_set():
                return
            self.ser.write(_CRC_C)  # 请求文件头
            got = self._read_packet(timeout=1.0)
            if got is not None and got[1] != _EOT and got[0] == 0:
                hdr = got[1]
                break  # 文件头块（seq=0）
        if hdr is None:
            return
        parts = hdr.split(b"\x00")  # header = name\x00size\x00...
        self._cur_name = parts[0].decode("ascii", errors="replace") or "unnamed"
        self._cur_size = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
        self._cur_buf = bytearray()
        self.ser.write(_ACK + _CRC_C)
        if is_firmware and self.emit_json:
            self._emit_json_burst()
        # 数据包：seq 1..255 循环（255 后回 1；0 仅用于文件头/结束块，对齐真机
        # ymodem.c:429-433），不连续时回 NAK 等发送端重发同 seq 包。
        expected_seq = 1
        while not self._stop.is_set():
            got = self._read_packet(timeout=12.0, expect_seq=expected_seq)
            if got is None:
                continue
            seq, pkt = got
            if pkt == _EOT:
                self.ser.write(_NAK)
                self._read_byte(timeout=5.0)    # 第二个 EOT
                self.ser.write(_ACK + _CRC_C)
                self._read_packet(timeout=5.0)  # 空结束块
                self.ser.write(_ACK)
                self._finalize_ymodem_file()
                self.ser.write(b"YMODEM OK\r\n")
                return
            if seq == 0:
                # 文件头之后收到 seq=0：真机当「结束块」ACK 并截断文件（ymodem.c:395-400）
                self.ser.write(_ACK)
                self._finalize_ymodem_file()
                return
            self._cur_buf.extend(pkt)  # pkt 已是纯 body
            expected_seq = 1 if expected_seq == 255 else expected_seq + 1
            if self.emit_json and not is_firmware:
                self._emit_json_burst()
            self.ser.write(_ACK)

    def _finalize_ymodem_file(self) -> None:
        if not self._cur_name:
            return
        data = bytes(self._cur_buf)
        if self._cur_size is not None:
            data = data[:self._cur_size]  # 按文件头声明大小截断填充
        self.received_files[self._cur_name] = data

    def _read_packet(self, timeout: float = 12.0, expect_seq: int | None = None) -> tuple[int | None, bytes] | None:
        """读一个 YMODEM 包；块大小由 mark 决定（SOH=128/STX=1024）。
        返回 (seq, 纯 body)（body 已去 mark/seq/~seq/crc），EOT 返回 (None, b"\\x04")。
        expect_seq 非 None 时校验包 seq（1..255 循环），不匹配回 NAK 并返回 None。"""
        old = self.ser.timeout
        self.ser.timeout = timeout
        try:
            mark = self.ser.read(1)
            if not mark:
                return None
            if mark[0] == ym.EOT:
                return (None, _EOT)
            block_size = 128 if mark[0] == ym.SOH else 1024
            rest_len = 2 + block_size + 2  # seq,~seq + body + crc16
            rest = self.ser.read(rest_len)
            if len(rest) != rest_len:
                return None
            # seq=0 例外：真机在文件头之后把 seq=0 当结束块（ymodem.c:395-400 先于
            # bn!=blk_expect 判断），交给上层处理而不在此 NAK。
            if expect_seq is not None and rest[0] != expect_seq and rest[0] != 0:
                self.ser.write(_NAK)
                return None
            return (rest[0], rest[2:-2])  # (seq, 剥去 seq/~seq 前缀与 crc 尾部)
        finally:
            self.ser.timeout = old

    def _emit_json_burst(self) -> None:
        self.ser.write(b'{"adc":1234,"deviceList":[]}\r\n')
