# 设备数据监控页 + NEW-AI 传感器更新 · 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增独立「数据监控」页，实时解析设备流式 JSON 并按端口卡片展示 + 底部主机状态栏；NEW-AI 额外支持传感器更新指令下发。

**Architecture:** 纯逻辑（行解析 `MonitorParser`、组帧 `sensor_update`）放 `backend/`，零 GUI 依赖。`MonitorWorker` 是普通 `QObject`，用现有 `SerialTransport` 的 RX 后台线程 + `set_data_handler` 接原始字节，喂解析器后经 Qt signal（跨线程自动 QueuedConnection）把 dict 送主线程。`MonitorPage` 用「最新帧缓存 + QTimer 节流」渲染卡片与状态栏，产品差异由 `MONITOR_PROFILES` 表驱动。

**Tech Stack:** Python 3.13、PySide6、qtawesome、pytest-qt、pyserial（测试用 `tests/fakes.py::FakeSerial`）。

## Global Constraints

- Python 3.13、Windows、解释器命令用 `python`（非 `python3`）。
- **GUI 层只做界面**：串口读写经 `MonitorWorker` 调 `SerialTransport`；解析/组帧纯函数放 `backend/`，不 import 任何 PySide6。
- 深色主题：颜色/圆角一律取 `theme.*` 常量，禁止硬编码色值。
- 事件/信号处理器中先 `super()` 再 `emit`（避免 use-after-delete）。
- 测试用 pytest-qt + `qtbot.addWidget` + 手动调用槽/`emit`，**不碰真串口**；GUI 测试按文件单独跑，容忍多线程 teardown 段错误（以断言结果为准）。
- 监控串口连接独立于部署：`start_monitor()` 才 open，`stop_monitor()` 才 close。
- 帧协议复用现有 `backend/protocol_frame.py`：`build_frame(cmd, data)` → `[5A 97 98][len][cmd][data][checksum=sum&0xFF][A5]`。
- 现有 nav 已有 `("monitor", "数据监控", "fa5s.chart-line", False)` 项（当前禁用），本计划将其启用。

---

## File Structure

**新增（backend，纯逻辑）:**
- `src/lbs_firmware_studio/backend/monitor_parser.py` — `MonitorParser` 行缓冲 + JSON 解析。
- `src/lbs_firmware_studio/backend/sensor_update.py` — 设备类型 ID 常量 + `build_sensor_update_frame()` + `SENSOR_UPDATE_OPTIONS`。

**新增（GUI）:**
- `src/lbs_firmware_studio/gui/pages/monitor_profiles.py` — `MONITOR_PROFILES` 表 + `SENSOR_NAMES` 映射 + `get_by_path()` 点路径取值。
- `src/lbs_firmware_studio/gui/widgets/sensor_card.py` — `SensorCard` 通用键值卡片。
- `src/lbs_firmware_studio/gui/widgets/host_status_bar.py` — `HostStatusBar` 底部主机状态栏。
- `src/lbs_firmware_studio/gui/monitor_worker.py` — `MonitorWorker(QObject)`。
- `src/lbs_firmware_studio/gui/pages/monitor_page.py` — `MonitorPage` 组装。
- `src/lbs_firmware_studio/gui/dialogs/__init__.py` + `src/lbs_firmware_studio/gui/dialogs/sensor_update_dialog.py` — `SensorUpdateDialog`。

**修改:**
- `src/lbs_firmware_studio/gui/main_window.py` — 启用 monitor nav、`_make_page` 接入 `MonitorPage`、导航离开时停监控。

**新增测试:**
- `tests/test_monitor_parser.py`、`tests/test_sensor_update.py`
- `tests/gui/test_monitor_profiles.py`、`tests/gui/test_sensor_card.py`、`tests/gui/test_host_status_bar.py`、`tests/gui/test_monitor_worker.py`、`tests/gui/test_monitor_page.py`、`tests/gui/test_sensor_update_dialog.py`
- 修改 `tests/gui/test_main_window.py`

---

## Task 1: MonitorParser（行缓冲 + JSON 解析）

**Files:**
- Create: `src/lbs_firmware_studio/backend/monitor_parser.py`
- Test: `tests/test_monitor_parser.py`

**Interfaces:**
- Consumes: 无（纯 stdlib）。
- Produces: `class MonitorParser` with `feed(data: bytes) -> list[dict]`；类属性 `MAX_BUFFER = 64 * 1024`。

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_monitor_parser.py
from lbs_firmware_studio.backend.monitor_parser import MonitorParser


def test_single_complete_line():
    p = MonitorParser()
    frames = p.feed(b'{"a": 1}\r\n')
    assert frames == [{"a": 1}]


def test_multiple_lines_one_feed():
    p = MonitorParser()
    frames = p.feed(b'{"a": 1}\r\n{"b": 2}\r\n')
    assert frames == [{"a": 1}, {"b": 2}]


def test_half_line_across_chunks():
    p = MonitorParser()
    assert p.feed(b'{"a": ') == []          # 半行留缓冲
    assert p.feed(b'1}\r\n') == [{"a": 1}]   # 补齐后解析


def test_plain_newline_also_splits():
    p = MonitorParser()
    assert p.feed(b'{"a": 1}\n') == [{"a": 1}]


def test_bad_json_line_dropped_silently():
    p = MonitorParser()
    frames = p.feed(b'not json\r\n{"ok": 1}\r\n')
    assert frames == [{"ok": 1}]            # 坏行丢弃，好行保留


def test_non_object_json_dropped():
    p = MonitorParser()
    # 顶层非 dict（如数组/数字）丢弃，只保留 dict
    assert p.feed(b'[1,2]\r\n42\r\n{"x": 1}\r\n') == [{"x": 1}]


def test_buffer_overflow_resets():
    p = MonitorParser()
    p.feed(b"x" * (MonitorParser.MAX_BUFFER + 10))   # 无换行超上限 -> 清空
    assert p.feed(b'{"a": 1}\r\n') == [{"a": 1}]      # 清空后仍能正常解析
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_monitor_parser.py -v`
Expected: FAIL（`ModuleNotFoundError: monitor_parser`）

- [ ] **Step 3: Write minimal implementation**

```python
# src/lbs_firmware_studio/backend/monitor_parser.py
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
        # 缓冲超上限且仍无换行 -> 异常流，清空防内存膨胀
        if len(self._buf) > self.MAX_BUFFER and b"\n" not in self._buf:
            self._buf.clear()
            return []
        out: list[dict] = []
        while b"\n" in self._buf:
            line, _, rest = self._buf.partition(b"\n")
            self._buf = bytearray(rest)
            obj = self._parse_line(bytes(line))
            if obj is not None:
                out.append(obj)
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_monitor_parser.py -v`
Expected: PASS（7 passed）

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/backend/monitor_parser.py tests/test_monitor_parser.py
git commit -m "feat(backend): MonitorParser line-buffered JSON stream parser"
```

---

## Task 2: sensor_update 组帧（NEW-AI 传感器更新指令）

**Files:**
- Create: `src/lbs_firmware_studio/backend/sensor_update.py`
- Test: `tests/test_sensor_update.py`

**Interfaces:**
- Consumes: `backend/protocol_frame.build_frame(cmd: int, data: bytes) -> bytes`（已有）。
- Produces:
  - 常量 `CMD_SENSOR_UPDATE = 0x32`、`KEEP = 0xFF`。
  - `DEV_ID_BIG_MOTOR=0xA1, DEV_ID_SMALL_MOTOR=0xA6, DEV_ID_COLOR=0xA2, DEV_ID_ULTRASION=0xA3, DEV_ID_TOUCH=0xA4, DEV_ID_CAMER=0xA7, DEV_ID_GRAY=0xA9, DEV_ID_GRAY_V2=0xB0, DEV_ID_NFC=0xB2`。
  - `SENSOR_UPDATE_OPTIONS: list[tuple[str, int]]`（首项 `("保持不动", 0xFF)`）。
  - `build_sensor_update_frame(port_ids: list[int]) -> bytes`。

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_sensor_update.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_sensor_update.py -v`
Expected: FAIL（`ModuleNotFoundError: sensor_update`）

- [ ] **Step 3: Write minimal implementation**

```python
# src/lbs_firmware_studio/backend/sensor_update.py
"""NEW-AI 传感器更新指令：为 8 端口指定目标设备类型 ID，组帧下发。

帧格式复用 protocol_frame：5A 97 98 08 32 [A..H] checksum A5。
每字节为该端口目标设备类型 ID，0xFF=保持不动。设备类型 ID 源码核实自
e:/LBS-NEW-AI/Drivers/DataFile/*。即发即忘，不等 ACK。
"""
from __future__ import annotations
from .protocol_frame import build_frame

CMD_SENSOR_UPDATE = 0x32
KEEP = 0xFF

DEV_ID_BIG_MOTOR = 0xA1
DEV_ID_SMALL_MOTOR = 0xA6
DEV_ID_COLOR = 0xA2
DEV_ID_ULTRASION = 0xA3
DEV_ID_TOUCH = 0xA4
DEV_ID_CAMER = 0xA7
DEV_ID_GRAY = 0xA9
DEV_ID_GRAY_V2 = 0xB0
DEV_ID_NFC = 0xB2

# 下拉框选项：(显示名, id 值)，首项为保持不动
SENSOR_UPDATE_OPTIONS: list[tuple[str, int]] = [
    ("保持不动", KEEP),
    ("大电机", DEV_ID_BIG_MOTOR),
    ("中电机", DEV_ID_SMALL_MOTOR),
    ("颜色", DEV_ID_COLOR),
    ("超声波", DEV_ID_ULTRASION),
    ("触摸", DEV_ID_TOUCH),
    ("摄像头", DEV_ID_CAMER),
    ("灰度", DEV_ID_GRAY),
    ("灰度V2", DEV_ID_GRAY_V2),
    ("NFC", DEV_ID_NFC),
]


def build_sensor_update_frame(port_ids: list[int]) -> bytes:
    """8 个端口目标设备类型 ID -> 完整指令帧。长度必须为 8。"""
    if len(port_ids) != 8:
        raise ValueError(f"port_ids 必须正好 8 个，收到 {len(port_ids)}")
    return build_frame(CMD_SENSOR_UPDATE, bytes(port_ids))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_sensor_update.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/backend/sensor_update.py tests/test_sensor_update.py
git commit -m "feat(backend): sensor update frame builder for NEW-AI"
```

---

## Task 3: 产品参数化表 monitor_profiles

**Files:**
- Create: `src/lbs_firmware_studio/gui/pages/monitor_profiles.py`
- Test: `tests/gui/test_monitor_profiles.py`

**Interfaces:**
- Consumes: 无。
- Produces:
  - `MONITOR_PROFILES: dict[str, dict]`，每项 `{"ports": int, "status_fields": list[tuple[str, str]], "sensor_update": bool}`。
  - `SENSOR_NAMES: dict[str, str]`（JSON key → 中文名）。
  - `get_by_path(data: dict, path: str) -> object | None`（点路径取嵌套值）。
  - `sensor_display_name(key: str) -> str`（未知 key 原样返回）。

- [ ] **Step 1: Write the failing tests**

```python
# tests/gui/test_monitor_profiles.py
from lbs_firmware_studio.gui.pages.monitor_profiles import (
    MONITOR_PROFILES, SENSOR_NAMES, get_by_path, sensor_display_name,
)


def test_profiles_ports():
    assert MONITOR_PROFILES["NEW-AI"]["ports"] == 8
    assert MONITOR_PROFILES["SPARK-AI"]["ports"] == 4
    assert MONITOR_PROFILES["NEXT-AI"]["ports"] == 2


def test_sensor_update_only_new_ai():
    assert MONITOR_PROFILES["NEW-AI"]["sensor_update"] is True
    assert MONITOR_PROFILES["SPARK-AI"]["sensor_update"] is False
    assert MONITOR_PROFILES["NEXT-AI"]["sensor_update"] is False


def test_status_fields_have_label_and_path():
    for prof in MONITOR_PROFILES.values():
        for item in prof["status_fields"]:
            assert isinstance(item, tuple) and len(item) == 2


def test_get_by_path_flat():
    assert get_by_path({"version": 317}, "version") == 317


def test_get_by_path_nested():
    assert get_by_path({"adc": {"bat": "82%"}}, "adc.bat") == "82%"


def test_get_by_path_missing_returns_none():
    assert get_by_path({"adc": {}}, "adc.bat") is None
    assert get_by_path({}, "x.y.z") is None


def test_sensor_display_name_known_and_unknown():
    assert sensor_display_name("big_motor") == "大电机"
    assert sensor_display_name("color") == "颜色"
    assert sensor_display_name("gray_v2") == "灰度V2"
    assert sensor_display_name("weird_key") == "weird_key"   # 未知原样返回
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/gui/test_monitor_profiles.py -v`
Expected: FAIL（`ModuleNotFoundError: monitor_profiles`）

- [ ] **Step 3: Write minimal implementation**

```python
# src/lbs_firmware_studio/gui/pages/monitor_profiles.py
"""数据监控的产品参数化：卡片数 / 底部状态字段 / 是否显示传感器更新，
以及传感器 JSON key -> 中文名映射。纯数据 + 取值辅助，无 Qt 依赖。"""
from __future__ import annotations

MONITOR_PROFILES: dict[str, dict] = {
    "NEW-AI": {
        "ports": 8,
        "status_fields": [
            ("主机", "MAC"), ("版本", "version"), ("电量", "bat"),
            ("运行状态", "NewAiState"), ("IMU", "mem"),
            ("音量", "voic"), ("Heap", "heap"),
        ],
        "sensor_update": True,
    },
    "SPARK-AI": {
        "ports": 4,
        "status_fields": [
            ("版本", "version"), ("电量", "adc.bat"),
            ("运行状态", "WillAiState"), ("Heap", "heap"),
        ],
        "sensor_update": False,
    },
    "NEXT-AI": {
        "ports": 2,
        "status_fields": [
            ("蓝牙名", "btName"), ("版本", "version"), ("电量", "adc.bat"),
            ("IR", "adc.ir"), ("运行状态", "State"), ("Heap", "heap"),
        ],
        "sensor_update": False,
    },
}

SENSOR_NAMES: dict[str, str] = {
    "big_motor": "大电机", "small_motor": "中电机",
    "color": "颜色", "ultrasion": "超声波", "touch": "触摸",
    "camer": "摄像头", "gray": "灰度", "gray_v2": "灰度V2", "nfc": "NFC",
    "dev null": "无设备",
}


def get_by_path(data: dict, path: str):
    """点路径取嵌套值，如 'adc.bat'；任一层缺失返回 None。"""
    cur = data
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def sensor_display_name(key: str) -> str:
    return SENSOR_NAMES.get(key, key)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/gui/test_monitor_profiles.py -v`
Expected: PASS（7 passed）

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/gui/pages/monitor_profiles.py tests/gui/test_monitor_profiles.py
git commit -m "feat(gui): MONITOR_PROFILES product table + sensor name map + path getter"
```

---

## Task 4: SensorCard 通用键值卡片

**Files:**
- Create: `src/lbs_firmware_studio/gui/widgets/sensor_card.py`
- Test: `tests/gui/test_sensor_card.py`

**Interfaces:**
- Consumes: `monitor_profiles.sensor_display_name`；`theme`。
- Produces: `class SensorCard(QFrame)`：`__init__(port: int)`；`update(sensor_key: str | None, fields: dict) -> None`；测试访问器 `title_text() -> str`、`rows() -> list[tuple[str, str]]`。
  - `update(None, {})` → 空态：标题 `端口 N`，无行。
  - `update("color", {...})` → 标题 `端口 N · 颜色`，字段逐行。

- [ ] **Step 1: Write the failing tests**

```python
# tests/gui/test_sensor_card.py
from lbs_firmware_studio.gui.widgets.sensor_card import SensorCard


def test_empty_state_title_no_rows(qtbot):
    c = SensorCard(3); qtbot.addWidget(c)
    c.update(None, {})
    assert c.title_text() == "端口 3"
    assert c.rows() == []


def test_sensor_title_uses_chinese_name(qtbot):
    c = SensorCard(2); qtbot.addWidget(c)
    c.update("color", {"r": 10, "g": 20, "b": 30, "lux": 1615})
    assert c.title_text() == "端口 2 · 颜色"


def test_sensor_fields_as_rows(qtbot):
    c = SensorCard(0); qtbot.addWidget(c)
    c.update("ultrasion", {"cm": "255"})
    assert ("cm", "255") in c.rows()


def test_update_replaces_previous_rows(qtbot):
    c = SensorCard(1); qtbot.addWidget(c)
    c.update("touch", {"state": 1})
    c.update(None, {})                 # 设备拔出 -> 回到空态
    assert c.title_text() == "端口 1"
    assert c.rows() == []


def test_all_field_values_stringified(qtbot):
    c = SensorCard(0); qtbot.addWidget(c)
    c.update("gray", {"1": 100, "b1": 0})
    assert ("1", "100") in c.rows()
    assert ("b1", "0") in c.rows()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/gui/test_sensor_card.py -v`
Expected: FAIL（`ModuleNotFoundError: sensor_card`）

- [ ] **Step 3: Write minimal implementation**

```python
# src/lbs_firmware_studio/gui/widgets/sensor_card.py
"""通用键值传感器卡片：标题=端口+中文类型名，下方逐行 键: 值。
MVP 方案（对所有传感器/产品统一适用，字段增改无需改代码）。"""
from __future__ import annotations
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QGridLayout, QWidget
from .. import theme
from ..pages.monitor_profiles import sensor_display_name


class SensorCard(QFrame):
    def __init__(self, port: int, parent=None):
        super().__init__(parent)
        self._port = port
        self._rows: list[tuple[str, str]] = []
        self.setObjectName("card")
        self.setMinimumHeight(120)

        self._title = QLabel()
        self._title.setStyleSheet(
            f"font-weight:600; color:{theme.TEXT_PRIMARY}; background:transparent;")
        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(12)
        self._grid.setVerticalSpacing(2)

        lay = QVBoxLayout(self)
        lay.addWidget(self._title)
        lay.addWidget(self._grid_host)
        lay.addStretch(1)

        self.update(None, {})

    def update(self, sensor_key: "str | None", fields: dict) -> None:
        if sensor_key:
            self._title.setText(f"端口 {self._port} · {sensor_display_name(sensor_key)}")
        else:
            self._title.setText(f"端口 {self._port}")
        self._rows = [(str(k), str(v)) for k, v in fields.items()]
        self._rebuild_grid()

    def _rebuild_grid(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        for i, (k, v) in enumerate(self._rows):
            klab = QLabel(k + ":")
            klab.setStyleSheet(f"color:{theme.TEXT_SECONDARY}; background:transparent;")
            vlab = QLabel(v)
            vlab.setStyleSheet(f"color:{theme.TEXT_PRIMARY}; background:transparent;")
            self._grid.addWidget(klab, i, 0)
            self._grid.addWidget(vlab, i, 1)

    # --- 测试访问器 ---
    def title_text(self) -> str:
        return self._title.text()

    def rows(self) -> list[tuple[str, str]]:
        return list(self._rows)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/gui/test_sensor_card.py -v`
Expected: PASS（5 passed）

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/gui/widgets/sensor_card.py tests/gui/test_sensor_card.py
git commit -m "feat(gui): SensorCard generic key-value sensor card"
```

---

## Task 5: HostStatusBar 主机状态栏

**Files:**
- Create: `src/lbs_firmware_studio/gui/widgets/host_status_bar.py`
- Test: `tests/gui/test_host_status_bar.py`

**Interfaces:**
- Consumes: `monitor_profiles.get_by_path`；`theme`。
- Produces: `class HostStatusBar(QFrame)`：`set_fields(status_fields: list[tuple[str, str]]) -> None`（配置 label + 点路径）；`update_from(frame: dict) -> None`（按帧刷新）；测试访问器 `field_text(label: str) -> str`。
  - 取不到显示 `--`。
  - `mem` 路径值为 dict（`{yaw,pitch,roll}`）时组合成 `yaw/pitch/roll` 字符串。

- [ ] **Step 1: Write the failing tests**

```python
# tests/gui/test_host_status_bar.py
from lbs_firmware_studio.gui.widgets.host_status_bar import HostStatusBar


def test_flat_field(qtbot):
    b = HostStatusBar(); qtbot.addWidget(b)
    b.set_fields([("版本", "version")])
    b.update_from({"version": 317})
    assert b.field_text("版本") == "317"


def test_nested_path_field(qtbot):
    b = HostStatusBar(); qtbot.addWidget(b)
    b.set_fields([("电量", "adc.bat")])
    b.update_from({"adc": {"bat": "82%"}})
    assert b.field_text("电量") == "82%"


def test_missing_shows_dashes(qtbot):
    b = HostStatusBar(); qtbot.addWidget(b)
    b.set_fields([("电量", "adc.bat")])
    b.update_from({"adc": {}})
    assert b.field_text("电量") == "--"


def test_imu_dict_combined(qtbot):
    b = HostStatusBar(); qtbot.addWidget(b)
    b.set_fields([("IMU", "mem")])
    b.update_from({"mem": {"yaw": "60.31", "pitch": "179.39", "roll": "-0.34"}})
    assert b.field_text("IMU") == "60.31/179.39/-0.34"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/gui/test_host_status_bar.py -v`
Expected: FAIL（`ModuleNotFoundError: host_status_bar`）

- [ ] **Step 3: Write minimal implementation**

```python
# src/lbs_firmware_studio/gui/widgets/host_status_bar.py
"""底部主机状态栏：按产品 status_fields(label + json 点路径) 显示。
取不到显示 '--'；mem 这类 dict 值组合成 yaw/pitch/roll。"""
from __future__ import annotations
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel
from .. import theme
from ..pages.monitor_profiles import get_by_path


class HostStatusBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self._fields: list[tuple[str, str]] = []
        self._value_labels: dict[str, QLabel] = {}
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(12, 6, 12, 6)
        self._lay.setSpacing(18)

    def set_fields(self, status_fields: list[tuple[str, str]]) -> None:
        # 清空旧字段
        while self._lay.count():
            item = self._lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._fields = list(status_fields)
        self._value_labels = {}
        for label, _path in self._fields:
            cap = QLabel(f"{label}:")
            cap.setStyleSheet(f"color:{theme.TEXT_SECONDARY}; background:transparent;")
            val = QLabel("--")
            val.setStyleSheet(f"color:{theme.TEXT_PRIMARY}; background:transparent;")
            self._lay.addWidget(cap)
            self._lay.addWidget(val)
            self._value_labels[label] = val
        self._lay.addStretch(1)

    def update_from(self, frame: dict) -> None:
        for label, path in self._fields:
            raw = get_by_path(frame, path)
            self._value_labels[label].setText(self._format(raw))

    @staticmethod
    def _format(raw) -> str:
        if raw is None:
            return "--"
        if isinstance(raw, dict):
            # 如 mem={yaw,pitch,roll} -> 组合
            return "/".join(str(v) for v in raw.values())
        return str(raw)

    # --- 测试访问器 ---
    def field_text(self, label: str) -> str:
        return self._value_labels[label].text() if label in self._value_labels else ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/gui/test_host_status_bar.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/gui/widgets/host_status_bar.py tests/gui/test_host_status_bar.py
git commit -m "feat(gui): HostStatusBar product-driven host status bar"
```

---

## Task 6: MonitorWorker（QObject，串口 RX → 解析 → 信号）

**Files:**
- Create: `src/lbs_firmware_studio/gui/monitor_worker.py`
- Test: `tests/gui/test_monitor_worker.py`

**Interfaces:**
- Consumes: `SerialTransport`（已有：`open/start_rx/close/write/set_data_handler`）；`MonitorParser`。
- Produces: `class MonitorWorker(QObject)`：
  - signals：`frame_parsed = Signal(object)`（payload dict）、`error = Signal(str)`、`state_changed = Signal(str)`（`"connected"`/`"disconnected"`）。
  - `__init__(transport=None)`：可注入 transport（测试用 FakeSerial 构造）。
  - `start(port: str, baud: int) -> None`：open→set_data_handler(self._on_data)→start_rx→emit `state_changed("connected")`；失败 emit `error` + `state_changed("disconnected")`。
  - `send_frame(frame: bytes) -> None`：`transport.write(frame)`。
  - `stop() -> None`：`transport.close()`→emit `state_changed("disconnected")`。
  - `_on_data(data: bytes)`：喂 parser，每帧 `frame_parsed.emit(dict)`（此方法在 transport RX 线程被调用，Qt 自动 QueuedConnection 切主线程）。

- [ ] **Step 1: Write the failing tests**

```python
# tests/gui/test_monitor_worker.py
from lbs_firmware_studio.gui.monitor_worker import MonitorWorker
from lbs_firmware_studio.backend.serial_transport import SerialTransport
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fakes import make_fake_serial_pair


def test_on_data_emits_parsed_frame(qtbot):
    w = MonitorWorker()
    got = []
    w.frame_parsed.connect(lambda d: got.append(d))
    w._on_data(b'{"version": 317}\r\n')
    assert got == [{"version": 317}]


def test_on_data_half_line_buffers(qtbot):
    w = MonitorWorker()
    got = []
    w.frame_parsed.connect(lambda d: got.append(d))
    w._on_data(b'{"a": ')
    assert got == []
    w._on_data(b'1}\r\n')
    assert got == [{"a": 1}]


def test_send_frame_writes_to_transport(qtbot):
    dev, host = make_fake_serial_pair()
    transport = SerialTransport(serial_obj=host)
    transport.open("COMX", 115200)
    w = MonitorWorker(transport=transport)
    w.send_frame(bytes([0x5A, 0x97, 0x98]))
    # 对端 dev 应收到这些字节
    import queue
    got = [dev.read(1)[0] for _ in range(3)]
    assert got == [0x5A, 0x97, 0x98]


def test_start_emits_connected(qtbot):
    dev, host = make_fake_serial_pair()
    transport = SerialTransport(serial_obj=host)
    w = MonitorWorker(transport=transport)
    states = []
    w.state_changed.connect(lambda s: states.append(s))
    w.start("COMX", 115200)
    assert "connected" in states
    w.stop()
    assert "disconnected" in states
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/gui/test_monitor_worker.py -v`
Expected: FAIL（`ModuleNotFoundError: monitor_worker`）

- [ ] **Step 3: Write minimal implementation**

```python
# src/lbs_firmware_studio/gui/monitor_worker.py
"""监控 worker：普通 QObject。用 SerialTransport 的 RX 后台线程 + set_data_handler
接原始字节，喂 MonitorParser，每帧经 frame_parsed 信号送主线程。

_on_data 在 transport 的 RX 线程被调用；MonitorWorker 存活于主线程，故 emit 会被
Qt 自动以 QueuedConnection 投递到主线程，UI 更新安全。绝不在此碰 widget。
"""
from __future__ import annotations
from PySide6.QtCore import QObject, Signal
from ..backend.serial_transport import SerialTransport
from ..backend.monitor_parser import MonitorParser


class MonitorWorker(QObject):
    frame_parsed = Signal(object)   # payload: dict
    error = Signal(str)
    state_changed = Signal(str)     # "connected" | "disconnected"

    def __init__(self, transport: "SerialTransport | None" = None, parent=None):
        super().__init__(parent)
        self._transport = transport if transport is not None else SerialTransport()
        self._parser = MonitorParser()

    def start(self, port: str, baud: int) -> None:
        try:
            self._parser = MonitorParser()          # 每次连接重置缓冲
            self._transport.open(port, baud)
            self._transport.set_data_handler(self._on_data)
            self._transport.start_rx()
            self.state_changed.emit("connected")
        except Exception as e:
            self.error.emit(f"打开串口失败: {e}")
            self.state_changed.emit("disconnected")

    def send_frame(self, frame: bytes) -> None:
        try:
            self._transport.write(frame)
        except Exception as e:
            self.error.emit(f"下发失败: {e}")

    def stop(self) -> None:
        try:
            self._transport.close()
        except Exception:
            pass
        self.state_changed.emit("disconnected")

    def _on_data(self, data: bytes) -> None:
        for frame in self._parser.feed(data):
            self.frame_parsed.emit(frame)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/gui/test_monitor_worker.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/gui/monitor_worker.py tests/gui/test_monitor_worker.py
git commit -m "feat(gui): MonitorWorker streams serial RX to parsed-frame signals"
```

---

## Task 7: MonitorPage 组装（卡片 + 状态栏 + 节流渲染 + 启停）

**Files:**
- Create: `src/lbs_firmware_studio/gui/pages/monitor_page.py`
- Test: `tests/gui/test_monitor_page.py`

**Interfaces:**
- Consumes: `MonitorWorker`、`SensorCard`、`HostStatusBar`、`PortSelector`、`MONITOR_PROFILES`、`theme`、qtawesome。
- Produces: `class MonitorPage(QWidget)`：
  - `set_profile(profile) -> None`：查表建 N 张 `SensorCard`（左半 / 右半两列），配置状态栏字段，按 `sensor_update` 显隐传感器更新按钮；未知产品显示提示。
  - `set_port_getter(fn) -> None`。
  - `_on_frame(frame: dict) -> None`：只写 `self._latest`（连到 worker.frame_parsed）。
  - `_render() -> None`：把 `self._latest` 渲染到卡片 + 状态栏（QTimer 100ms 周期调用）。
  - `start_monitor() / stop_monitor()`：管理 worker 生命周期。
  - 测试访问器：`card_count() -> int`、`card_at(port) -> SensorCard`、`has_sensor_update_button() -> bool`、`latest_frame() -> dict | None`。

- [ ] **Step 1: Write the failing tests**

```python
# tests/gui/test_monitor_page.py
from lbs_firmware_studio.gui.pages.monitor_page import MonitorPage
from lbs_firmware_studio.backend.profile import DeviceProfile


def _profile(name):
    return DeviceProfile(name=name, protocol="custom_frame")


NEW_AI_FRAME = {
    "deviceList": [
        {"port": 0, "color": {"r": 1, "g": 2, "b": 3, "lux": 1615}},
        {"port": 1}, {"port": 2, "ultrasion": {"cm": "255"}},
        {"port": 3}, {"port": 4}, {"port": 5}, {"port": 6}, {"port": 7},
    ],
    "version": 317, "bat": "100.00",
    "mem": {"yaw": "60.31", "pitch": "179.39", "roll": "-0.34"},
    "voic": "0.07", "heap": "236624", "MAC": "EC230905AA48",
    "NewAiState": "stop",
}


def test_new_ai_has_8_cards_and_update_button(qtbot):
    p = MonitorPage(); qtbot.addWidget(p)
    p.set_profile(_profile("NEW-AI"))
    assert p.card_count() == 8
    assert p.has_sensor_update_button() is True


def test_spark_ai_has_4_cards_no_update_button(qtbot):
    p = MonitorPage(); qtbot.addWidget(p)
    p.set_profile(_profile("SPARK-AI"))
    assert p.card_count() == 4
    assert p.has_sensor_update_button() is False


def test_next_ai_has_2_cards(qtbot):
    p = MonitorPage(); qtbot.addWidget(p)
    p.set_profile(_profile("NEXT-AI"))
    assert p.card_count() == 2


def test_render_updates_cards_and_status(qtbot):
    p = MonitorPage(); qtbot.addWidget(p)
    p.set_profile(_profile("NEW-AI"))
    p._on_frame(NEW_AI_FRAME)
    p._render()                        # 直接触发渲染（绕过节流 timer）
    assert p.card_at(0).title_text() == "端口 0 · 颜色"
    assert ("cm", "255") in p.card_at(2).rows()
    assert p.card_at(1).rows() == []   # 空端口占位
    assert p._status.field_text("版本") == "317"
    assert p._status.field_text("IMU") == "60.31/179.39/-0.34"


def test_on_frame_only_caches_latest(qtbot):
    p = MonitorPage(); qtbot.addWidget(p)
    p.set_profile(_profile("NEW-AI"))
    p._on_frame({"deviceList": [], "version": 1})
    p._on_frame({"deviceList": [], "version": 2})   # 覆盖
    assert p.latest_frame()["version"] == 2         # 只保留最新
    p._render()
    assert p._status.field_text("版本") == "2"


def test_unknown_product_shows_message_no_crash(qtbot):
    p = MonitorPage(); qtbot.addWidget(p)
    p.set_profile(_profile("MYSTERY"))
    assert p.card_count() == 0        # 无卡片，不崩溃
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/gui/test_monitor_page.py -v`
Expected: FAIL（`ModuleNotFoundError: monitor_page`）

- [ ] **Step 3: Write minimal implementation**

```python
# src/lbs_firmware_studio/gui/pages/monitor_page.py
"""数据监控页：顶部串口+启停(+传感器更新)，中部左/右两列 SensorCard，底部 HostStatusBar。
设备流式 JSON 经 MonitorWorker.frame_parsed 进来 -> 只缓存最新帧 -> QTimer(100ms) 节流渲染。"""
from __future__ import annotations
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QLabel, QPushButton, QMessageBox)
from PySide6.QtCore import QTimer
import qtawesome as qta
from .. import theme
from ..widgets.port_selector import PortSelector
from ..widgets.sensor_card import SensorCard
from ..widgets.host_status_bar import HostStatusBar
from ..monitor_worker import MonitorWorker
from .monitor_profiles import MONITOR_PROFILES

_RENDER_INTERVAL_MS = 100


class MonitorPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._profile = None
        self._cards: dict[int, SensorCard] = {}
        self._latest: dict | None = None
        self._port_getter = lambda: None
        self._monitoring = False

        self._worker = MonitorWorker()
        self._worker.frame_parsed.connect(self._on_frame)
        self._worker.error.connect(self._on_error)
        self._worker.state_changed.connect(self._on_worker_state)

        # 顶栏
        self._port = PortSelector()
        self._start_btn = QPushButton("▶ 开始监控"); self._start_btn.setObjectName("primary")
        self._start_btn.clicked.connect(self._toggle_monitor)
        self._update_btn = QPushButton("传感器更新")
        self._update_btn.setIcon(qta.icon("fa5s.sync", color=theme.TEXT_PRIMARY))
        self._update_btn.clicked.connect(self._open_sensor_update)
        self._update_btn.setEnabled(False)     # 需监控中才能下发
        top = QHBoxLayout()
        top.addWidget(QLabel("串口:")); top.addWidget(self._port, 1)
        top.addWidget(self._start_btn); top.addWidget(self._update_btn)

        # 卡片区（两列）
        self._grid = QGridLayout()
        self._grid.setHorizontalSpacing(12); self._grid.setVerticalSpacing(12)
        self._grid_host = QWidget(); self._grid_host.setLayout(self._grid)

        # 底部状态栏
        self._status = HostStatusBar()

        # 未知产品提示
        self._notice = QLabel(""); self._notice.setStyleSheet(
            f"color:{theme.TEXT_SECONDARY}; background:transparent;")

        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self._notice)
        lay.addWidget(self._grid_host, 1)
        lay.addWidget(self._status)

        # 节流渲染定时器
        self._timer = QTimer(self)
        self._timer.setInterval(_RENDER_INTERVAL_MS)
        self._timer.timeout.connect(self._render)

    # --- profile ---
    def set_profile(self, profile) -> None:
        self._profile = profile
        self._rebuild_cards()

    def _rebuild_cards(self) -> None:
        # 清空旧卡片
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._cards = {}

        prof = MONITOR_PROFILES.get(self._profile.name) if self._profile else None
        if prof is None:
            self._notice.setText(f"产品 {getattr(self._profile, 'name', '?')} 暂不支持数据监控")
            self._update_btn.setVisible(False)
            self._status.set_fields([])
            return

        self._notice.setText("")
        n = prof["ports"]
        half = (n + 1) // 2
        for port in range(n):
            card = SensorCard(port)
            self._cards[port] = card
            col = 0 if port < half else 1
            rowpos = port if port < half else port - half
            self._grid.addWidget(card, rowpos, col)
        self._status.set_fields(prof["status_fields"])
        self._update_btn.setVisible(prof["sensor_update"])

    def set_port_getter(self, fn) -> None:
        self._port_getter = fn

    # --- 启停 ---
    def _toggle_monitor(self) -> None:
        if self._monitoring:
            self.stop_monitor()
        else:
            self.start_monitor()

    def start_monitor(self) -> None:
        port = self._port.selected_port()
        if not port:
            QMessageBox.warning(self, "提示", "未选择串口"); return
        baud = getattr(self._profile, "baud", 115200)
        self._worker.start(port, baud)

    def stop_monitor(self) -> None:
        self._timer.stop()
        self._worker.stop()

    def _on_worker_state(self, state: str) -> None:
        self._monitoring = (state == "connected")
        self._start_btn.setText("■ 停止监控" if self._monitoring else "▶ 开始监控")
        # 传感器更新仅在 NEW-AI 且监控中可用
        prof = MONITOR_PROFILES.get(self._profile.name) if self._profile else None
        can_update = self._monitoring and bool(prof and prof["sensor_update"])
        self._update_btn.setEnabled(can_update)
        if self._monitoring:
            self._timer.start()
        else:
            self._timer.stop()

    def _on_error(self, msg: str) -> None:
        QMessageBox.critical(self, "错误", msg)

    # --- 帧渲染（节流）---
    def _on_frame(self, frame: dict) -> None:
        self._latest = frame

    def _render(self) -> None:
        frame = self._latest
        if not frame:
            return
        by_port = {}
        for item in frame.get("deviceList", []):
            if isinstance(item, dict) and "port" in item:
                by_port[item["port"]] = item
        for port, card in self._cards.items():
            item = by_port.get(port)
            sensor_key, fields = self._extract_sensor(item)
            card.update(sensor_key, fields)
        self._status.update_from(frame)

    @staticmethod
    def _extract_sensor(item: "dict | None"):
        """从 deviceList 项取 (传感器key, 字段dict)。无设备 -> (None, {})。"""
        if not item:
            return None, {}
        for k, v in item.items():
            if k == "port":
                continue
            return k, (v if isinstance(v, dict) else {})
        return None, {}

    # --- 传感器更新 ---
    def _open_sensor_update(self) -> None:
        from ..dialogs.sensor_update_dialog import SensorUpdateDialog
        dlg = SensorUpdateDialog(self)
        dlg.frame_ready.connect(self._worker.send_frame)
        dlg.exec()

    # --- 测试访问器 ---
    def card_count(self) -> int:
        return len(self._cards)

    def card_at(self, port: int) -> SensorCard:
        return self._cards[port]

    def has_sensor_update_button(self) -> bool:
        return self._update_btn.isVisible()

    def latest_frame(self) -> "dict | None":
        return self._latest
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/gui/test_monitor_page.py -v`
Expected: PASS（6 passed）
（注：`test_new_ai_has_8_cards_and_update_button` 断言 `has_sensor_update_button() is True` —— 未 show 的 widget `isVisible()` 可能为 False。若失败，将访问器改为 `return not self._update_btn.isHidden()`，它反映显式 setVisible 状态而不依赖父窗可见性。实现时按此调整。）

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/gui/pages/monitor_page.py tests/gui/test_monitor_page.py
git commit -m "feat(gui): MonitorPage cards + status bar + throttled render + start/stop"
```

---

## Task 8: SensorUpdateDialog（NEW-AI 传感器更新对话框）

**Files:**
- Create: `src/lbs_firmware_studio/gui/dialogs/__init__.py`（空文件）
- Create: `src/lbs_firmware_studio/gui/dialogs/sensor_update_dialog.py`
- Test: `tests/gui/test_sensor_update_dialog.py`

**Interfaces:**
- Consumes: `sensor_update.SENSOR_UPDATE_OPTIONS`、`build_sensor_update_frame`、`KEEP`；`theme`。
- Produces: `class SensorUpdateDialog(QDialog)`：
  - signal `frame_ready = Signal(object)`（payload: bytes 完整帧）。
  - 8 行，每行端口标签 + `QComboBox`（选项 = `SENSOR_UPDATE_OPTIONS`，默认「保持不动」）。
  - 「下发」按钮 → 组帧 → `frame_ready.emit(frame)` → 状态提示「已下发」。
  - 测试访问器：`selected_ids() -> list[int]`；`set_port_selection(port, id_value)`（供测试设置下拉）；`_submit()`。

- [ ] **Step 1: Write the failing tests**

```python
# tests/gui/test_sensor_update_dialog.py
from lbs_firmware_studio.gui.dialogs.sensor_update_dialog import SensorUpdateDialog
from lbs_firmware_studio.backend.sensor_update import (
    KEEP, DEV_ID_COLOR, DEV_ID_BIG_MOTOR, build_sensor_update_frame,
)


def test_default_all_keep(qtbot):
    d = SensorUpdateDialog(); qtbot.addWidget(d)
    assert d.selected_ids() == [KEEP] * 8


def test_set_selection_reflected(qtbot):
    d = SensorUpdateDialog(); qtbot.addWidget(d)
    d.set_port_selection(0, DEV_ID_COLOR)
    d.set_port_selection(2, DEV_ID_BIG_MOTOR)
    assert d.selected_ids() == [DEV_ID_COLOR, KEEP, DEV_ID_BIG_MOTOR,
                                KEEP, KEEP, KEEP, KEEP, KEEP]


def test_submit_emits_correct_frame(qtbot):
    d = SensorUpdateDialog(); qtbot.addWidget(d)
    d.set_port_selection(0, DEV_ID_COLOR)
    got = []
    d.frame_ready.connect(lambda f: got.append(bytes(f)))
    d._submit()
    ids = [DEV_ID_COLOR] + [KEEP] * 7
    assert got == [build_sensor_update_frame(ids)]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/gui/test_sensor_update_dialog.py -v`
Expected: FAIL（`ModuleNotFoundError: sensor_update_dialog`）

- [ ] **Step 3: Write minimal implementation**

```python
# src/lbs_firmware_studio/gui/dialogs/__init__.py
# (空文件，标记为包)
```

```python
# src/lbs_firmware_studio/gui/dialogs/sensor_update_dialog.py
"""NEW-AI 传感器更新对话框：8 端口各选目标设备类型 -> 组帧 -> frame_ready(bytes)。
即发即忘，不等 ACK；效果在后续监控帧体现。仅监控中可打开（页面侧控制）。"""
from __future__ import annotations
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QLabel, QComboBox, QPushButton)
from PySide6.QtCore import Signal
from ...backend.sensor_update import SENSOR_UPDATE_OPTIONS, build_sensor_update_frame


class SensorUpdateDialog(QDialog):
    frame_ready = Signal(object)   # payload: bytes 完整帧

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("传感器更新")
        self._combos: list[QComboBox] = []

        grid = QGridLayout()
        for port in range(8):
            grid.addWidget(QLabel(f"端口 {port}"), port, 0)
            combo = QComboBox()
            for name, id_value in SENSOR_UPDATE_OPTIONS:
                combo.addItem(name, id_value)
            grid.addWidget(combo, port, 1)
            self._combos.append(combo)

        self._status = QLabel("")
        self._submit_btn = QPushButton("下发"); self._submit_btn.setObjectName("primary")
        self._submit_btn.clicked.connect(self._submit)
        btn_row = QHBoxLayout(); btn_row.addWidget(self._status, 1); btn_row.addWidget(self._submit_btn)

        lay = QVBoxLayout(self)
        lay.addLayout(grid)
        lay.addLayout(btn_row)

    def selected_ids(self) -> list[int]:
        return [c.currentData() for c in self._combos]

    def set_port_selection(self, port: int, id_value: int) -> None:
        combo = self._combos[port]
        idx = combo.findData(id_value)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _submit(self) -> None:
        frame = build_sensor_update_frame(self.selected_ids())
        self.frame_ready.emit(frame)
        self._status.setText("已下发")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/gui/test_sensor_update_dialog.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/gui/dialogs/ tests/gui/test_sensor_update_dialog.py
git commit -m "feat(gui): SensorUpdateDialog 8-port sensor type selection + emit frame"
```

---

## Task 9: 接入 MainWindow（启用 nav + 建页 + 导航离开时停监控）

**Files:**
- Modify: `src/lbs_firmware_studio/gui/main_window.py`
- Test: `tests/gui/test_main_window.py`（新增用例）

**Interfaces:**
- Consumes: `MonitorPage`（Task 7）。
- Produces: MainWindow 中 `self._monitor` 页；nav `monitor` 项启用；`_on_nav` 在离开监控页时调用 `self._monitor.stop_monitor()` 释放串口。

- [ ] **Step 1: Write the failing tests**（追加到 `tests/gui/test_main_window.py`）

```python
def test_monitor_nav_enabled(qtbot, tmp_path):
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    assert "数据监控" in w.nav_labels()
    assert w.is_nav_enabled("数据监控") is True


def test_navigate_to_monitor_page(qtbot, tmp_path):
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w.navigate("数据监控")
    assert w.current_page_name() == "数据监控"


def test_leaving_monitor_stops_it(qtbot, tmp_path):
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w.navigate("数据监控")
    stopped = []
    w._monitor.stop_monitor = lambda: stopped.append(True)  # 打桩
    w.navigate("固件更新")     # 离开监控页
    assert stopped == [True]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/gui/test_main_window.py -v`
Expected: FAIL（`is_nav_enabled("数据监控")` 为 False；`_monitor` 不存在）

- [ ] **Step 3: Modify main_window.py**

3a. 启用 monitor nav —— 修改 `_NAV` 中 monitor 项的 enabled 为 True：

```python
_NAV = [
    ("firmware", "固件更新", "fa5s.download", True),
    ("editor", "代码编辑", "fa5s.code", True),
    ("monitor", "数据监控", "fa5s.chart-line", True),
    ("settings", "设置", "fa5s.cog", True),
]
```

3b. 顶部导入 `MonitorPage`：

```python
from .pages.monitor_page import MonitorPage
```

3c. `_make_page` 中接入 monitor 分支（放在 settings 分支之前）：

```python
    def _make_page(self, key):
        if key == "firmware":
            self._firmware = FirmwarePage(); return self._firmware
        if key == "editor":
            self._editor_page = ScriptEditorPage(); return self._editor_page
        if key == "monitor":
            self._monitor = MonitorPage()
            self._monitor.set_profile(self._profile)
            self._monitor.set_port_getter(self._port.selected_port)
            return self._monitor
        if key == "settings":
            return SettingsPage(self._raw, self._path)
        return PlaceholderPage(_KEY2LABEL[key])
```

3d. `_on_nav` 中，离开监控页时停监控（释放串口，避免占用同一端口影响部署）：

```python
    def _on_nav(self, key: str):
        # 离开监控页时停监控，释放串口
        if key != "monitor" and self._pages.get("monitor") is self._stack.currentWidget():
            self._monitor.stop_monitor()
        self._stack.setCurrentWidget(self._pages[key])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/gui/test_main_window.py -v`
Expected: PASS（含 3 个新用例）

- [ ] **Step 5: Run full suite + commit**

Run: `python -m pytest tests/test_monitor_parser.py tests/test_sensor_update.py -v` 然后逐个跑 GUI 测试文件：
`python -m pytest tests/gui/test_monitor_profiles.py tests/gui/test_sensor_card.py tests/gui/test_host_status_bar.py tests/gui/test_monitor_worker.py tests/gui/test_monitor_page.py tests/gui/test_sensor_update_dialog.py tests/gui/test_main_window.py -v`
Expected: 全部 PASS（GUI 测试容忍 teardown 段错误，以断言结果为准）

```bash
git add src/lbs_firmware_studio/gui/main_window.py tests/gui/test_main_window.py
git commit -m "feat(gui): wire MonitorPage into MainWindow + stop monitor on nav away"
```

---

## Self-Review

**1. Spec coverage:**
- 流式 JSON 按行解析 → Task 1 ✓
- 三产品字段差异（端口数/状态字段/运行状态 key/电池路径）→ Task 3 表驱动 ✓
- 8/4/2 卡片 + 左右两列布局 → Task 7 `_rebuild_cards` 两列 ✓
- 底部主机状态栏（含 IMU 组合、点路径、`--` 兜底）→ Task 5 ✓
- 通用键值卡片 + 空端口占位 → Task 4 + Task 7 `_extract_sensor` ✓
- 节流刷新（最新帧缓存 + QTimer 100ms）→ Task 7 ✓
- 独立串口连接（start 才 open，stop 才 close，离开页面停）→ Task 6 + Task 9 ✓
- NEW-AI 传感器更新（8 端口下拉、组帧 0x32、checksum、即发即忘、需监控中）→ Task 2 + Task 8 + Task 7 `_update_btn` 使能逻辑 ✓
- 错误处理（坏行丢弃、半行缓冲、缓冲上限、打开失败、未知产品）→ Task 1 + Task 6 + Task 7 ✓
- nav 已有 monitor 项启用 → Task 9 ✓

**2. Placeholder scan:** 无 TBD/TODO；每个 code step 均含完整可运行代码。

**3. Type consistency:**
- `MonitorParser.feed(bytes) -> list[dict]`：Task 1 定义，Task 6 调用 ✓
- `build_sensor_update_frame(list[int]) -> bytes`：Task 2 定义，Task 8 调用 ✓
- `get_by_path/sensor_display_name`：Task 3 定义，Task 4/5 调用 ✓
- `SensorCard.update(key|None, dict)`：Task 4 定义，Task 7 调用 ✓
- `HostStatusBar.set_fields/update_from/field_text`：Task 5 定义，Task 7 调用 ✓
- `MonitorWorker.frame_parsed(object)/send_frame/start/stop`：Task 6 定义，Task 7 连接 ✓
- `SensorUpdateDialog.frame_ready(object)`：Task 8 定义，Task 7 `_open_sensor_update` 连到 `worker.send_frame` ✓
- `MonitorPage.set_profile/set_port_getter/stop_monitor`：Task 7 定义，Task 9 调用 ✓

无遗漏、无签名冲突。
