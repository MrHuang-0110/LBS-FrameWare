"""设备端模拟器：在 FakeSerial 上模拟三款产品的设备侧应答。"""
import threading
from lbs_firmware_studio.backend import protocol_frame as pf
from lbs_firmware_studio.backend import ymodem as ym


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
        self.ser.write(pf.build_frame(pf.CMD_ACK, b""))

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
        # YMODEM 接收端在收到文件头前会周期性重发 'C'。真机复位重连后主机才开始等 'C'，
        # 故这里循环重发，避免与主机的“进入升级->复位重连”窗口错开导致握手丢失。
        hdr = None
        for _ in range(60):
            if self._stop.is_set():
                return
            self.ser.write(bytes([ym.CRC_C]))  # 请求文件头
            hdr = self._read_packet(timeout=1.0)
            if hdr is not None:
                break
        if hdr is None:
            return
        parts = hdr.split(b"\x00")  # header = name\x00size\x00...
        self._cur_name = parts[0].decode("ascii", errors="replace") if parts[0] else "unnamed"
        self._cur_size = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
        self._cur_buf = bytearray()
        self.ser.write(bytes([ym.ACK, ym.CRC_C]))
        if is_firmware and self.emit_json:
            self._emit_json_burst()
        # 收数据包
        while not self._stop.is_set():
            pkt = self._read_packet(timeout=12.0)
            if pkt is None:
                break
            if pkt == bytes([ym.EOT]):
                self.ser.write(bytes([ym.NAK]))
                self._read_byte(timeout=5.0)    # 第二个 EOT
                self.ser.write(bytes([ym.ACK]))
                self.ser.write(bytes([ym.CRC_C]))
                self._read_packet(timeout=5.0)  # 空结束块
                self.ser.write(bytes([ym.ACK]))
                self._finalize_ymodem_file()
                self.ser.write(b"YMODEM OK\r\n")
                return
            self._cur_buf.extend(pkt)  # pkt 已是纯 body
            if self.emit_json and not is_firmware:
                self._emit_json_burst()
            self.ser.write(bytes([ym.ACK]))

    def _finalize_ymodem_file(self) -> None:
        if not self._cur_name:
            return
        data = bytes(self._cur_buf)
        if self._cur_size is not None:
            data = data[:self._cur_size]  # 按文件头声明大小截断填充
        self.received_files[self._cur_name] = data

    def _read_packet(self, timeout: float = 12.0) -> bytes | None:
        """读一个 YMODEM 包；块大小由 mark 决定(SOH=128/STX=1024)。
        返回纯 body(去 mark/seq/~seq/crc)，或 EOT 单字节 bytes([ym.EOT])。"""
        old = self.ser.timeout
        self.ser.timeout = timeout
        try:
            mark = self.ser.read(1)
            if not mark:
                return None
            if mark[0] == ym.EOT:
                return bytes([ym.EOT])
            block_size = 128 if mark[0] == ym.SOH else 1024
            rest_len = 2 + block_size + 2  # seq,~seq + body + crc16
            rest = self.ser.read(rest_len)
            if len(rest) != rest_len:
                return None
            return rest[2:-2]  # 剥去 seq/~seq 前缀与 crc 尾部
        finally:
            self.ser.timeout = old

    def _emit_json_burst(self) -> None:
        self.ser.write(b'{"adc":1234,"deviceList":[]}\r\n')
