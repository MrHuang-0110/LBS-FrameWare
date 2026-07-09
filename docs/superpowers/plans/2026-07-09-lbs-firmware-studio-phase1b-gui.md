# LBS Firmware Studio · Phase 1b GUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 PySide6 构建 App Store 风格桌面 GUI，落地固件更新功能 + 完整界面骨架，调用已验证的 Phase 1a 后端。

**Architecture:** GUI 分层于 `src/lbs_firmware_studio/gui/`：入口 app.py → 启动产品选择 → 主窗口(顶栏+左导航+右 QStackedWidget)。设备操作经 DeployWorker 在 QThread 里跑 DeviceDeployer，四个 Qt 信号回主线程更新 UI。GUI 层不碰协议。

**Tech Stack:** Python 3.13、PySide6 6.11.1、pyserial、PyYAML、pytest + pytest-qt 4.5.0。

## Global Constraints

- Python 3.13；Windows；解释器用 `python`（非 python3）。
- GUI 层只做界面，所有设备操作经 `DeployWorker` 调 `DeviceDeployer`，不直接碰协议/串口写。
- 后端信号签名固定：`progress(int, int)`、`log(str)`、`state_changed(str)`、`error(str)`。
- 状态灯映射：`idle`=灰；`compiling`/`connecting`/`entering_upgrade`/`reconnecting`/`transfering`=琥珀；`done`=绿；`error`=红。
- 串口自动识别：`description` 含 "LBS Serial" 或 VID:PID=`0483:5740` 的端口置顶并默认选中。
- 配色：背景 `#F5F5F7`、面板 `#FFFFFF`、强调色 Apple 蓝 `#0071E3`、成功绿 `#34C759`、琥珀 `#FF9F0A`、错误红 `#FF3B30`、次级文字 `#86868B`。
- 本阶段只做固件更新可用；脚本下发/代码编辑/数据监控置灰"即将推出"；设置可用。
- GUI 测试用 pytest-qt + 手动 emit 信号驱动，**不碰真串口**；worker 线程测试用 Phase 1a 的 `tests/simulator.py` DeviceSimulator + `tests/fakes.py` make_fake_serial_pair。
- 协议层 log_cb 默认 None，保持协议纯净可独立单测。
- YAGNI：不加 max_slot（脚本下发才需要）。

---

## File Structure

```
src/lbs_firmware_studio/
  backend/
    deployer.py        # 修改：_make_protocol 传 log_cb=self.log.emit
    transfer_protocol.py # 修改：两协议加可选 log_cb，发每文件前回调文件名
    profile.py         # 修改：加 save_profiles(raw, path)；load 读 display_ports
  gui/
    __init__.py
    theme.py           # 配色常量 + QSS 字符串 + state->颜色映射
    worker.py          # DeployWorker(QObject): DeviceDeployer 放 QThread
    app.py             # main(): QApplication + 启动窗
    startup_window.py  # 产品选择界面
    main_window.py     # 主窗口: 顶栏 + 左导航 + QStackedWidget
    widgets/
      __init__.py
      port_selector.py # 串口下拉+刷新+自动识别
      status_badge.py  # 状态灯
      log_view.py      # 日志区
    pages/
      __init__.py
      placeholder_page.py # "即将推出"占位
      firmware_page.py    # 固件更新页
      settings_page.py    # 设置页
products.yaml          # 修改：加 display_ports 字段
pyproject.toml         # 修改：加 pytest-qt 到 dev 依赖 + gui 入口
tests/
  test_backend_log_cb.py    # 协议 log_cb 测试
  test_profile_save.py      # save_profiles 测试
  test_worker.py            # DeployWorker vs 模拟器
  gui/
    __init__.py
    conftest.py             # qtbot/qapp fixture 保障
    test_theme.py
    test_port_selector.py
    test_status_badge.py
    test_log_view.py
    test_placeholder_page.py
    test_firmware_page.py
    test_settings_page.py
    test_startup_window.py
    test_main_window.py
```

## 接口契约（各任务共同遵守）

```python
# backend/transfer_protocol.py（修改）
class CustomFrameProtocol:
    def __init__(self, ..., log_cb: Callable[[str], None] | None = None): ...
    # _send_file_with_cmd 发送每个文件前: if self.log_cb: self.log_cb(f"发送 {path.name}")
class YmodemProtocol:
    def __init__(self, ..., log_cb: Callable[[str], None] | None = None): ...
    # send_file 开头: if self.log_cb: self.log_cb(f"发送 {path.name}")

# backend/profile.py（新增）
def save_profiles(raw: dict, path: Path) -> None   # yaml.safe_dump 写回
# DeviceProfile 新增字段: display_ports: int = 0

# gui/theme.py
BG="#F5F5F7"; PANEL="#FFFFFF"; ACCENT="#0071E3"; SUCCESS="#34C759"
AMBER="#FF9F0A"; ERROR="#FF3B30"; MUTED="#86868B"
def state_color(state: str) -> str          # state -> 颜色
def app_qss() -> str                        # 全局 QSS 字符串

# gui/worker.py
class DeployWorker(QObject):
    finished = Signal()
    def __init__(self, transport, deployer): ...   # 复用后端信号
    def run_firmware(self, profile, port) -> None   # 槽: open→start_rx→update_firmware→close→finished

# gui/widgets/port_selector.py
class PortSelector(QWidget):
    def __init__(self, lister: Callable[[], list] | None = None): ...  # lister 默认 comports
    def refresh(self) -> None
    def selected_port(self) -> str | None          # 返回 COM 号
    # 内部: description 含 "LBS Serial" 或 vid:pid==(0x0483,0x5740) 置顶默认选中

# gui/widgets/status_badge.py
class StatusBadge(QWidget):
    def set_state(self, state: str) -> None         # 用 theme.state_color 上色
    def text(self) -> str                           # 当前状态文字(测试用)

# gui/widgets/log_view.py
class LogView(QWidget):
    def append(self, message: str, level: str = "info") -> None  # level: info/success/progress/error
    def plain_text(self) -> str                     # 测试用

# gui/pages/firmware_page.py
class FirmwarePage(QWidget):
    start_requested = Signal()                      # 点"开始"发出(端口由 MainWindow 提供)
    def set_profile(self, profile) -> None
    def set_busy(self, busy: bool) -> None          # 操作中锁控件
    def on_progress(self, done: int, total: int) -> None
    def on_state(self, state: str) -> None
    def on_log(self, msg: str) -> None

# gui/pages/settings_page.py
class SettingsPage(QWidget):
    def __init__(self, raw_config: dict, config_path: Path): ...
    # "保存"按钮 -> save_profiles

# gui/pages/placeholder_page.py
class PlaceholderPage(QWidget):
    def __init__(self, title: str): ...             # 显示 "<title> · 即将推出"

# gui/startup_window.py
class StartupWindow(QWidget):
    product_selected = Signal(str)                  # 发出产品名
    def __init__(self, profiles: dict): ...

# gui/main_window.py
class MainWindow(QWidget):
    switch_product_requested = Signal()
    def __init__(self, profile, raw_config, config_path): ...
```

---

### Task 1: 后端协议层 log_cb（TDD）

**Files:**
- Modify: `src/lbs_firmware_studio/backend/transfer_protocol.py`
- Modify: `src/lbs_firmware_studio/backend/deployer.py:41-48`
- Test: `tests/test_backend_log_cb.py`

**Interfaces:**
- Produces: `CustomFrameProtocol(log_cb=...)`, `YmodemProtocol(log_cb=...)`；deployer 传 `log_cb=self.log.emit`

- [ ] **Step 1: 写失败测试**

`tests/test_backend_log_cb.py`:
```python
import pathlib, tempfile
from lbs_firmware_studio.backend.serial_transport import SerialTransport
from lbs_firmware_studio.backend.transfer_protocol import CustomFrameProtocol, YmodemProtocol
from tests.fakes import make_fake_serial_pair
from tests.simulator import DeviceSimulator


def test_custom_frame_log_cb_reports_filename():
    host_ser, dev_ser = make_fake_serial_pair()
    sim = DeviceSimulator(dev_ser, protocol="custom_frame"); sim.start()
    t = SerialTransport(host_ser); t.start_rx()
    logs = []
    try:
        proto = CustomFrameProtocol(chunk_size=248, ack_timeout=2.0,
                                    last_frame_ack="wait_2s", log_cb=logs.append)
        with tempfile.NamedTemporaryFile(suffix=".o", delete=False) as f:
            f.write(b"hello"); path = pathlib.Path(f.name)
        proto.send_file(t, path, lambda d, n: None, firmware=False)
        assert any(path.name in m for m in logs)
    finally:
        t.stop_rx(); sim.stop()


def test_log_cb_defaults_none_no_crash():
    # log_cb 默认 None 时不报错（协议保持纯净）
    proto = CustomFrameProtocol()
    assert proto.log_cb is None
    proto2 = YmodemProtocol()
    assert proto2.log_cb is None
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_backend_log_cb.py -v`
Expected: FAIL（`TypeError: unexpected keyword argument 'log_cb'` 或 `AttributeError: log_cb`）

- [ ] **Step 3: 改 CustomFrameProtocol**

在 `transfer_protocol.py` 的 `CustomFrameProtocol.__init__` 增加参数并保存：
```python
    def __init__(self, chunk_size: int = 248, ack_timeout: float = 2.0,
                 last_frame_ack: str = "wait_2s", max_retries: int = 3,
                 filename_encoding: str = "gbk",
                 log_cb: "Callable[[str], None] | None" = None):
        self.chunk_size = min(chunk_size, pf.MAX_DATA_LEN)
        self.ack_timeout = ack_timeout
        self.last_frame_ack = last_frame_ack
        self.max_retries = max_retries
        self.filename_encoding = filename_encoding
        self.log_cb = log_cb
```
在 `_send_file_with_cmd` 开头（读文件后、发文件名帧前）加：
```python
    def _send_file_with_cmd(self, t, path, cmd, on_progress):
        name = path.name.encode(self.filename_encoding)
        data = path.read_bytes()
        if self.log_cb:
            self.log_cb(f"发送 {path.name}")
        self._send_and_wait(t, pf.build_frame(cmd, name))
        ...（其余不变）
```
确认文件顶部已 `from typing import Callable`（若无则加）。

- [ ] **Step 4: 改 YmodemProtocol**

`YmodemProtocol.__init__` 增加 `log_cb` 参数并保存 `self.log_cb = log_cb`；在 `send_file` 开头加：
```python
    def send_file(self, t, path, on_progress, *, firmware):
        data = path.read_bytes()
        if self.log_cb:
            self.log_cb(f"发送 {path.name}")
        name = path.name.encode("ascii", errors="replace")
        ...（其余不变）
```

- [ ] **Step 5: 改 deployer._make_protocol 传 log_cb**

`deployer.py` `_make_protocol`:
```python
    def _make_protocol(self, profile: DeviceProfile):
        if profile.protocol == "custom_frame":
            return CustomFrameProtocol(chunk_size=profile.chunk_size, ack_timeout=profile.ack_timeout,
                                       last_frame_ack=profile.last_frame_ack,
                                       filename_encoding=profile.filename_encoding,
                                       log_cb=self.log.emit)
        return YmodemProtocol(block_size=profile.chunk_size, ack_timeout=12.0,
                              log_cb=self.log.emit)
```

- [ ] **Step 6: 运行确认通过 + 全量回归**

Run: `python -m pytest tests/test_backend_log_cb.py -v && python -m pytest -q`
Expected: 新测试 2 passed；全量 42 passed（40 原有 + 2 新）

- [ ] **Step 7: Commit**

```bash
git add src/lbs_firmware_studio/backend/transfer_protocol.py src/lbs_firmware_studio/backend/deployer.py tests/test_backend_log_cb.py
git commit -m "feat: protocol log_cb reports current filename during transfer"
```

---

### Task 2: profile.save_profiles + display_ports（TDD）

**Files:**
- Modify: `src/lbs_firmware_studio/backend/profile.py`
- Modify: `products.yaml`
- Test: `tests/test_profile_save.py`

**Interfaces:**
- Produces: `save_profiles(raw: dict, path: Path)`；`DeviceProfile.display_ports: int`

- [ ] **Step 1: 写失败测试**

`tests/test_profile_save.py`:
```python
import textwrap
from pathlib import Path
from lbs_firmware_studio.backend.profile import load_profiles, save_profiles


def test_display_ports_loaded(tmp_path):
    p = tmp_path / "products.yaml"
    p.write_text(textwrap.dedent("""
        compiler_path: ./tools/rust-msc-latest-win10.exe
        products:
          NEW-AI:
            protocol: custom_frame
            display_ports: 8
    """))
    profiles = load_profiles(p)
    assert profiles["NEW-AI"].display_ports == 8


def test_save_profiles_roundtrip(tmp_path):
    p = tmp_path / "products.yaml"
    raw = {
        "compiler_path": "./tools/x.exe",
        "products": {"NEW-AI": {"protocol": "custom_frame", "display_ports": 8}},
    }
    save_profiles(raw, p)
    # 读回应保留关键字段
    import yaml
    back = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert back["compiler_path"] == "./tools/x.exe"
    assert back["products"]["NEW-AI"]["protocol"] == "custom_frame"
    # load_profiles 也能正常解析
    profiles = load_profiles(p)
    assert profiles["NEW-AI"].protocol == "custom_frame"
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_profile_save.py -v`
Expected: FAIL（`ImportError: cannot import save_profiles` / `AttributeError display_ports`）

- [ ] **Step 3: 加 display_ports 字段**

`profile.py` `DeviceProfile` 增加字段（放 disappear_timeout 后）：
```python
    disappear_timeout: float = 5.0
    display_ports: int = 0    # 启动卡片展示的端口数(纯展示，不影响协议)
```
`load_profiles` 构造处增加：
```python
            disappear_timeout=cfg.get("disappear_timeout", 5.0),
            display_ports=cfg.get("display_ports", 0),
```

- [ ] **Step 4: 加 save_profiles 函数**

`profile.py` 末尾：
```python
def save_profiles(raw: dict, path: Path) -> None:
    """把配置字典写回 YAML。注意 safe_dump 会丢失注释（本阶段接受）。"""
    path.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
```

- [ ] **Step 5: products.yaml 加 display_ports**

给三个产品各加一行（NEW-AI=8, SPARK-AI=4, NEXT-AI=2），放在各自 `protocol:` 下方：
```yaml
  NEW-AI:
    protocol: custom_frame
    display_ports: 8
    ...
  SPARK-AI:
    protocol: custom_frame
    display_ports: 4
    ...
  NEXT-AI:
    protocol: ymodem
    display_ports: 2
    ...
```

- [ ] **Step 6: 运行确认通过 + 回归**

Run: `python -m pytest tests/test_profile_save.py -v && python -m pytest -q`
Expected: 新测试 2 passed；全量 44 passed。另跑 `python -m lbs_firmware_studio.cli --list` 确认三产品仍正常。

- [ ] **Step 7: Commit**

```bash
git add src/lbs_firmware_studio/backend/profile.py products.yaml tests/test_profile_save.py
git commit -m "feat: save_profiles + display_ports config field"
```

---

### Task 3: theme.py（TDD）

**Files:**
- Create: `src/lbs_firmware_studio/gui/__init__.py`（空）
- Create: `src/lbs_firmware_studio/gui/theme.py`
- Create: `tests/gui/__init__.py`（空）, `tests/gui/conftest.py`, `tests/gui/test_theme.py`

**Interfaces:**
- Produces: 配色常量、`state_color(state)`、`app_qss()`

- [ ] **Step 1: 写 conftest 保障 QApplication**

`tests/gui/conftest.py`:
```python
# pytest-qt 提供 qtbot/qapp fixture；此文件占位，确保 tests/gui 被识别为包内测试
import pytest
```
`tests/gui/__init__.py`: 空文件。

- [ ] **Step 2: 写失败测试**

`tests/gui/test_theme.py`:
```python
from lbs_firmware_studio.gui import theme


def test_colors_defined():
    assert theme.ACCENT == "#0071E3"
    assert theme.BG == "#F5F5F7"
    assert theme.SUCCESS == "#34C759"
    assert theme.ERROR == "#FF3B30"


def test_state_color_mapping():
    assert theme.state_color("idle") == theme.MUTED
    assert theme.state_color("transfering") == theme.AMBER
    assert theme.state_color("reconnecting") == theme.AMBER
    assert theme.state_color("done") == theme.SUCCESS
    assert theme.state_color("error") == theme.ERROR
    assert theme.state_color("unknown_state") == theme.MUTED  # 未知态回退灰


def test_app_qss_is_str():
    qss = theme.app_qss()
    assert isinstance(qss, str) and len(qss) > 0
    assert theme.ACCENT in qss  # 强调色进了 QSS
```

- [ ] **Step 3: 运行确认失败**

Run: `python -m pytest tests/gui/test_theme.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 4: 实现 theme.py**

`gui/__init__.py`: 空。
`gui/theme.py`:
```python
"""App Store 风格配色 + 全局 QSS。集中管理，便于统一调整。"""
from __future__ import annotations

BG = "#F5F5F7"
PANEL = "#FFFFFF"
ACCENT = "#0071E3"
SUCCESS = "#34C759"
AMBER = "#FF9F0A"
ERROR = "#FF3B30"
MUTED = "#86868B"
TEXT = "#1D1D1F"

_STATE_COLORS = {
    "idle": MUTED,
    "compiling": AMBER, "connecting": AMBER, "entering_upgrade": AMBER,
    "reconnecting": AMBER, "transfering": AMBER,
    "done": SUCCESS,
    "error": ERROR,
}


def state_color(state: str) -> str:
    return _STATE_COLORS.get(state, MUTED)


def app_qss() -> str:
    return f"""
    QWidget {{ background: {BG}; color: {TEXT};
        font-family: 'Segoe UI Variable', 'Segoe UI', 'Inter', sans-serif; font-size: 14px; }}
    QFrame#card, QFrame#panel {{ background: {PANEL}; border-radius: 12px; }}
    QPushButton#primary {{ background: {ACCENT}; color: white; border: none;
        border-radius: 8px; padding: 10px 20px; font-weight: 600; }}
    QPushButton#primary:disabled {{ background: {MUTED}; }}
    QPushButton {{ background: {PANEL}; border: 1px solid #D2D2D7; border-radius: 8px;
        padding: 6px 14px; }}
    QComboBox {{ background: {PANEL}; border: 1px solid #D2D2D7; border-radius: 8px; padding: 6px; }}
    QTextEdit, QPlainTextEdit {{ background: {PANEL}; border: 1px solid #D2D2D7;
        border-radius: 8px; font-family: 'Cascadia Code', 'JetBrains Mono', monospace; }}
    QProgressBar {{ border: none; border-radius: 6px; background: #E5E5EA; height: 12px; text-align: center; }}
    QProgressBar::chunk {{ background: {ACCENT}; border-radius: 6px; }}
    """
```

- [ ] **Step 5: 运行确认通过**

Run: `python -m pytest tests/gui/test_theme.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add src/lbs_firmware_studio/gui/__init__.py src/lbs_firmware_studio/gui/theme.py tests/gui/
git commit -m "feat: gui theme (App Store colors + QSS + state mapping)"
```

---

### Task 4: StatusBadge 控件（TDD）

**Files:**
- Create: `src/lbs_firmware_studio/gui/widgets/__init__.py`（空）
- Create: `src/lbs_firmware_studio/gui/widgets/status_badge.py`
- Test: `tests/gui/test_status_badge.py`

**Interfaces:**
- Consumes: `theme.state_color`
- Produces: `StatusBadge.set_state(state)`, `.text()`

- [ ] **Step 1: 写失败测试**

`tests/gui/test_status_badge.py`:
```python
from lbs_firmware_studio.gui.widgets.status_badge import StatusBadge
from lbs_firmware_studio.gui import theme


def test_badge_default_idle(qtbot):
    w = StatusBadge(); qtbot.addWidget(w)
    assert "空闲" in w.text()


def test_badge_set_state_updates_text_and_color(qtbot):
    w = StatusBadge(); qtbot.addWidget(w)
    w.set_state("transfering")
    assert "传输" in w.text() or "操作" in w.text()
    assert w.current_color() == theme.AMBER
    w.set_state("done")
    assert w.current_color() == theme.SUCCESS
    w.set_state("error")
    assert w.current_color() == theme.ERROR
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/gui/test_status_badge.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 status_badge.py**

`gui/widgets/__init__.py`: 空。
`gui/widgets/status_badge.py`:
```python
"""左上角状态灯：圆点 + 文字，颜色随 state 变化。"""
from __future__ import annotations
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt
from .. import theme

_STATE_TEXT = {
    "idle": "空闲", "compiling": "编译中", "connecting": "连接中",
    "entering_upgrade": "进入升级", "reconnecting": "重连中",
    "transfering": "传输中", "done": "完成", "error": "错误",
}


class StatusBadge(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = theme.MUTED
        self._dot = QLabel("●")
        self._label = QLabel(_STATE_TEXT["idle"])
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(6)
        lay.addWidget(self._dot); lay.addWidget(self._label)
        self._apply()

    def set_state(self, state: str) -> None:
        self._color = theme.state_color(state)
        self._label.setText(_STATE_TEXT.get(state, state))
        self._apply()

    def _apply(self) -> None:
        self._dot.setStyleSheet(f"color: {self._color}; font-size: 14px;")

    def current_color(self) -> str:
        return self._color

    def text(self) -> str:
        return self._label.text()
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/gui/test_status_badge.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/gui/widgets/ tests/gui/test_status_badge.py
git commit -m "feat: StatusBadge widget"
```

---

### Task 5: PortSelector 控件（TDD）

**Files:**
- Create: `src/lbs_firmware_studio/gui/widgets/port_selector.py`
- Test: `tests/gui/test_port_selector.py`

**Interfaces:**
- Produces: `PortSelector(lister=None)`, `.refresh()`, `.selected_port()`

- [ ] **Step 1: 写失败测试**

`tests/gui/test_port_selector.py`:
```python
from lbs_firmware_studio.gui.widgets.port_selector import PortSelector


class _FakePort:
    def __init__(self, device, description, vid=None, pid=None):
        self.device = device; self.description = description
        self.vid = vid; self.pid = pid


def test_lbs_device_auto_selected(qtbot):
    ports = [
        _FakePort("COM3", "USB-SERIAL CH340"),
        _FakePort("COM9", "LBS Serial (COM9)", vid=0x0483, pid=0x5740),
        _FakePort("COM5", "Standard Serial"),
    ]
    w = PortSelector(lister=lambda: ports); qtbot.addWidget(w)
    assert w.selected_port() == "COM9"


def test_no_lbs_device_none_selected(qtbot):
    ports = [_FakePort("COM3", "USB-SERIAL CH340")]
    w = PortSelector(lister=lambda: ports); qtbot.addWidget(w)
    # 无 LBS 设备：仍列出端口，但不强制选中 LBS（selected_port 返回第一个或 None 由实现定）
    assert w.selected_port() in ("COM3", None)


def test_refresh_updates_list(qtbot):
    state = {"ports": [_FakePort("COM3", "CH340")]}
    w = PortSelector(lister=lambda: state["ports"]); qtbot.addWidget(w)
    state["ports"] = [_FakePort("COM9", "LBS Serial (COM9)", vid=0x0483, pid=0x5740)]
    w.refresh()
    assert w.selected_port() == "COM9"


def test_empty_ports(qtbot):
    w = PortSelector(lister=lambda: []); qtbot.addWidget(w)
    assert w.selected_port() is None
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/gui/test_port_selector.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 port_selector.py**

```python
"""串口选择：下拉 + 刷新，自动识别 LBS Serial 设备置顶默认选中。"""
from __future__ import annotations
from typing import Callable
from PySide6.QtWidgets import QWidget, QHBoxLayout, QComboBox, QPushButton

_LBS_VID_PID = (0x0483, 0x5740)


def _default_lister():
    import serial.tools.list_ports
    return list(serial.tools.list_ports.comports())


def _is_lbs(p) -> bool:
    desc = (getattr(p, "description", "") or "")
    if "LBS Serial" in desc:
        return True
    vid = getattr(p, "vid", None); pid = getattr(p, "pid", None)
    return (vid, pid) == _LBS_VID_PID


class PortSelector(QWidget):
    def __init__(self, lister: "Callable[[], list] | None" = None, parent=None):
        super().__init__(parent)
        self._lister = lister or _default_lister
        self._combo = QComboBox()
        self._refresh_btn = QPushButton("刷新")
        self._refresh_btn.clicked.connect(self.refresh)
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._combo, 1); lay.addWidget(self._refresh_btn)
        self.refresh()

    def refresh(self) -> None:
        ports = list(self._lister())
        # LBS 设备排前
        ports.sort(key=lambda p: 0 if _is_lbs(p) else 1)
        self._combo.clear()
        lbs_index = -1
        for i, p in enumerate(ports):
            label = getattr(p, "description", None) or p.device
            self._combo.addItem(label, p.device)
            if lbs_index < 0 and _is_lbs(p):
                lbs_index = i
        if lbs_index >= 0:
            self._combo.setCurrentIndex(lbs_index)

    def selected_port(self) -> "str | None":
        if self._combo.count() == 0:
            return None
        return self._combo.currentData()
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/gui/test_port_selector.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/gui/widgets/port_selector.py tests/gui/test_port_selector.py
git commit -m "feat: PortSelector with LBS auto-detect"
```

---

### Task 6: LogView 控件（TDD）

**Files:**
- Create: `src/lbs_firmware_studio/gui/widgets/log_view.py`
- Test: `tests/gui/test_log_view.py`

**Interfaces:**
- Produces: `LogView.append(msg, level)`, `.plain_text()`

- [ ] **Step 1: 写失败测试**

`tests/gui/test_log_view.py`:
```python
from lbs_firmware_studio.gui.widgets.log_view import LogView


def test_append_shows_message(qtbot):
    w = LogView(); qtbot.addWidget(w)
    w.append("打开 COM9", level="success")
    assert "打开 COM9" in w.plain_text()


def test_append_multiple_lines(qtbot):
    w = LogView(); qtbot.addWidget(w)
    w.append("a"); w.append("b"); w.append("c")
    txt = w.plain_text()
    assert "a" in txt and "b" in txt and "c" in txt


def test_append_has_timestamp(qtbot):
    w = LogView(); qtbot.addWidget(w)
    w.append("hello")
    # 时间戳形如 HH:MM:SS，检查有冒号分隔的时间
    import re
    assert re.search(r"\d{2}:\d{2}:\d{2}", w.plain_text())
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/gui/test_log_view.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 log_view.py**

```python
"""日志区：只读文本，时间戳 + 级别着色。"""
from __future__ import annotations
import time
from PySide6.QtWidgets import QPlainTextEdit
from .. import theme

_LEVEL_COLOR = {
    "info": theme.TEXT, "success": theme.SUCCESS,
    "progress": theme.ACCENT, "error": theme.ERROR,
}


class LogView(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)

    def append(self, message: str, level: str = "info") -> None:
        ts = time.strftime("%H:%M:%S")
        color = _LEVEL_COLOR.get(level, theme.TEXT)
        self.appendHtml(f'<span style="color:{theme.MUTED}">{ts}</span> '
                        f'<span style="color:{color}">{message}</span>')

    def plain_text(self) -> str:
        return self.toPlainText()
```

> 注：`time.strftime` 在 GUI 运行时可用（不同于 workflow 脚本限制）。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/gui/test_log_view.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/gui/widgets/log_view.py tests/gui/test_log_view.py
git commit -m "feat: LogView widget with timestamp + level colors"
```

---

### Task 7: PlaceholderPage（TDD）

**Files:**
- Create: `src/lbs_firmware_studio/gui/pages/__init__.py`（空）
- Create: `src/lbs_firmware_studio/gui/pages/placeholder_page.py`
- Test: `tests/gui/test_placeholder_page.py`

**Interfaces:**
- Produces: `PlaceholderPage(title)`

- [ ] **Step 1: 写失败测试**

`tests/gui/test_placeholder_page.py`:
```python
from lbs_firmware_studio.gui.pages.placeholder_page import PlaceholderPage


def test_placeholder_shows_title_and_coming_soon(qtbot):
    w = PlaceholderPage("数据监控"); qtbot.addWidget(w)
    assert "数据监控" in w.displayed_text()
    assert "即将推出" in w.displayed_text()
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/gui/test_placeholder_page.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 placeholder_page.py**

`gui/pages/__init__.py`: 空。
`gui/pages/placeholder_page.py`:
```python
"""占位页：脚本下发/代码编辑/数据监控共用，显示 <title> · 即将推出。"""
from __future__ import annotations
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from .. import theme


class PlaceholderPage(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._text = f"{title} · 即将推出"
        lay = QVBoxLayout(self)
        lbl = QLabel(self._text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"color: {theme.MUTED}; font-size: 18px;")
        lay.addStretch(); lay.addWidget(lbl); lay.addStretch()

    def displayed_text(self) -> str:
        return self._text
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/gui/test_placeholder_page.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/gui/pages/ tests/gui/test_placeholder_page.py
git commit -m "feat: PlaceholderPage for coming-soon features"
```

---

### Task 8: FirmwarePage（TDD）

**Files:**
- Create: `src/lbs_firmware_studio/gui/pages/firmware_page.py`
- Test: `tests/gui/test_firmware_page.py`

**Interfaces:**
- Consumes: `LogView`, `theme`
- Produces: `FirmwarePage`：`start_requested` 信号、`set_profile`、`set_busy`、`on_progress`、`on_state`、`on_log`

- [ ] **Step 1: 写失败测试**

`tests/gui/test_firmware_page.py`:
```python
from lbs_firmware_studio.gui.pages.firmware_page import FirmwarePage
from lbs_firmware_studio.backend.profile import DeviceProfile
from pathlib import Path


def _profile():
    return DeviceProfile(name="NEW-AI", protocol="custom_frame",
                         folders=["app", "music", "boot", "config", "version"],
                         firmware_dir=Path("./products/NEW-AI/fwlib"))


def test_set_profile_shows_folders_and_dir(qtbot):
    w = FirmwarePage(); qtbot.addWidget(w)
    w.set_profile(_profile())
    txt = w.summary_text()
    assert "app" in txt and "music" in txt
    assert "NEW-AI/fwlib" in w.firmware_dir_text().replace("\\", "/")


def test_start_button_emits_signal(qtbot):
    w = FirmwarePage(); qtbot.addWidget(w)
    w.set_profile(_profile())
    with qtbot.waitSignal(w.start_requested, timeout=500):
        w.start_button().click()


def test_set_busy_disables_start(qtbot):
    w = FirmwarePage(); qtbot.addWidget(w)
    w.set_profile(_profile())
    w.set_busy(True)
    assert not w.start_button().isEnabled()
    w.set_busy(False)
    assert w.start_button().isEnabled()


def test_on_progress_updates_bar(qtbot):
    w = FirmwarePage(); qtbot.addWidget(w)
    w.on_progress(50, 100)
    assert w.progress_value() == 50


def test_on_state_updates_stage_text(qtbot):
    w = FirmwarePage(); qtbot.addWidget(w)
    w.on_state("transfering")
    assert "传输" in w.stage_text()


def test_on_log_appends(qtbot):
    w = FirmwarePage(); qtbot.addWidget(w)
    w.on_log("发送 A.wav")
    assert "A.wav" in w.log_text()
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/gui/test_firmware_page.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 firmware_page.py**

```python
"""固件更新页：固件源 + 待发送文件夹 + 开始按钮 + 阶段进度 + 日志。"""
from __future__ import annotations
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QProgressBar, QLineEdit)
from PySide6.QtCore import Signal
from ..widgets.log_view import LogView
from ..widgets.status_badge import _STATE_TEXT

_STAGE_TEXT = {
    "idle": "就绪", "compiling": "编译中", "connecting": "连接中",
    "entering_upgrade": "进入升级模式", "reconnecting": "等待设备重连",
    "transfering": "传输中", "done": "完成", "error": "出错",
}


class FirmwarePage(QWidget):
    start_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._profile = None
        self._dir_edit = QLineEdit(); self._dir_edit.setReadOnly(True)
        self._summary = QLabel("待发送: -")
        self._start = QPushButton("▶ 开始固件更新"); self._start.setObjectName("primary")
        self._start.clicked.connect(self.start_requested.emit)
        self._stage = QLabel("就绪")
        self._bar = QProgressBar(); self._bar.setRange(0, 100); self._bar.setValue(0)
        self._log = LogView()

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("固件更新"))
        row = QHBoxLayout(); row.addWidget(QLabel("固件源:")); row.addWidget(self._dir_edit, 1)
        lay.addLayout(row)
        lay.addWidget(self._summary)
        lay.addWidget(self._start)
        lay.addWidget(self._stage)
        lay.addWidget(self._bar)
        lay.addWidget(QLabel("日志"))
        lay.addWidget(self._log, 1)

    def set_profile(self, profile) -> None:
        self._profile = profile
        self._dir_edit.setText(str(profile.firmware_dir))
        self._summary.setText("待发送: " + ", ".join(profile.folders))

    def set_busy(self, busy: bool) -> None:
        self._start.setEnabled(not busy)

    def on_progress(self, done: int, total: int) -> None:
        pct = int(done * 100 / total) if total else 0
        self._bar.setValue(pct)

    def on_state(self, state: str) -> None:
        self._stage.setText(_STAGE_TEXT.get(state, state))

    def on_log(self, msg: str) -> None:
        level = "error" if ("失败" in msg or "错误" in msg) else "info"
        self._log.append(msg, level=level)

    # --- 测试辅助访问器 ---
    def start_button(self): return self._start
    def summary_text(self): return self._summary.text()
    def firmware_dir_text(self): return self._dir_edit.text()
    def progress_value(self): return self._bar.value()
    def stage_text(self): return self._stage.text()
    def log_text(self): return self._log.plain_text()
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/gui/test_firmware_page.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/gui/pages/firmware_page.py tests/gui/test_firmware_page.py
git commit -m "feat: FirmwarePage (source/start/progress/log)"
```

---

### Task 9: SettingsPage（TDD）

**Files:**
- Create: `src/lbs_firmware_studio/gui/pages/settings_page.py`
- Test: `tests/gui/test_settings_page.py`

**Interfaces:**
- Consumes: `save_profiles`
- Produces: `SettingsPage(raw_config, config_path)`

- [ ] **Step 1: 写失败测试**

`tests/gui/test_settings_page.py`:
```python
import yaml
from pathlib import Path
from lbs_firmware_studio.gui.pages.settings_page import SettingsPage


def _raw():
    return {"compiler_path": "./tools/rust-msc-latest-win10.exe",
            "products": {"NEW-AI": {"protocol": "custom_frame"}}}


def test_shows_compiler_path(qtbot, tmp_path):
    w = SettingsPage(_raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    assert "rust-msc" in w.compiler_path_text()


def test_edit_and_save_writes_yaml(qtbot, tmp_path):
    cfg = tmp_path / "products.yaml"
    w = SettingsPage(_raw(), cfg); qtbot.addWidget(w)
    w.set_compiler_path("D:/tools/new-compiler.exe")
    w.save()
    back = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert back["compiler_path"] == "D:/tools/new-compiler.exe"
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/gui/test_settings_page.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 settings_page.py**

```python
"""设置页：编辑编译器路径等，保存写回 products.yaml。"""
from __future__ import annotations
from pathlib import Path
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QFileDialog)
from ...backend.profile import save_profiles


class SettingsPage(QWidget):
    def __init__(self, raw_config: dict, config_path: Path, parent=None):
        super().__init__(parent)
        self._raw = raw_config
        self._path = Path(config_path)
        self._compiler = QLineEdit(str(raw_config.get("compiler_path", "")))
        browse = QPushButton("浏览"); browse.clicked.connect(self._browse)
        self._status = QLabel("")
        save_btn = QPushButton("保存"); save_btn.setObjectName("primary")
        save_btn.clicked.connect(self.save)

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("设置"))
        row = QHBoxLayout(); row.addWidget(QLabel("编译器路径:"))
        row.addWidget(self._compiler, 1); row.addWidget(browse)
        lay.addLayout(row)
        lay.addWidget(save_btn)
        lay.addWidget(self._status)
        lay.addStretch()

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择编译器", "", "可执行文件 (*.exe);;所有文件 (*)")
        if path:
            self._compiler.setText(path)

    def set_compiler_path(self, path: str) -> None:
        self._compiler.setText(path)

    def compiler_path_text(self) -> str:
        return self._compiler.text()

    def save(self) -> None:
        self._raw["compiler_path"] = self._compiler.text()
        save_profiles(self._raw, self._path)
        self._status.setText("已保存，重启后生效")
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/gui/test_settings_page.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/gui/pages/settings_page.py tests/gui/test_settings_page.py
git commit -m "feat: SettingsPage (edit compiler path, save to yaml)"
```

---

### Task 10: DeployWorker（TDD vs 模拟器）

**Files:**
- Create: `src/lbs_firmware_studio/gui/worker.py`
- Test: `tests/test_worker.py`

**Interfaces:**
- Consumes: `SerialTransport`, `DeviceDeployer`, DeviceSimulator
- Produces: `DeployWorker(transport, deployer)`：`finished` 信号、`run_firmware(profile, port)`

- [ ] **Step 1: 写失败测试**

`tests/test_worker.py`:
```python
import pathlib, tempfile
from lbs_firmware_studio.backend.profile import DeviceProfile
from lbs_firmware_studio.backend.deployer import DeviceDeployer
from lbs_firmware_studio.backend.serial_transport import SerialTransport
from lbs_firmware_studio.gui.worker import DeployWorker
from tests.fakes import make_fake_serial_pair
from tests.simulator import DeviceSimulator


def _profile(d):
    return DeviceProfile(name="NEW-AI", protocol="custom_frame",
                         firmware_enter_cmd=b"RESET_FWLIB", script_enter_cmd=b"RESET_FWLIB",
                         folders=["app"], chunk_size=248, last_frame_ack="wait_2s",
                         filename_encoding="gbk", firmware_dir=pathlib.Path(d),
                         reopen_retries=3, reopen_delay=0.02, post_reopen_delay=0.0,
                         disappear_timeout=0.0)


def test_worker_runs_firmware_and_emits_finished(qtbot):
    host_ser, dev_ser = make_fake_serial_pair()
    sim = DeviceSimulator(dev_ser, protocol="custom_frame"); sim.start()
    t = SerialTransport(host_ser); t.start_rx()
    try:
        with tempfile.TemporaryDirectory() as d:
            app = pathlib.Path(d) / "app"; app.mkdir()
            (app / "0.o").write_bytes(b"firmware data")
            dep = DeviceDeployer(t)
            worker = DeployWorker(t, dep)
            states = []
            dep.state_changed.connect(lambda s: states.append(s))
            with qtbot.waitSignal(worker.finished, timeout=5000):
                worker.run_firmware(_profile(d), "COM_FAKE")
            assert "done" in states
            assert sim.received_files.get("0.o") == b"firmware data"
    finally:
        t.stop_rx(); sim.stop()


def test_worker_emits_finished_on_error(qtbot):
    # 传一个协议会失败的场景：不启动模拟器 -> 无 ACK -> error，但 finished 仍应发出
    host_ser, dev_ser = make_fake_serial_pair()
    t = SerialTransport(host_ser); t.start_rx()
    try:
        with tempfile.TemporaryDirectory() as d:
            app = pathlib.Path(d) / "app"; app.mkdir()
            (app / "0.o").write_bytes(b"x" * 500)
            prof = _profile(d); prof.ack_timeout = 0.1; prof.last_frame_ack = "skip"
            dep = DeviceDeployer(t)
            worker = DeployWorker(t, dep)
            errors = []
            dep.error.connect(lambda e: errors.append(e))
            with qtbot.waitSignal(worker.finished, timeout=5000):
                worker.run_firmware(prof, "COM_FAKE")
            assert errors  # 有错误上报
    finally:
        t.stop_rx(); sim_close(t)


def sim_close(t):
    try: t.stop_rx()
    except Exception: pass
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_worker.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 worker.py**

```python
"""DeployWorker：把 DeviceDeployer 放到 QThread 里跑，避免阻塞 UI。

用法（MainWindow 里）：
    thread = QThread()
    worker = DeployWorker(transport, deployer)
    worker.moveToThread(thread)
    thread.started.connect(lambda: worker.run_firmware(profile, port))
    worker.finished.connect(thread.quit)
    thread.start()
本 worker 复用 deployer 的 progress/log/state_changed/error 信号（已是 Qt Signal）。
"""
from __future__ import annotations
from PySide6.QtCore import QObject, Signal


class DeployWorker(QObject):
    finished = Signal()

    def __init__(self, transport, deployer, parent=None):
        super().__init__(parent)
        self._transport = transport
        self._deployer = deployer

    def run_firmware(self, profile, port: str) -> None:
        try:
            self._transport.open(port, profile.baud)
            self._transport.start_rx()
            self._deployer.update_firmware(profile, port)
        except Exception:
            pass  # 错误已由 deployer.error 信号上报；此处不再抛以保证 finished 必发
        finally:
            try:
                self._transport.close()
            except Exception:
                pass
            self.finished.emit()
```

> 注：`update_firmware` 出错时 deployer 已 emit error 并 re-raise；worker 捕获异常避免线程崩溃，但确保 `finished` 一定发出，让 UI 解锁。测试里 transport 已在主线程 open，worker.run_firmware 再 open 是幂等的（SerialTransport.open 对已有 serial 只设 timeout）。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_worker.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/gui/worker.py tests/test_worker.py
git commit -m "feat: DeployWorker runs deployer off the UI thread"
```

---

### Task 11: StartupWindow（TDD）

**Files:**
- Create: `src/lbs_firmware_studio/gui/startup_window.py`
- Test: `tests/gui/test_startup_window.py`

**Interfaces:**
- Consumes: profiles dict, `theme`
- Produces: `StartupWindow(profiles)`：`product_selected(str)` 信号

- [ ] **Step 1: 写失败测试**

`tests/gui/test_startup_window.py`:
```python
from lbs_firmware_studio.gui.startup_window import StartupWindow
from lbs_firmware_studio.backend.profile import DeviceProfile


def _profiles():
    return {
        "NEW-AI": DeviceProfile(name="NEW-AI", protocol="custom_frame", display_ports=8),
        "SPARK-AI": DeviceProfile(name="SPARK-AI", protocol="custom_frame", display_ports=4),
        "NEXT-AI": DeviceProfile(name="NEXT-AI", protocol="ymodem", display_ports=2),
    }


def test_shows_all_products(qtbot):
    w = StartupWindow(_profiles()); qtbot.addWidget(w)
    txt = w.all_text()
    assert "NEW-AI" in txt and "SPARK-AI" in txt and "NEXT-AI" in txt


def test_card_click_emits_product(qtbot):
    w = StartupWindow(_profiles()); qtbot.addWidget(w)
    with qtbot.waitSignal(w.product_selected, timeout=500) as blocker:
        w.click_product("SPARK-AI")
    assert blocker.args == ["SPARK-AI"]
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/gui/test_startup_window.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 startup_window.py**

```python
"""启动产品选择界面：每产品一张卡片，点击发出 product_selected。"""
from __future__ import annotations
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
                               QPushButton)
from PySide6.QtCore import Signal, Qt
from . import theme

_PROTO_LABEL = {"custom_frame": "自定义帧", "ymodem": "YMODEM"}


class StartupWindow(QWidget):
    product_selected = Signal(str)

    def __init__(self, profiles: dict, parent=None):
        super().__init__(parent)
        self._buttons = {}
        self.setWindowTitle("LBS Firmware Studio")
        outer = QVBoxLayout(self)
        outer.addWidget(self._center_label("LBS Firmware Studio", 22, theme.TEXT))
        outer.addWidget(self._center_label("选择要操作的产品", 15, theme.MUTED))
        cards = QHBoxLayout(); cards.setSpacing(20)
        for name, prof in profiles.items():
            cards.addWidget(self._make_card(name, prof))
        outer.addLayout(cards)
        outer.addStretch()

    def _center_label(self, text, size, color):
        lbl = QLabel(text); lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"font-size:{size}px; color:{color};")
        return lbl

    def _make_card(self, name, prof):
        card = QFrame(); card.setObjectName("card")
        card.setFixedSize(180, 200)
        lay = QVBoxLayout(card)
        title = QLabel(name); title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size:18px; font-weight:600;")
        ports = QLabel(f"{prof.display_ports} 端口"); ports.setAlignment(Qt.AlignCenter)
        proto = QLabel(_PROTO_LABEL.get(prof.protocol, prof.protocol))
        proto.setAlignment(Qt.AlignCenter); proto.setStyleSheet(f"color:{theme.MUTED};")
        btn = QPushButton("选择"); btn.setObjectName("primary")
        btn.clicked.connect(lambda: self.product_selected.emit(name))
        self._buttons[name] = btn
        lay.addStretch(); lay.addWidget(title); lay.addWidget(ports)
        lay.addWidget(proto); lay.addWidget(btn); lay.addStretch()
        return card

    def click_product(self, name: str) -> None:
        self._buttons[name].click()

    def all_text(self) -> str:
        return " ".join(b_name for b_name in self._buttons)
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/gui/test_startup_window.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/gui/startup_window.py tests/gui/test_startup_window.py
git commit -m "feat: StartupWindow product selection"
```

---

### Task 12: MainWindow（TDD）

**Files:**
- Create: `src/lbs_firmware_studio/gui/main_window.py`
- Test: `tests/gui/test_main_window.py`

**Interfaces:**
- Consumes: 全部页面/控件、`DeployWorker`、`theme`
- Produces: `MainWindow(profile, raw_config, config_path)`：`switch_product_requested` 信号

- [ ] **Step 1: 写失败测试**

`tests/gui/test_main_window.py`:
```python
from lbs_firmware_studio.gui.main_window import MainWindow
from lbs_firmware_studio.backend.profile import DeviceProfile
from pathlib import Path


def _profile():
    return DeviceProfile(name="NEW-AI", protocol="custom_frame", display_ports=8,
                         folders=["app", "version"], firmware_dir=Path("./x"))


def _raw():
    return {"compiler_path": "./t.exe", "products": {"NEW-AI": {"protocol": "custom_frame"}}}


def test_shows_product_name(qtbot, tmp_path):
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    assert "NEW-AI" in w.header_text()


def test_nav_items_present_and_locked(qtbot, tmp_path):
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    labels = w.nav_labels()
    assert "固件更新" in labels
    assert "脚本下发" in labels  # 存在但置灰
    assert "设置" in labels
    # 固件更新可用，脚本下发禁用
    assert w.is_nav_enabled("固件更新") is True
    assert w.is_nav_enabled("脚本下发") is False


def test_nav_switches_page(qtbot, tmp_path):
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w.navigate("设置")
    assert w.current_page_name() == "设置"


def test_switch_product_button_emits(qtbot, tmp_path):
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    with qtbot.waitSignal(w.switch_product_requested, timeout=500):
        w.click_switch_product()


def test_state_updates_badge_and_locks(qtbot, tmp_path):
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    # 模拟 deployer 发状态：transfering -> 锁定、状态灯琥珀
    w._on_state("transfering")
    assert w.is_busy() is True
    w._on_state("done")
    assert w.is_busy() is False
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/gui/test_main_window.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 main_window.py**

```python
"""主窗口：顶栏(产品+状态+串口+切换) + 左导航 + 右 QStackedWidget。
固件更新走 DeployWorker 在 QThread 里跑，信号回主线程更新页面。"""
from __future__ import annotations
from pathlib import Path
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QListWidget, QListWidgetItem, QStackedWidget,
                               QMessageBox)
from PySide6.QtCore import Signal, Qt, QThread
from . import theme
from .widgets.status_badge import StatusBadge
from .widgets.port_selector import PortSelector
from .pages.firmware_page import FirmwarePage
from .pages.settings_page import SettingsPage
from .pages.placeholder_page import PlaceholderPage
from .worker import DeployWorker
from ..backend.serial_transport import SerialTransport
from ..backend.deployer import DeviceDeployer

# 导航项: (标签, 是否可用)
_NAV = [("固件更新", True), ("脚本下发", False), ("代码编辑", False),
        ("数据监控", False), ("设置", True)]
_BUSY_STATES = {"compiling", "connecting", "entering_upgrade", "reconnecting", "transfering"}


class MainWindow(QWidget):
    switch_product_requested = Signal()

    def __init__(self, profile, raw_config: dict, config_path: Path, parent=None):
        super().__init__(parent)
        self._profile = profile
        self._busy = False
        self._thread = None
        self._worker = None
        self.setWindowTitle(f"LBS Firmware Studio - {profile.name}")

        # 顶栏
        self._product_lbl = QLabel(profile.name)
        self._product_lbl.setStyleSheet("font-size:16px; font-weight:600;")
        self._badge = StatusBadge()
        self._port = PortSelector()
        self._switch_btn = QPushButton("切换产品")
        self._switch_btn.clicked.connect(self.switch_product_requested.emit)
        top = QHBoxLayout()
        top.addWidget(self._product_lbl); top.addWidget(self._badge)
        top.addStretch(); top.addWidget(self._port); top.addWidget(self._switch_btn)

        # 左导航 + 右内容
        self._nav = QListWidget(); self._nav.setFixedWidth(160)
        self._stack = QStackedWidget()
        self._pages = {}
        for label, enabled in _NAV:
            item = QListWidgetItem(label if enabled else f"{label} 🔒")
            if not enabled:
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            self._nav.addItem(item)
            page = self._make_page(label)
            self._pages[label] = page
            self._stack.addWidget(page)
        self._nav.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._nav.setCurrentRow(0)

        body = QHBoxLayout()
        body.addWidget(self._nav); body.addWidget(self._stack, 1)

        outer = QVBoxLayout(self)
        outer.addLayout(top); outer.addLayout(body, 1)

        # 固件页信号
        self._firmware.set_profile(profile)
        self._firmware.start_requested.connect(self._start_firmware)

    def _make_page(self, label):
        if label == "固件更新":
            self._firmware = FirmwarePage(); return self._firmware
        if label == "设置":
            return SettingsPage(self._raw_config_ref(), self._config_path_ref())
        return PlaceholderPage(label)

    # 用属性缓存 raw/path（供 _make_page 调用时已存在）
    def _raw_config_ref(self):
        return getattr(self, "_raw", None) or {}
    def _config_path_ref(self):
        return getattr(self, "_path", Path("products.yaml"))

    # ---- 固件更新流程 ----
    def _start_firmware(self):
        port = self._port.selected_port()
        if not port:
            QMessageBox.warning(self, "提示", "未选择串口"); return
        self._transport = SerialTransport()
        self._deployer = DeviceDeployer(self._transport)
        self._deployer.progress.connect(self._firmware.on_progress)
        self._deployer.state_changed.connect(self._on_state)
        self._deployer.log.connect(self._firmware.on_log)
        self._deployer.error.connect(self._on_error)
        self._thread = QThread()
        self._worker = DeployWorker(self._transport, self._deployer)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(lambda: self._worker.run_firmware(self._profile, port))
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._on_finished)
        self._thread.start()

    def _on_state(self, state: str):
        self._badge.set_state(state)
        self._firmware.on_state(state)
        self._busy = state in _BUSY_STATES
        self._firmware.set_busy(self._busy)
        self._port.setEnabled(not self._busy)
        self._switch_btn.setEnabled(not self._busy)

    def _on_error(self, msg: str):
        QMessageBox.critical(self, "错误", msg)

    def _on_finished(self):
        self._busy = False
        self._firmware.set_busy(False)
        self._port.setEnabled(True)
        self._switch_btn.setEnabled(True)

    # ---- 测试辅助 ----
    def header_text(self): return self._product_lbl.text()
    def nav_labels(self): return [self._nav.item(i).text().replace(" 🔒", "")
                                  for i in range(self._nav.count())]
    def is_nav_enabled(self, label):
        for i in range(self._nav.count()):
            if self._nav.item(i).text().replace(" 🔒", "") == label:
                return bool(self._nav.item(i).flags() & Qt.ItemIsEnabled)
        return False
    def navigate(self, label):
        for i in range(self._nav.count()):
            if self._nav.item(i).text().replace(" 🔒", "") == label:
                self._nav.setCurrentRow(i); return
    def current_page_name(self):
        idx = self._stack.currentIndex()
        return list(self._pages.keys())[idx]
    def click_switch_product(self): self._switch_btn.click()
    def is_busy(self): return self._busy
```

> **实现注意**：`_make_page` 里用到 `self._raw` / `self._path`，需在 `__init__` 顶部先赋值 `self._raw = raw_config; self._path = Path(config_path)`（在调用 `_make_page` 之前）。请在实现时把这两行加到 `__init__` 开头（`self._profile = profile` 之后）。删除临时的 `_raw_config_ref/_config_path_ref` 间接层，SettingsPage 直接传 `self._raw, self._path`。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/gui/test_main_window.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/gui/main_window.py tests/gui/test_main_window.py
git commit -m "feat: MainWindow (nav + pages + firmware worker wiring)"
```

---

### Task 13: app.py 入口 + 打通启动流（TDD smoke + 手动）

**Files:**
- Create: `src/lbs_firmware_studio/gui/app.py`
- Modify: `pyproject.toml`（加 gui 入口 + pytest-qt dev 依赖标注）
- Test: `tests/gui/test_app_smoke.py`

**Interfaces:**
- Consumes: `StartupWindow`, `MainWindow`, `load_profiles`, `theme`
- Produces: `main(argv=None) -> int`, `create_app_controller(profiles, raw, path)`（可测的控制器，管理启动窗↔主窗切换）

- [ ] **Step 1: 写失败 smoke 测试**

`tests/gui/test_app_smoke.py`:
```python
from pathlib import Path
from lbs_firmware_studio.gui.app import AppController
from lbs_firmware_studio.backend.profile import DeviceProfile


def _profiles():
    return {"NEW-AI": DeviceProfile(name="NEW-AI", protocol="custom_frame", display_ports=8,
                                    folders=["app"], firmware_dir=Path("./x"))}


def test_controller_starts_on_startup_window(qtbot):
    ctl = AppController(_profiles(), {"products": {}}, Path("products.yaml"))
    ctl.show_startup()
    assert ctl.current_window_kind() == "startup"


def test_controller_switches_to_main_on_select(qtbot):
    ctl = AppController(_profiles(), {"products": {}}, Path("products.yaml"))
    ctl.show_startup()
    ctl.on_product_selected("NEW-AI")
    assert ctl.current_window_kind() == "main"


def test_controller_back_to_startup_on_switch(qtbot):
    ctl = AppController(_profiles(), {"products": {}}, Path("products.yaml"))
    ctl.show_startup()
    ctl.on_product_selected("NEW-AI")
    ctl.on_switch_product()
    assert ctl.current_window_kind() == "startup"
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/gui/test_app_smoke.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 app.py**

```python
"""GUI 入口 + AppController（启动窗 ↔ 主窗切换，可单测）。"""
from __future__ import annotations
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from . import theme
from .startup_window import StartupWindow
from .main_window import MainWindow
from ..backend.profile import load_profiles


class AppController:
    def __init__(self, profiles: dict, raw_config: dict, config_path: Path):
        self._profiles = profiles
        self._raw = raw_config
        self._path = Path(config_path)
        self._startup = None
        self._main = None
        self._kind = None

    def show_startup(self) -> None:
        if self._main is not None:
            self._main.close(); self._main = None
        self._startup = StartupWindow(self._profiles)
        self._startup.product_selected.connect(self.on_product_selected)
        self._startup.show()
        self._kind = "startup"

    def on_product_selected(self, name: str) -> None:
        if self._startup is not None:
            self._startup.close(); self._startup = None
        self._main = MainWindow(self._profiles[name], self._raw, self._path)
        self._main.switch_product_requested.connect(self.on_switch_product)
        self._main.show()
        self._kind = "main"

    def on_switch_product(self) -> None:
        self.show_startup()

    def current_window_kind(self) -> str:
        return self._kind


def main(argv=None) -> int:
    app = QApplication.instance() or QApplication(sys.argv if argv is None else argv)
    app.setStyleSheet(theme.app_qss())
    config_path = Path("products.yaml")
    import yaml
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    profiles = load_profiles(config_path)
    ctl = AppController(profiles, raw, config_path)
    ctl.show_startup()
    app._ctl = ctl  # 防止被 GC
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/gui/test_app_smoke.py -v`
Expected: 3 passed

- [ ] **Step 5: 加 pyproject 入口**

`pyproject.toml` `[project.scripts]` 增加：
```toml
[project.scripts]
lbs-firmware = "lbs_firmware_studio.cli:main"
lbs-firmware-gui = "lbs_firmware_studio.gui.app:main"
```

- [ ] **Step 6: 全量回归 + 手动启动验证**

Run: `python -m pytest -q`
Expected: 全部 passed（约 60 项）

手动（非自动化）：`python -m lbs_firmware_studio.gui.app` 应弹出启动窗，能选产品进主窗、看到固件页与置灰导航、能回启动窗。（真机固件更新用 HITL 清单验证。）

- [ ] **Step 7: Commit**

```bash
git add src/lbs_firmware_studio/gui/app.py pyproject.toml tests/gui/test_app_smoke.py
git commit -m "feat: GUI entrypoint + AppController (startup<->main)"
```

---

## Self-Review 记录

- **Spec 覆盖**：启动产品选择(T11)、主窗骨架+左上角状态+左导航(T12)、固件更新页(T8)、串口自动识别(T5)、设置页可编辑保存(T2,T9)、状态灯(T4)、日志区(T6)、线程模型 worker(T10)、进度阶段文字(T8 on_state/on_progress)、置灰占位(T7,T12)、主题(T3)、入口(T13)、后端 log_cb(T1)、save_profiles+display_ports(T2)、视觉规范(T3 QSS) —— 均有任务。
- **占位扫描**：无 TBD/TODO；每步含完整代码或确切命令。T12 有一处实现注意（`self._raw/_path` 需在 `__init__` 顶部赋值），已在步骤内明确写出正确做法，非占位。
- **类型一致性**：信号名 progress/log/state_changed/error 全程一致；FirmwarePage 的 on_progress/on_state/on_log/set_busy/start_requested 在 T8 定义、T12 使用一致；PortSelector.selected_port、StatusBadge.set_state、save_profiles(raw,path)、load_profiles、DeployWorker(transport,deployer).run_firmware(profile,port) 各任务签名一致；theme.state_color/app_qss 一致。
- **已知风险**：QSS 观感需手动微调（T13 手动验证）；图标本阶段用文字/emoji 占位（🔒 等），真图标资源后续用 ui-ux-pro-max 出；MainWindow 的真实固件流程只能靠 T13 手动 + HITL 真机验证（单测用假信号覆盖逻辑）。
