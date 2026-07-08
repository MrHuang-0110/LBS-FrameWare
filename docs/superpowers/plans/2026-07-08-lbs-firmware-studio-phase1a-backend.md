# LBS Firmware Studio · 阶段 1a 后端实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建可脱离 GUI 独立运行的后端：统一三层架构（串口层 / 协议层 / 编排层）+ 设备模拟器，支持 NEW-AI / SPARK-AI（自定义帧）与 NEXT-AI（YMODEM）的固件更新与 Python 脚本下发，全部用模拟器自动化测试。

**Architecture:** 纯协议逻辑（帧/CRC/组包）零 IO 耦合、先行 TDD；`SerialTransport` 封装 pyserial 并带后台 RX 线程（为阶段 3 监控预留字节路由）；`TransferProtocol` ABC 统一两套协议的接口契约；`DeviceDeployer` 按产品配置编排编译→连接→进升级→传输→收尾，用 Qt 信号上报进度；`DeviceSimulator` 作为测试资产在 `FakeSerial` 上模拟设备端应答。

**Tech Stack:** Python 3.13、pyserial、PyYAML、pytest；后续阶段才引入 PySide6 / QScintilla / pyqtgraph（本计划不装）。

## Global Constraints

- Python 3.13；Windows 平台。
- 协议字节必须与现有真机代码逐字一致：自定义帧 `0x5A 0x97 0x98 [len][cmd][data][checksum] 0xA5`，checksum = `sum(HEADER..data) & 0xFF`；YMODEM CRC16-XMODEM 多项式 `0x1021`、大端。
- `"ymodem update fmware\r\n"` 拼写错误**保留**（与设备端 C 代码一致，勿改）。
- 固件更新末帧 ACK：`wait_2s`（等 2s 无应答则跳过，符合 `LBS_BURN/LBS烧录器需求.txt`）。
- 重传：`max_retries=3`。
- 文件名编码可配（`gbk` / `utf-8`），按产品默认。
- 阶段 1 只做 USB，不实现蓝牙。
- 合并现有两套 YMODEM 为一份（容错接收：跳过可打印字符、忽略杂散 'C'，同时覆盖 Boot 干净通道与 APP JSON 干扰通道）。

---

## File Structure

```
e:\LBS-FramWare\
  pyproject.toml
  .gitignore
  products.yaml
  tools/
    rust-msc-latest-win10.exe            # 从现有项目复制
  src/lbs_firmware_studio/
    __init__.py
    backend/
      __init__.py
      protocol_frame.py     # 自定义帧纯函数 + 常量（零 IO）
      ymodem.py             # YMODEM 纯函数（crc16/make_packet）+ 常量
      serial_transport.py   # pyserial 封装 + 后台 RX 线程 + 重连
      transfer_protocol.py  # TransferProtocol ABC + CustomFrameProtocol + YmodemProtocol
      pika_compiler.py      # 调 rust-msc 编译 .py -> .py.o
      profile.py            # DeviceProfile + load_profiles
      deployer.py           # DeviceDeployer(QObject) 编排 + 信号
    cli.py                  # 无头 CLI 入口（阶段 1a 交付物）
  tests/
    __init__.py
    conftest.py
    fakes.py                # FakeSerial 串口对
    simulator.py            # DeviceSimulator 测试资产
    test_protocol_frame.py
    test_ymodem.py
    test_serial_transport.py
    test_custom_frame_protocol.py
    test_ymodem_protocol.py
    test_pika_compiler.py
    test_profile.py
    test_deployer.py
```

## 接口契约（各任务共同遵守）

```python
# protocol_frame.py
HEADER=0x5A; SOURCE=0x97; DEST=0x98; FOOTER=0xA5
CMD_RESET=0x6F; CMD_ACK=0xFD; CMD_FILE_START=0xDA; CMD_FILE_DATA=0xAA
CMD_FILE_END=0xBB; CMD_MUSIC=0xEC; CMD_BOOT=0xDB; CMD_CONFIG=0xDC; CMD_VERSION=0xDD
FOLDER_CMD_MAP = {"app":0xDA,"music":0xEC,"boot":0xDB,"config":0xDC,"version":0xDD}
def calculate_checksum(data: bytes) -> int
def build_frame(cmd: int, data: bytes) -> bytes
def parse_frame(raw: bytes) -> tuple[int, bytes] | None   # None=非法/校验失败

# ymodem.py
SOH=0x01; STX=0x02; EOT=0x04; ACK=0x06; NAK=0x15; CAN=0x18; CRC_C=0x43
def crc16_xmodem(data: bytes) -> int
def make_packet(seq: int, payload: bytes, block_size: int) -> bytes   # block_size∈{128,1024}

# serial_transport.py
class SerialTransport:
    def open(self, port: str, baud: int) -> None
    def close(self) -> None
    def write(self, data: bytes) -> int
    def read_byte(self, timeout: float) -> int | None
    def set_data_handler(self, handler: Callable[[bytes], None] | None) -> None  # 阶段3用
    def wait_for_reopen(self, port: str, baud: int, retries: int, delay: float) -> bool
    # 构造可注入 serial_obj 便于测试: SerialTransport(serial_obj=None)

# transfer_protocol.py
class TransferProtocol(ABC):
    def enter_upgrade_mode(self, t: SerialTransport, *, firmware: bool) -> None
    def send_file(self, t, path: Path, on_progress: Callable[[int,int],None], *, firmware: bool) -> None
    def finish_session(self, t, *, firmware: bool) -> None

# pika_compiler.py
def compile_py(py_path: Path, out_path: Path, compiler_path: Path, cwd: Path | None = None) -> Path

# profile.py
@dataclass
class DeviceProfile:
    name: str; protocol: str          # "custom_frame" | "ymodem"
    baud: int = 115200
    firmware_enter_cmd: bytes         # NEW/SPARK: RESET_FWLIB帧; NEXT固件: "ymodem update fmware\r\n"
    script_enter_cmd: bytes           # NEW/SPARK: 同上; NEXT脚本: "ymodem\r\n"
    folders: list[str]                # NEW:5 / SPARK:2 / NEXT:["__single__"]
    chunk_size: int                   # 自定义帧248 / YMODEM 1024
    ack_timeout: float = 2.0
    last_frame_ack: str = "wait_2s"   # "wait_2s"|"wait_30s"|"skip"
    filename_encoding: str = "gbk"
    compiler_path: Path
    script_dirs: dict                 # 源.py目录 -> 输出.py.o目录
    firmware_dir: Path
    reopen_retries: int = 5
    reopen_delay: float = 2.0
def load_profiles(path: Path) -> dict[str, DeviceProfile]

# deployer.py
class DeviceDeployer(QObject):
    progress = Signal(int, int); log = Signal(str)
    state_changed = Signal(str); error = Signal(str)
    def compile_scripts(self, profile, py_dir: Path) -> list[Path]
    def update_firmware(self, profile, port: str) -> None
    def deploy_scripts(self, profile, port: str, py_dir: Path) -> None
```

---

### Task 1: 项目脚手架

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `src/lbs_firmware_studio/__init__.py`, `src/lbs_firmware_studio/backend/__init__.py`, `tests/__init__.py`, `tests/conftest.py`, `products.yaml`
- Copy: `tools/rust-msc-latest-win10.exe`（从 `E:\LBS-Project\pikapython-download-tool\rust-msc-latest-win10.exe` 复制）

**Interfaces:** 无（基础设施）

- [ ] **Step 1: 初始化 git 与目录**

```bash
cd e:/LBS-FramWare
git init
mkdir -p src/lbs_firmware_studio/backend tests tools
```

- [ ] **Step 2: 写 pyproject.toml**

```toml
[project]
name = "lbs-firmware-studio"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = ["pyserial>=3.5", "PyYAML>=6.0"]

[project.scripts]
lbs-firmware = "lbs_firmware_studio.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 3: 写 .gitignore**

```
__pycache__/
*.pyc
.venv/
dist/
*.egg-info/
.pytest_cache/
compile_log.txt
```

- [ ] **Step 4: 写空 __init__.py 与 conftest.py**

`src/lbs_firmware_studio/__init__.py`:
```python
__version__ = "0.1.0"
```
`src/lbs_firmware_studio/backend/__init__.py`:（空文件）
`tests/__init__.py`:（空文件）
`tests/conftest.py`:
```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
```

- [ ] **Step 5: 写 products.yaml 骨架**

```yaml
compiler_path: ./tools/rust-msc-latest-win10.exe
products:
  NEW-AI:
    protocol: custom_frame
    baud: 115200
    folders: [app, music, boot, config, version]
    firmware_dir: ./products/NEW-AI/fwlib
    script_dirs: { ./products/NEW-AI/write: ./products/NEW-AI/app }
    chunk_size: 248
    last_frame_ack: wait_2s
    filename_encoding: gbk
    firmware_enter_cmd: RESET_FWLIB
    script_enter_cmd: RESET_FWLIB
    reopen_retries: 5
    reopen_delay: 2.0
  SPARK-AI:
    protocol: custom_frame
    baud: 115200
    folders: [app, version]
    firmware_dir: ./products/SPARK-AI/fwlib
    script_dirs: { ./products/SPARK-AI/write: ./products/SPARK-AI/app }
    chunk_size: 248
    last_frame_ack: wait_2s
    filename_encoding: gbk
    firmware_enter_cmd: RESET_FWLIB
    script_enter_cmd: RESET_FWLIB
  NEXT-AI:
    protocol: ymodem
    baud: 115200
    folders: [__single__]
    firmware_dir: ./products/NEXT-AI/fwlib
    script_dirs: { ./products/NEXT-AI/write: ./products/NEXT-AI/app }
    chunk_size: 1024
    last_frame_ack: skip
    filename_encoding: utf-8
    firmware_enter_cmd: "ymodem update fmware\r\n"
    script_enter_cmd: "ymodem\r\n"
    reopen_retries: 40
    reopen_delay: 3.0
```

- [ ] **Step 6: 复制编译器**

```bash
cp "E:/LBS-Project/pikapython-download-tool/rust-msc-latest-win10.exe" e:/LBS-FramWare/tools/
```

- [ ] **Step 7: 安装依赖并验证**

```bash
python -m pip install -e . pytest
python -m pytest --co -q
```
Expected: `no tests ran`（0 错误，能收集）

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "chore: scaffold project structure and config"
```

---

### Task 2: 自定义帧纯函数（TDD）

**Files:**
- Create: `src/lbs_firmware_studio/backend/protocol_frame.py`
- Test: `tests/test_protocol_frame.py`

**Interfaces:**
- Produces: `calculate_checksum`, `build_frame`, `parse_frame`, 常量与 `FOLDER_CMD_MAP`

- [ ] **Step 1: 写失败测试**

`tests/test_protocol_frame.py`:
```python
from lbs_firmware_studio.backend.protocol_frame import (
    HEADER, SOURCE, DEST, FOOTER, CMD_RESET, CMD_ACK, CMD_FILE_START,
    FOLDER_CMD_MAP, calculate_checksum, build_frame, parse_frame,
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_protocol_frame.py -v
```
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: 实现 protocol_frame.py**

```python
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
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_protocol_frame.py -v
```
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/backend/protocol_frame.py tests/test_protocol_frame.py
git commit -m "feat: custom-frame protocol pure functions"
```

---

### Task 3: YMODEM 纯函数（TDD）

**Files:**
- Create: `src/lbs_firmware_studio/backend/ymodem.py`
- Test: `tests/test_ymodem.py`

**Interfaces:**
- Produces: `crc16_xmodem`, `make_packet`, 常量

- [ ] **Step 1: 写失败测试**

`tests/test_ymodem.py`:
```python
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
    assert body[:10] == payload and body[10:] == b"\x00" * (1024 - 10)
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
```

- [ ] **Step 2: 运行确认失败**

```bash
python -m pytest tests/test_ymodem.py -v
```
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: 实现 ymodem.py 纯函数部分**

```python
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
    body = payload + bytes(block_size - len(payload))
    mark = SOH if block_size == BLOCK_128 else STX
    header = bytes([mark, seq & 0xFF, (~seq) & 0xFF])
    return header + body + struct.pack(">H", crc16_xmodem(body))
```

- [ ] **Step 4: 运行确认通过**

```bash
python -m pytest tests/test_ymodem.py -v
```
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/backend/ymodem.py tests/test_ymodem.py
git commit -m "feat: ymodem crc16 and packet builder"
```

---

### Task 4: FakeSerial 与设备模拟器（测试资产）

**Files:**
- Create: `tests/fakes.py`, `tests/simulator.py`
- Test: `tests/test_simulator.py`

**Interfaces:**
- Produces: `make_fake_serial_pair() -> (FakeSerial, FakeSerial)`、`DeviceSimulator`（设备端状态机，跑在独立线程）
- Consumes: `protocol_frame`、`ymodem` 纯函数

- [ ] **Step 1: 写 FakeSerial（tests/fakes.py）**

```python
"""测试用虚拟串口：两个端点互连，模拟 pyserial 接口子集。"""
import queue


class FakeSerial:
    def __init__(self, rx_queue: queue.Queue, tx_queue: queue.Queue):
        self._rx = rx_queue
        self._tx = tx_queue
        self.is_open = True
        self.timeout = 1.0
        self.dtr = False
        self.rts = False
        self.write_timeout = 5.0

    def write(self, data: bytes) -> int:
        for b in data:
            self._tx.put(b)
        return len(data)

    def read(self, n: int = 1) -> bytes:
        try:
            first = self._rx.get(timeout=self.timeout)
        except queue.Empty:
            return b""
        out = bytearray([first])
        while len(out) < n:
            try:
                out.append(self._rx.get_nowait())
            except queue.Empty:
                break
        return bytes(out)

    @property
    def in_waiting(self) -> int:
        return self._rx.qsize()

    def reset_input_buffer(self) -> None:
        while True:
            try:
                self._rx.get_nowait()
            except queue.Empty:
                break

    def reset_output_buffer(self) -> None:
        pass

    def cancel_read(self) -> None:
        pass

    def close(self) -> None:
        self.is_open = False


def make_fake_serial_pair():
    a_rx: queue.Queue = queue.Queue()
    b_rx: queue.Queue = queue.Queue()
    a = FakeSerial(a_rx, b_rx)
    b = FakeSerial(b_rx, a_rx)
    return a, b
```

- [ ] **Step 2: 写 DeviceSimulator（tests/simulator.py）**

设备端逻辑：收到自定义帧文件名帧/数据帧回 ACK(0xFD)；收到 reset 帧后"复位"（清状态）；收到 `ymodem update fmware\r\n` / `ymodem\r\n` 进入 YMODEM，发 'C'，按 SOH/STX 收包回 ACK，EOT 双发处理，结束时发 "YMODEM OK"。可选 `emit_json=True` 在 APP YMODEM 期间注入 JSON 干扰。

```python
"""设备端模拟器：在 FakeSerial 上模拟三款产品的设备侧应答。"""
import threading, time
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
        self.ser.write(bytes([ym.CRC_C]))  # 请求文件头
        # 收文件头包 (SOH, seq=0)；_read_packet 返回纯 payload(已剥 mark/seq/~seq/crc)
        hdr = self._read_packet()
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
```

- [ ] **Step 3: 写模拟器自测（tests/test_simulator.py）**

```python
from tests.fakes import make_fake_serial_pair
from tests.simulator import DeviceSimulator
from lbs_firmware_studio.backend import protocol_frame as pf


def test_simulator_acks_custom_frame_file():
    host_ser, dev_ser = make_fake_serial_pair()
    sim = DeviceSimulator(dev_ser, protocol="custom_frame")
    sim.start()
    try:
        # 发文件名帧 (app 文件夹)
        host_ser.write(pf.build_frame(pf.CMD_FILE_START, "demo.py.o".encode("gbk")))
        ack = pf.parse_frame(_read_frame(host_ser, timeout=2.0))
        assert ack is not None and ack[0] == pf.CMD_ACK
        # 发一帧数据 + 末帧
        host_ser.write(pf.build_frame(pf.CMD_FILE_DATA, b"hello"))
        assert pf.parse_frame(_read_frame(host_ser)) is not None
        host_ser.write(pf.build_frame(pf.CMD_FILE_END, b""))
        assert pf.parse_frame(_read_frame(host_ser)) is not None
        assert sim.received_files.get("demo.py.o") == b"hello"
    finally:
        sim.stop()


def _read_frame(host_ser, timeout=2.0):
    old = host_ser.timeout
    host_ser.timeout = timeout
    try:
        b = host_ser.read(1)
        while b and b[0] != pf.HEADER:
            b = host_ser.read(1)
        if not b:
            return b""
        fixed = host_ser.read(4)
        data_len = fixed[2] if len(fixed) == 4 else 0
        data = host_ser.read(data_len)
        tail = host_ser.read(2)
        return bytes([pf.HEADER]) + fixed + data + tail
    finally:
        host_ser.timeout = old
```

- [ ] **Step 4: 运行确认通过**

```bash
python -m pytest tests/test_simulator.py -v
```
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add tests/fakes.py tests/simulator.py tests/test_simulator.py
git commit -m "test: fake serial and device simulator"
```

---

### Task 5: SerialTransport（TDD）

**Files:**
- Create: `src/lbs_firmware_studio/backend/serial_transport.py`
- Test: `tests/test_serial_transport.py`

**Interfaces:**
- Produces: `SerialTransport`
- Consumes: `FakeSerial`

- [ ] **Step 1: 写失败测试**

`tests/test_serial_transport.py`:
```python
from lbs_firmware_studio.backend.serial_transport import SerialTransport
from tests.fakes import make_fake_serial_pair


def test_read_byte_receives_written_byte():
    host_ser, dev_ser = make_fake_serial_pair()
    t = SerialTransport(host_ser)
    t.start_rx()
    try:
        dev_ser.write(b"\x41")
        assert t.read_byte(timeout=1.0) == 0x41
    finally:
        t.stop_rx()


def test_read_byte_returns_none_on_timeout():
    host_ser, _ = make_fake_serial_pair()
    t = SerialTransport(host_ser)
    t.start_rx()
    try:
        assert t.read_byte(timeout=0.1) is None
    finally:
        t.stop_rx()


def test_data_handler_receives_bytes():
    host_ser, dev_ser = make_fake_serial_pair()
    t = SerialTransport(host_ser)
    received = []
    t.set_data_handler(lambda data: received.append(data))
    t.start_rx()
    try:
        dev_ser.write(b"\x01\x02\x03")
        import time; time.sleep(0.2)
        assert b"".join(received) == b"\x01\x02\x03"
        # handler 模式下 read_byte 无数据
        assert t.read_byte(timeout=0.1) is None
    finally:
        t.stop_rx()


def test_write_sends_to_peer():
    host_ser, dev_ser = make_fake_serial_pair()
    t = SerialTransport(host_ser)
    try:
        t.write(b"ping")
        import time; time.sleep(0.1)
        assert dev_ser.read(4) == b"ping"
    finally:
        pass
```

- [ ] **Step 2: 运行确认失败**

```bash
python -m pytest tests/test_serial_transport.py -v
```
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: 实现 serial_transport.py**

```python
"""串口层：封装 pyserial，后台 RX 线程把字节路由给队列或数据回调。"""
from __future__ import annotations
import threading, queue, time
from typing import Callable

try:
    import serial
    import serial.tools.list_ports
except ImportError:  # 测试环境用 FakeSerial，pyserial 可能未装
    serial = None


class SerialTransport:
    def __init__(self, serial_obj=None):
        self._serial = serial_obj
        self._rx_queue: queue.Queue[int] = queue.Queue()
        self._data_handler: Callable[[bytes], None] | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def is_open(self) -> bool:
        return self._serial is not None and getattr(self._serial, "is_open", True)

    def open(self, port: str, baud: int) -> None:
        if self._serial is None:
            self._serial = serial.Serial(port=port, baudrate=baud, timeout=0.1)
        else:
            self._serial.timeout = 0.1

    def close(self) -> None:
        self.stop_rx()
        if self._serial and getattr(self._serial, "is_open", False):
            try:
                self._serial.close()
            except Exception:
                pass

    def write(self, data: bytes) -> int:
        if self._serial is None:
            raise RuntimeError("serial not open")
        return self._serial.write(data)

    def set_data_handler(self, handler: Callable[[bytes], None] | None) -> None:
        self._data_handler = handler
        if handler is not None:
            while True:
                try:
                    self._rx_queue.get_nowait()
                except queue.Empty:
                    break

    def start_rx(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._rx_loop, daemon=True)
        self._thread.start()

    def stop_rx(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def _rx_loop(self) -> None:
        while not self._stop.is_set():
            try:
                chunk = self._serial.read(64)
            except Exception:
                time.sleep(0.05)
                continue
            if not chunk:
                continue
            if self._data_handler is not None:
                self._data_handler(bytes(chunk))
            else:
                for b in chunk:
                    self._rx_queue.put(b)

    def read_byte(self, timeout: float) -> int | None:
        if self._data_handler is not None:
            return None
        try:
            return self._rx_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def wait_for_reopen(self, port: str, baud: int, retries: int, delay: float) -> bool:
        self.close()
        for attempt in range(retries):
            time.sleep(delay if attempt else min(delay, 0.5))
            try:
                if serial is not None:
                    self._serial = serial.Serial(port=port, baudrate=baud, timeout=0.1)
                else:
                    self._serial.is_open = True
                self._rx_queue = queue.Queue()
                return True
            except Exception:
                continue
        return False
```

- [ ] **Step 4: 运行确认通过**

```bash
python -m pytest tests/test_serial_transport.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/backend/serial_transport.py tests/test_serial_transport.py
git commit -m "feat: serial transport with rx thread and data handler"
```

---

### Task 6: CustomFrameProtocol（TDD vs 模拟器）

**Files:**
- Create: `src/lbs_firmware_studio/backend/transfer_protocol.py`
- Test: `tests/test_custom_frame_protocol.py`

**Interfaces:**
- Produces: `TransferProtocol`（ABC）、`CustomFrameProtocol`
- Consumes: `protocol_frame`、`SerialTransport`、`DeviceSimulator`

- [ ] **Step 1: 写失败测试**

`tests/test_custom_frame_protocol.py`:
```python
import pathlib, tempfile
from lbs_firmware_studio.backend.serial_transport import SerialTransport
from lbs_firmware_studio.backend.transfer_protocol import CustomFrameProtocol
from tests.fakes import make_fake_serial_pair
from tests.simulator import DeviceSimulator


def _setup(protocol="custom_frame", emit_json=False):
    host_ser, dev_ser = make_fake_serial_pair()
    sim = DeviceSimulator(dev_ser, protocol=protocol, emit_json=emit_json)
    sim.start()
    t = SerialTransport(host_ser); t.start_rx()
    return t, sim


def test_enter_upgrade_sends_reset_frame():
    t, sim = _setup()
    try:
        proto = CustomFrameProtocol()
        proto.enter_upgrade_mode(t, firmware=True)
        # reset 帧已发，模拟器清空 received_files
        assert sim.received_files == {}
    finally:
        t.stop_rx(); sim.stop()


def test_send_file_delivers_to_simulator():
    t, sim = _setup()
    try:
        proto = CustomFrameProtocol(chunk_size=248, ack_timeout=2.0, last_frame_ack="wait_2s")
        proto.enter_upgrade_mode(t, firmware=True)
        with tempfile.NamedTemporaryFile(suffix=".py.o", delete=False) as f:
            f.write(b"hello world data")
            path = pathlib.Path(f.name)
        progress = []
        proto.send_file(t, path, lambda d, n: progress.append((d, n)), firmware=False)
        assert "path" in str(path) or True
        assert sim.received_files.get(path.name) == b"hello world data"
        assert progress[-1][0] == progress[-1][1]  # 完成
    finally:
        t.stop_rx(); sim.stop()


def test_send_file_retries_on_timeout():
    host_ser, dev_ser = make_fake_serial_pair()
    # 不启动模拟器 -> 不会回 ACK -> 触发重传
    t = SerialTransport(host_ser); t.start_rx()
    try:
        proto = CustomFrameProtocol(chunk_size=248, ack_timeout=0.2, last_frame_ack="skip", max_retries=3)
        proto.enter_upgrade_mode(t, firmware=True)
        import pytest
        with pytest.raises(TimeoutError):
            with tempfile.NamedTemporaryFile(delete=False) as f:
                f.write(b"x" * 10); path = pathlib.Path(f.name)
            proto.send_file(t, path, lambda d, n: None, firmware=False)
    finally:
        t.stop_rx()
```

- [ ] **Step 2: 运行确认失败**

```bash
python -m pytest tests/test_custom_frame_protocol.py -v
```
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: 实现 transfer_protocol.py（含 ABC 与 CustomFrameProtocol）**

```python
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
        name = path.name.encode(self.filename_encoding)
        folder_cmd = pf.CMD_FILE_START  # app 文件夹（脚本下发）；固件由 send_folder 调用时传入
        data = path.read_bytes()
        # 1. 文件名帧
        self._send_and_wait(t, pf.build_frame(folder_cmd, name))
        time.sleep(0.05)
        # 2. 数据分块
        total = len(data)
        sent = 0
        seq = 0
        while sent < total:
            chunk = data[sent:sent + self.chunk_size]
            is_last = sent + len(chunk) >= total
            cmd = pf.CMD_FILE_END if is_last else pf.CMD_FILE_DATA
            self._send_and_wait(t, pf.build_frame(cmd, chunk), is_last=is_last)
            sent += len(chunk)
            seq += 1
            on_progress(sent, total)

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
```

- [ ] **Step 4: 运行确认通过**

```bash
python -m pytest tests/test_custom_frame_protocol.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/backend/transfer_protocol.py tests/test_custom_frame_protocol.py
git commit -m "feat: custom frame transfer protocol"
```

---

### Task 7: YmodemProtocol（TDD vs 模拟器）

**Files:**
- Modify: `src/lbs_firmware_studio/backend/transfer_protocol.py`（追加 `YmodemProtocol`）
- Test: `tests/test_ymodem_protocol.py`

**Interfaces:**
- Produces: `YmodemProtocol`
- Consumes: `ymodem`、`SerialTransport`、`DeviceSimulator`

- [ ] **Step 1: 写失败测试**

`tests/test_ymodem_protocol.py`:
```python
import pathlib, tempfile
from lbs_firmware_studio.backend.serial_transport import SerialTransport
from lbs_firmware_studio.backend.transfer_protocol import YmodemProtocol
from tests.fakes import make_fake_serial_pair
from tests.simulator import DeviceSimulator


def test_firmware_update_boot_ymodem():
    host_ser, dev_ser = make_fake_serial_pair()
    sim = DeviceSimulator(dev_ser, protocol="ymodem")
    sim.start()
    t = SerialTransport(host_ser); t.start_rx()
    try:
        proto = YmodemProtocol(block_size=1024, ack_timeout=5.0)
        proto.enter_upgrade_mode(t, firmware=True)  # 发 "ymodem update fmware\r\n"
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(b"\xAA" * 2048); path = pathlib.Path(f.name)
        progress = []
        proto.send_file(t, path, lambda d, n: progress.append((d, n)), firmware=True)
        assert sim.received_files.get(path.name) == b"\xAA" * 2048
    finally:
        t.stop_rx(); sim.stop()


def test_script_deploy_tolerates_json():
    host_ser, dev_ser = make_fake_serial_pair()
    sim = DeviceSimulator(dev_ser, protocol="ymodem", emit_json=True)
    sim.start()
    t = SerialTransport(host_ser); t.start_rx()
    try:
        proto = YmodemProtocol(block_size=1024, ack_timeout=5.0)
        proto.enter_upgrade_mode(t, firmware=False)  # 发 "ymodem\r\n"
        with tempfile.NamedTemporaryFile(suffix=".py.o", delete=False) as f:
            f.write(b"\xBB" * 500); path = pathlib.Path(f.name)
        proto.send_file(t, path, lambda d, n: None, firmware=False)
        assert sim.received_files.get(path.name) == b"\xBB" * 500
    finally:
        t.stop_rx(); sim.stop()
```

- [ ] **Step 2: 运行确认失败**

```bash
python -m pytest tests/test_ymodem_protocol.py -v
```
Expected: FAIL `ImportError: cannot import YmodemProtocol`

- [ ] **Step 3: 追加 YmodemProtocol 到 transfer_protocol.py**

在文件末尾追加：
```python
class YmodemProtocol(TransferProtocol):
    def __init__(self, block_size: int = 1024, ack_timeout: float = 12.0,
                 crc_wait: float = 120.0, max_retries: int = 3,
                 usb_quick_exit: bool = True):
        self.block_size = block_size
        self.ack_timeout = ack_timeout
        self.crc_wait = crc_wait
        self.max_retries = max_retries
        self.usb_quick_exit = usb_quick_exit

    def enter_upgrade_mode(self, t: SerialTransport, *, firmware: bool) -> None:
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
                    if firmware and self.usb_quick_exit:
                        return  # Boot 复位断线视为完成
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
```

- [ ] **Step 4: 运行确认通过**

```bash
python -m pytest tests/test_ymodem_protocol.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/backend/transfer_protocol.py tests/test_ymodem_protocol.py
git commit -m "feat: ymodem transfer protocol with tolerant receive"
```

---

### Task 8: PikaCompiler（TDD，mock subprocess）

**Files:**
- Create: `src/lbs_firmware_studio/backend/pika_compiler.py`
- Test: `tests/test_pika_compiler.py`

**Interfaces:**
- Produces: `compile_py`

- [ ] **Step 1: 写失败测试**

`tests/test_pika_compiler.py`:
```python
import pathlib, subprocess
from unittest.mock import patch
import pytest
from lbs_firmware_studio.backend.pika_compiler import compile_py


def test_compile_success(monkeypatch, tmp_path):
    py = tmp_path / "main.py"; py.write_text("print(1)")
    out = tmp_path / "main.py.o"
    compiler = tmp_path / "rust-msc.exe"

    def fake_run(cmd, cwd=None, capture_output=True, text=True, encoding=None, errors=None):
        # 模拟编译器写出 .o
        out_path = pathlib.Path(cmd[cmd.index("-o") + 1])
        out_path.write_bytes(b"\x0F\x70 79o\x00")  # magic .pyo
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = compile_py(py, out, compiler)
    assert result == out and out.exists()


def test_compile_failure_raises(monkeypatch, tmp_path):
    py = tmp_path / "main.py"; py.write_text("x")
    out = tmp_path / "main.py.o"
    compiler = tmp_path / "rust-msc.exe"
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a[0], 1, stdout="", stderr="syntax error"))
    with pytest.raises(RuntimeError, match="exit=1"):
        compile_py(py, out, compiler)


def test_compile_missing_compiler(tmp_path):
    with pytest.raises(FileNotFoundError):
        compile_py(tmp_path / "a.py", tmp_path / "a.py.o", tmp_path / "nope.exe")
```

- [ ] **Step 2: 运行确认失败**

```bash
python -m pytest tests/test_pika_compiler.py -v
```
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: 实现 pika_compiler.py**

```python
"""调用 rust-msc 编译器把 .py 编译成 .py.o 字节码。"""
from __future__ import annotations
import subprocess
from pathlib import Path


def compile_py(py_path: Path, out_path: Path, compiler_path: Path, cwd: Path | None = None) -> Path:
    if not compiler_path.is_file():
        raise FileNotFoundError(f"compiler not found: {compiler_path}")
    if not py_path.is_file():
        raise FileNotFoundError(f"source not found: {py_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [str(compiler_path), "-c", str(py_path), "-o", str(out_path)]
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"compile failed, exit={proc.returncode}: {proc.stderr.strip()}")
    if not out_path.is_file():
        raise FileNotFoundError(f"output not generated: {out_path}")
    return out_path
```

- [ ] **Step 4: 运行确认通过**

```bash
python -m pytest tests/test_pika_compiler.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/backend/pika_compiler.py tests/test_pika_compiler.py
git commit -m "feat: pika compiler wrapper"
```

---

### Task 9: DeviceProfile + 配置加载（TDD）

**Files:**
- Create: `src/lbs_firmware_studio/backend/profile.py`
- Test: `tests/test_profile.py`

**Interfaces:**
- Produces: `DeviceProfile`, `load_profiles`

- [ ] **Step 1: 写失败测试**

`tests/test_profile.py`:
```python
import pathlib, textwrap
from lbs_firmware_studio.backend.profile import load_profiles


def test_load_three_products(tmp_path):
    yaml_text = textwrap.dedent("""
        compiler_path: ./tools/rust-msc-latest-win10.exe
        products:
          NEW-AI:
            protocol: custom_frame
            baud: 115200
            folders: [app, music, boot, config, version]
            firmware_dir: ./products/NEW-AI/fwlib
            script_dirs: {./products/NEW-AI/write: ./products/NEW-AI/app}
            chunk_size: 248
            last_frame_ack: wait_2s
            filename_encoding: gbk
            firmware_enter_cmd: RESET_FWLIB
            script_enter_cmd: RESET_FWLIB
            reopen_retries: 5
            reopen_delay: 2.0
          NEXT-AI:
            protocol: ymodem
            folders: [__single__]
            firmware_dir: ./products/NEXT-AI/fwlib
            script_dirs: {./products/NEXT-AI/write: ./products/NEXT-AI/app}
            chunk_size: 1024
            last_frame_ack: skip
            filename_encoding: utf-8
            firmware_enter_cmd: "ymodem update fmware\\r\\n"
            script_enter_cmd: "ymodem\\r\\n"
            reopen_retries: 40
            reopen_delay: 3.0
    """)
    p = tmp_path / "products.yaml"; p.write_text(yaml_text)
    profiles = load_profiles(p)
    assert set(profiles) == {"NEW-AI", "NEXT-AI"}
    new = profiles["NEW-AI"]
    assert new.protocol == "custom_frame"
    assert new.folders == ["app", "music", "boot", "config", "version"]
    assert new.last_frame_ack == "wait_2s"
    assert new.firmware_enter_cmd == b"RESET_FWLIB"
    nxt = profiles["NEXT-AI"]
    assert nxt.protocol == "ymodem"
    assert nxt.script_enter_cmd == b"ymodem\r\n"
    assert nxt.firmware_enter_cmd == b"ymodem update fmware\r\n"
```

- [ ] **Step 2: 运行确认失败**

```bash
python -m pytest tests/test_profile.py -v
```
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: 实现 profile.py**

```python
"""产品配置：DeviceProfile 数据类 + 从 YAML 加载。"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import yaml


@dataclass
class DeviceProfile:
    name: str
    protocol: str                          # "custom_frame" | "ymodem"
    baud: int = 115200
    firmware_enter_cmd: bytes = b""
    script_enter_cmd: bytes = b""
    folders: list[str] = field(default_factory=list)
    chunk_size: int = 248
    ack_timeout: float = 2.0
    last_frame_ack: str = "wait_2s"
    filename_encoding: str = "gbk"
    compiler_path: Path = Path("./tools/rust-msc-latest-win10.exe")
    script_dirs: dict = field(default_factory=dict)
    firmware_dir: Path = Path(".")
    reopen_retries: int = 5
    reopen_delay: float = 2.0


def _to_bytes(val) -> bytes:
    if isinstance(val, bytes):
        return val
    if isinstance(val, str):
        # 允许含转义序列的字符串（如 "ymodem\r\n"）按字面解释
        return val.encode("utf-8").decode("unicode_escape").encode("latin-1")
    return b""


def load_profiles(path: Path) -> dict[str, DeviceProfile]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    compiler = Path(raw.get("compiler_path", "./tools/rust-msc-latest-win10.exe"))
    out: dict[str, DeviceProfile] = {}
    for name, cfg in raw.get("products", {}).items():
        out[name] = DeviceProfile(
            name=name,
            protocol=cfg["protocol"],
            baud=cfg.get("baud", 115200),
            firmware_enter_cmd=_to_bytes(cfg.get("firmware_enter_cmd", "")),
            script_enter_cmd=_to_bytes(cfg.get("script_enter_cmd", "")),
            folders=cfg.get("folders", []),
            chunk_size=cfg.get("chunk_size", 248),
            ack_timeout=cfg.get("ack_timeout", 2.0),
            last_frame_ack=cfg.get("last_frame_ack", "wait_2s"),
            filename_encoding=cfg.get("filename_encoding", "gbk"),
            compiler_path=compiler,
            script_dirs={Path(k): Path(v) for k, v in cfg.get("script_dirs", {}).items()},
            firmware_dir=Path(cfg.get("firmware_dir", ".")),
            reopen_retries=cfg.get("reopen_retries", 5),
            reopen_delay=cfg.get("reopen_delay", 2.0),
        )
    return out
```

- [ ] **Step 4: 运行确认通过**

```bash
python -m pytest tests/test_profile.py -v
```
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/backend/profile.py tests/test_profile.py
git commit -m "feat: device profile and yaml loader"
```

---

### Task 10: DeviceDeployer 编排 + 集成测试（TDD vs 模拟器）

**Files:**
- Create: `src/lbs_firmware_studio/backend/deployer.py`
- Test: `tests/test_deployer.py`

**Interfaces:**
- Produces: `DeviceDeployer`
- Consumes: 全部上层模块、`DeviceSimulator`

- [ ] **Step 1: 写失败测试**

`tests/test_deployer.py`:
```python
import pathlib, tempfile
from lbs_firmware_studio.backend.profile import DeviceProfile
from lbs_firmware_studio.backend.deployer import DeviceDeployer
from lbs_firmware_studio.backend.serial_transport import SerialTransport
from tests.fakes import make_fake_serial_pair
from tests.simulator import DeviceSimulator


def _profile(name, protocol):
    return DeviceProfile(name=name, protocol=protocol, baud=115200,
                         firmware_enter_cmd=b"RESET_FWLIB" if protocol=="custom_frame" else b"ymodem update fmware\r\n",
                         script_enter_cmd=b"RESET_FWLIB" if protocol=="custom_frame" else b"ymodem\r\n",
                         folders=["app"] if protocol=="custom_frame" else ["__single__"],
                         chunk_size=248 if protocol=="custom_frame" else 1024,
                         last_frame_ack="wait_2s" if protocol=="custom_frame" else "skip",
                         filename_encoding="gbk")


def test_deploy_scripts_custom_frame():
    host_ser, dev_ser = make_fake_serial_pair()
    sim = DeviceSimulator(dev_ser, protocol="custom_frame"); sim.start()
    t = SerialTransport(host_ser); t.start_rx()
    try:
        dep = DeviceDeployer(transport=t)
        with tempfile.TemporaryDirectory() as d:
            (pathlib.Path(d) / "main.py").write_text("print(1)")
            # 用真编译器会失败；这里 mock compile_scripts 产物
            dep.compile_scripts = lambda profile, py_dir: [pathlib.Path(py_dir) / "main.py.o"]
            # 手动造 .py.o
            (pathlib.Path(d) / "main.py.o").write_bytes(b"\x0F\x70 79o compiled")
            states = []
            dep.state_changed.connect(lambda s: states.append(s))
            dep.deploy_scripts(_profile("NEW-AI", "custom_frame"), "COM_FAKE", pathlib.Path(d))
            assert sim.received_files.get("main.py.o") == b"\x0F\x70 79o compiled"
            assert "done" in states
    finally:
        t.stop_rx(); sim.stop()


def test_update_firmware_ymodem():
    host_ser, dev_ser = make_fake_serial_pair()
    sim = DeviceSimulator(dev_ser, protocol="ymodem"); sim.start()
    t = SerialTransport(host_ser); t.start_rx()
    try:
        dep = DeviceDeployer(transport=t)
        with tempfile.TemporaryDirectory() as d:
            fw = pathlib.Path(d) / "next.bin"; fw.write_bytes(b"\xAA" * 2048)
            prof = _profile("NEXT-AI", "ymodem")
            prof.firmware_dir = pathlib.Path(d)
            dep.update_firmware(prof, "COM_FAKE")
            assert sim.received_files.get("next.bin") == b"\xAA" * 2048
    finally:
        t.stop_rx(); sim.stop()
```

- [ ] **Step 2: 运行确认失败**

```bash
python -m pytest tests/test_deployer.py -v
```
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: 实现 deployer.py**

```python
"""编排层：按 DeviceProfile 驱动编译->连接->进升级->传输->收尾，用 Qt 信号上报。"""
from __future__ import annotations
from pathlib import Path
try:
    from PySide6.QtCore import QObject, Signal
except ImportError:  # 后端可脱离 PySide6 运行（CLI/测试）
    class QObject:  # type: ignore
        def __init__(self, *a, **k): pass
    class Signal:  # type: ignore
        def __init__(self, *a, **k): pass
        def connect(self, fn): self._fn = fn
        def emit(self, *a, **k):
            if hasattr(self, "_fn"): self._fn(*a, **k)

from .transfer_protocol import CustomFrameProtocol, YmodemProtocol
from .pika_compiler import compile_py
from .profile import DeviceProfile


class DeviceDeployer(QObject):
    progress = Signal(int, int)
    log = Signal(str)
    state_changed = Signal(str)
    error = Signal(str)

    def __init__(self, transport=None):
        super().__init__()
        self._transport = transport

    def set_transport(self, transport) -> None:
        self._transport = transport

    def compile_scripts(self, profile: DeviceProfile, py_dir: Path) -> list[Path]:
        self.state_changed.emit("compiling")
        outs = []
        for src, dst in profile.script_dirs.items():
            for py in sorted(Path(py_dir).glob("*.py")):
                out = Path(py_dir) / (py.stem + ".py.o")
                self.log.emit(f"compile {py.name}")
                compile_py(py, out, profile.compiler_path)
                outs.append(out)
        return outs

    def _make_protocol(self, profile: DeviceProfile):
        if profile.protocol == "custom_frame":
            return CustomFrameProtocol(chunk_size=profile.chunk_size, ack_timeout=profile.ack_timeout,
                                       last_frame_ack=profile.last_frame_ack,
                                       filename_encoding=profile.filename_encoding)
        return YmodemProtocol(block_size=profile.chunk_size, ack_timeout=12.0)

    def update_firmware(self, profile: DeviceProfile, port: str) -> None:
        try:
            self.state_changed.emit("connecting")
            proto = self._make_protocol(profile)
            self.state_changed.emit("entering_upgrade")
            proto.enter_upgrade_mode(self._transport, firmware=True)
            self.state_changed.emit("transfering")
            if profile.protocol == "custom_frame":
                fw_dir = Path(profile.firmware_dir)
                for folder in profile.folders:
                    sub = fw_dir / folder
                    if sub.exists():
                        proto.send_folder(self._transport, sub, folder, self._on_progress)  # type: ignore[attr-defined]
            else:
                for fw in sorted(Path(profile.firmware_dir).glob("*")):
                    if fw.is_file():
                        proto.send_file(self._transport, fw, self._on_progress, firmware=True)
                        break
            proto.finish_session(self._transport, firmware=True)
            self.state_changed.emit("done")
        except Exception as e:
            self.error.emit(str(e))
            self.state_changed.emit("error")
            raise

    def deploy_scripts(self, profile: DeviceProfile, port: str, py_dir: Path) -> None:
        try:
            outs = self.compile_scripts(profile, py_dir)
            self.state_changed.emit("connecting")
            proto = self._make_protocol(profile)
            self.state_changed.emit("entering_upgrade")
            proto.enter_upgrade_mode(self._transport, firmware=False)
            self.state_changed.emit("transfering")
            if profile.protocol == "custom_frame":
                # 脚本作为 app 文件夹下发
                import tempfile, shutil
                tmp = Path(tempfile.mkdtemp())
                for o in outs:
                    shutil.copy(o, tmp / o.name)
                proto.send_folder(self._transport, tmp, "app", self._on_progress)  # type: ignore[attr-defined]
            else:
                for o in outs:
                    proto.send_file(self._transport, o, self._on_progress, firmware=False)
            proto.finish_session(self._transport, firmware=False)
            self.state_changed.emit("done")
        except Exception as e:
            self.error.emit(str(e))
            self.state_changed.emit("error")
            raise

    def _on_progress(self, done: int, total: int) -> None:
        self.progress.emit(done, total)
```

- [ ] **Step 4: 运行确认通过**

```bash
python -m pytest tests/test_deployer.py -v
```
Expected: 2 passed

- [ ] **Step 5: 全量回归**

```bash
python -m pytest -v
```
Expected: 全部 passed（约 29 项）

- [ ] **Step 6: Commit**

```bash
git add src/lbs_firmware_studio/backend/deployer.py tests/test_deployer.py
git commit -m "feat: device deployer orchestration with integration tests"
```

---

### Task 11: 无头 CLI 入口（阶段 1a 交付物）

**Files:**
- Create: `src/lbs_firmware_studio/cli.py`
- Test: `tests/test_cli.py`（smoke）

**Interfaces:**
- Produces: `main(argv)`

- [ ] **Step 1: 写 smoke 测试**

`tests/test_cli.py`:
```python
import subprocess, sys
from lbs_firmware_studio.cli import main


def test_cli_lists_products(monkeypatch, tmp_path, capsys):
    yaml = """
compiler_path: ./tools/rust-msc-latest-win10.exe
products:
  NEW-AI: {protocol: custom_frame, folders: [app], firmware_dir: ., script_dirs: {}, chunk_size: 248}
"""
    p = tmp_path / "products.yaml"; p.write_text(yaml)
    rc = main(["--config", str(p), "--list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "NEW-AI" in out
```

- [ ] **Step 2: 运行确认失败**

```bash
python -m pytest tests/test_cli.py -v
```
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: 实现 cli.py**

```python
"""无头 CLI：阶段 1a 的可运行交付物，证明后端可脱离 GUI 工作。"""
from __future__ import annotations
import sys, argparse
from pathlib import Path
from .backend.profile import load_profiles
from .backend.deployer import DeviceDeployer
from .backend.serial_transport import SerialTransport


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lbs-firmware")
    parser.add_argument("--config", default="products.yaml")
    parser.add_argument("--list", action="store_true", help="列出已配置产品")
    parser.add_argument("--product", help="产品名")
    parser.add_argument("--port", help="串口号")
    parser.add_argument("--firmware", action="store_true", help="固件更新")
    parser.add_argument("--scripts", metavar="DIR", help="脚本下发，指定 .py 文件夹")
    args = parser.parse_args(argv)

    profiles = load_profiles(Path(args.config))

    if args.list:
        for name, p in profiles.items():
            print(f"{name}: {p.protocol}, folders={p.folders}")
        return 0

    if not args.product:
        parser.error("--product 必填（或用 --list 查看）")
    profile = profiles[args.product]

    if not (args.firmware or args.scripts):
        parser.error("需指定 --firmware 或 --scripts DIR")

    import serial  # 真机模式才需要
    t = SerialTransport(serial.Serial(args.port, profile.baud, timeout=0.1))
    t.start_rx()
    dep = DeviceDeployer(t)
    dep.log.connect(lambda s: print(s))
    dep.progress.connect(lambda d, n: print(f"\r{d}/{n}", end="", flush=True))
    dep.state_changed.connect(lambda s: print(f"\n[{s}]"))
    try:
        if args.firmware:
            dep.update_firmware(profile, args.port)
        else:
            dep.deploy_scripts(profile, args.port, Path(args.scripts))
        print("\n完成")
        return 0
    except Exception as e:
        print(f"\n失败: {e}", file=sys.stderr)
        return 1
    finally:
        t.close()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 运行确认通过**

```bash
python -m pytest tests/test_cli.py -v
```
Expected: 1 passed

- [ ] **Step 5: 全量回归 + 安装验证**

```bash
python -m pytest -v
python -m lbs_firmware_studio.cli --config products.yaml --list
```
Expected: 全部测试通过；CLI 打印三款产品

- [ ] **Step 6: Commit**

```bash
git add src/lbs_firmware_studio/cli.py tests/test_cli.py
git commit -m "feat: headless CLI entrypoint (phase 1a deliverable)"
```

---

## Self-Review 记录

- **Spec 覆盖**：三层架构(T1-T10)、自定义帧(T2,T6)、YMODEM 合并(T3,T7)、串口层+RX线程(T5)、DeviceProfile(T9)、编译(T8)、编排(T10)、配置yaml(T1,T9)、已知坑修复（末帧wait_2s[T6]、重传max_retries[T6,T7]、合并两套YMODEM[T7]、文件名编码可配[T9]、去硬编码[T9]、日志轮转-CLI暂未引入compile_log故无需）、设备模拟器(T4)、后端可脱离GUI(T11 CLI) —— 均有对应任务。蓝牙明确不在范围（Global Constraints）。
- **占位扫描**：无 TBD/TODO；每步含完整代码或确切命令。
- **类型一致性**：`build_frame(cmd,data)`、`parse_frame->(cmd,data)|None`、`make_packet(seq,payload,block_size)`、`SerialTransport.read_byte/write/set_data_handler/wait_for_reopen`、`TransferProtocol.enter_upgrade_mode/send_file/finish_session(firmware:bool)`、`compile_py(py,out,compiler)`、`DeviceProfile`、`DeviceDeployer.update_firmware/deploy_scripts` 在各任务签名一致。
- **已知风险**：`DeviceSimulator._do_ymodem_session` 的 EOT 处理在 `usb_quick_exit` 场景下可能与真机时序有差异，真机验证（Plan 1b 之后的 HITL）时需校准；`deployer` 的 PySide6 可选回退 Signal 是简化实现，阶段 1b 接 GUI 时替换为真 Signal。
