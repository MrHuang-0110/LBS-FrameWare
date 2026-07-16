# 运行/暂停程序按钮 · 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在代码编辑器页面增加运行/暂停按钮，通过 0xB6 协议命令控制设备端脚本执行，按钮状态由监控数据流中的设备实际运行状态驱动。

**Architecture:** 协议层加 `CMD_RUN_TOGGLE` 常量；MonitorPage 从渲染帧中提取运行状态并通过 `host_state_changed` 信号发出；ScriptEditorPage 新增两个浮动按钮，乐观更新 + 信号驱动；MainWindow 接线转发信号并直接 write 8 字节命令帧。

**Tech Stack:** Python 3.13, PySide6 6.11.1, qtawesome, pytest-qt

## Global Constraints

- GUI 层只做界面，不碰协议/串口写（toggle 命令由 MainWindow 统一发）
- 深色主题：颜色/圆角取 `theme.*` 常量，禁止硬编码色值
- 测试用 pytest-qt，不碰真串口
- 8 字节 toggle 命令主线程直接写，不建线程
- 三产品（NEW-AI/SPARK-AI/NEXT-AI）共用同一命令

---

### Task 1: 协议层 — 新增 CMD_RUN_TOGGLE 常量

**Files:**
- Modify: `src/lbs_firmware_studio/backend/protocol_frame.py`

**Interfaces:**
- Produces: `CMD_RUN_TOGGLE = 0xB6`

- [ ] **Step 1: 在 protocol_frame.py 末尾添加常量**

```python
CMD_RUN_TOGGLE = 0xB6
```

插入位置：在 `CMD_VERSION = 0xDD` 之后，`FOLDER_CMD_MAP` 之前。

- [ ] **Step 2: 验证常量值**

```bash
python -c "from lbs_firmware_studio.backend.protocol_frame import CMD_RUN_TOGGLE; print(hex(CMD_RUN_TOGGLE))"
```

Expected: `0xb6`

- [ ] **Step 3: 验证 build_frame 输出与真机协议一致**

```bash
python -c "from lbs_firmware_studio.backend.protocol_frame import build_frame, CMD_RUN_TOGGLE; f=build_frame(CMD_RUN_TOGGLE, b'\x01'); print(f.hex(' '))"
```

Expected: `5a 97 98 01 b6 01 41 a5`

- [ ] **Step 4: Commit**

```bash
git add src/lbs_firmware_studio/backend/protocol_frame.py
git commit -m "feat(protocol): 新增 CMD_RUN_TOGGLE (0xB6) 运行/暂停切换命令"
```

---

### Task 2: 监控配置 — 新增运行状态路径提取辅助函数

**Files:**
- Modify: `src/lbs_firmware_studio/gui/pages/monitor_profiles.py`

**Interfaces:**
- Produces: `get_host_state_path(product_name: str) -> str | None`

- [ ] **Step 1: 添加辅助函数**

在 `monitor_profiles.py` 文件末尾（`sensor_display_name` 函数之后）添加：

```python
def get_host_state_path(product_name: str) -> "str | None":
    """返回产品监控配置中"运行状态"字段的 JSON 路径，无配置返回 None。"""
    prof = MONITOR_PROFILES.get(product_name)
    if prof is None:
        return None
    for label, path in prof["status_fields"]:
        if label == "运行状态":
            return path
    return None
```

- [ ] **Step 2: 验证各产品路径正确**

```bash
python -c "
from lbs_firmware_studio.gui.pages.monitor_profiles import get_host_state_path
print('NEW-AI:', get_host_state_path('NEW-AI'))
print('SPARK-AI:', get_host_state_path('SPARK-AI'))
print('NEXT-AI:', get_host_state_path('NEXT-AI'))
print('UNKNOWN:', get_host_state_path('UNKNOWN'))
"
```

Expected:
```
NEW-AI: NewAiState
SPARK-AI: WillAiState
NEXT-AI: State
UNKNOWN: None
```

- [ ] **Step 3: Commit**

```bash
git add src/lbs_firmware_studio/gui/pages/monitor_profiles.py
git commit -m "feat(monitor): 新增 get_host_state_path 提取运行状态 JSON 路径"
```

---

### Task 3: MonitorPage — 新增 host_state_changed 信号

**Files:**
- Modify: `src/lbs_firmware_studio/gui/pages/monitor_page.py`

**Interfaces:**
- Consumes: `get_host_state_path` from `monitor_profiles`
- Produces: `host_state_changed = Signal(str)` — 值为 `"start"` / `"stop"` / `""`

- [ ] **Step 1: 添加信号定义**

在 `MonitorPage.__init__` 中，`self._timer` 初始化行之后，添加：

```python
self.host_state_changed = Signal(str)
self._last_host_state = ""
```

- [ ] **Step 2: 在 _render() 中提取运行状态并 emit**

在 `_render` 方法末尾（`self._status.update_from(frame)` 之后），添加状态提取和 emit 逻辑：

```python
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
        # --- 新增：提取运行状态 ---
        self._emit_host_state(frame)
```

新增 `_emit_host_state` 方法：

```python
    def _emit_host_state(self, frame: dict) -> None:
        """从帧中提取运行状态，变化时 emit host_state_changed。"""
        from .monitor_profiles import get_host_state_path, get_by_path
        name = getattr(self._profile, "name", None) if self._profile else None
        if name is None:
            return
        path = get_host_state_path(name)
        if path is None:
            return
        raw = get_by_path(frame, path)
        state = str(raw).strip().lower() if raw is not None else ""
        if state not in ("start", "stop"):
            state = ""  # 非预期值当未知处理
        if state != self._last_host_state:
            self._last_host_state = state
            self.host_state_changed.emit(state)
```

- [ ] **Step 3: 监控停止时 emit 空状态**

在 `_on_worker_state` 方法中，`self._monitoring = (state == "connected")` 之后，添加：

```python
        if not self._monitoring:
            self._last_host_state = ""
            self.host_state_changed.emit("")
```

在 `stop_monitor` 方法中，`self._worker.stop()` 之后，添加：

```python
        self._last_host_state = ""
        self.host_state_changed.emit("")
```

- [ ] **Step 4: Commit**

```bash
git add src/lbs_firmware_studio/gui/pages/monitor_page.py
git commit -m "feat(monitor): MonitorPage 新增 host_state_changed 信号，提取设备运行状态"
```

---

### Task 4: ScriptEditorPage — 新增运行/暂停浮动按钮

**Files:**
- Modify: `src/lbs_firmware_studio/gui/pages/script_editor_page.py`

**Interfaces:**
- Produces: `run_toggle_requested = Signal()`, `on_host_state_changed(state: str)`, `set_run_buttons_enabled(enabled: bool)`, `_run_btn`, `_pause_btn`

- [ ] **Step 1: 在 __init__ 中创建两个浮动按钮**

在 `_deploy_btn` 创建之后，`for b in (self._slot_btn, self._deploy_btn):` 循环之前，添加：

```python
        # 运行按钮
        self._run_btn = QPushButton(self._editor)
        self._run_btn.setObjectName("floatbtn")
        self._run_btn.setIcon(qta.icon("fa5s.play", color=theme.ACCENT))
        self._run_btn.setToolTip("运行程序")
        self._run_btn.clicked.connect(self._on_run_toggle)
        self._run_btn.setEnabled(False)

        # 暂停按钮
        self._pause_btn = QPushButton(self._editor)
        self._pause_btn.setObjectName("floatbtn")
        self._pause_btn.setIcon(qta.icon("fa5s.stop", color=theme.WARNING))
        self._pause_btn.setToolTip("暂停程序")
        self._pause_btn.clicked.connect(self._on_run_toggle)
        self._pause_btn.setEnabled(False)
```

更新浮动按钮样式循环，将 `_run_btn` 和 `_pause_btn` 加入：

```python
        for b in (self._run_btn, self._pause_btn, self._slot_btn, self._deploy_btn):
```

- [ ] **Step 2: 添加 run_toggle_requested 信号**

在 `deploy_requested = Signal(Path, int)` 之后添加：

```python
    run_toggle_requested = Signal()
```

- [ ] **Step 3: 添加 _on_run_toggle 方法**

在 `_on_deploy` 方法附近添加：

```python
    def _on_run_toggle(self):
        """点击运行/暂停按钮：emit 信号让 MainWindow 发 0xB6 命令，乐观更新 UI。"""
        self._running = not self._running
        self._apply_run_state()
        self.run_toggle_requested.emit()
```

- [ ] **Step 4: 添加状态管理方法**

在 `set_busy` 方法附近添加：

```python
    def on_host_state_changed(self, state: str) -> None:
        """接收监控帧确认的运行状态，以帧值为准。"""
        if state == "start":
            self._running = True
        elif state == "stop":
            self._running = False
        else:
            self._running = False   # 未知/空 → 禁用两按钮
        self._apply_run_state()

    def _apply_run_state(self) -> None:
        """根据 _running 和 _busy 更新运行/暂停按钮启用态。"""
        if self._busy:
            self._run_btn.setEnabled(False)
            self._pause_btn.setEnabled(False)
        elif self._running:
            self._run_btn.setEnabled(False)
            self._pause_btn.setEnabled(True)
        else:
            self._run_btn.setEnabled(True)
            self._pause_btn.setEnabled(False)
```

在 `__init__` 末尾（`self._editor.installEventFilter(self)` 之前或之后）添加：

```python
        self._running = False
        self._busy = False
```

- [ ] **Step 5: 扩展 set_busy 以包含运行/暂停按钮**

在 `set_busy` 方法中，按钮列表添加 `_run_btn`、`_pause_btn`：

```python
    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._deploy_btn.setEnabled(not busy)
        self._save_btn.setEnabled(not busy)
        self._open_btn.setEnabled(not busy)
        self._slot_btn.setEnabled(not busy)
        self._tpl_combo.setEnabled(not busy)
        if busy:
            self._run_btn.setEnabled(False)
            self._pause_btn.setEnabled(False)
        else:
            self._apply_run_state()
```

- [ ] **Step 6: 扩展 _reposition_float_buttons 四按钮定位**

```python
    def _reposition_float_buttons(self):
        margin = 8
        w = self._editor.width()
        self._deploy_btn.adjustSize()
        self._slot_btn.adjustSize()
        self._pause_btn.adjustSize()
        self._run_btn.adjustSize()
        dx = w - margin - self._deploy_btn.width()
        self._deploy_btn.move(dx, margin)
        self._slot_btn.move(dx - self._slot_btn.width() - 8, margin)
        self._pause_btn.move(dx - self._slot_btn.width() - self._pause_btn.width() - 16, margin)
        self._run_btn.move(dx - self._slot_btn.width() - self._pause_btn.width() - self._run_btn.width() - 24, margin)
```

- [ ] **Step 7: Commit**

```bash
git add src/lbs_firmware_studio/gui/pages/script_editor_page.py
git commit -m "feat(editor): 新增运行/暂停浮动按钮，乐观更新 + 监控状态驱动"
```

---

### Task 5: MainWindow — 信号接线与 toggle 命令发送

**Files:**
- Modify: `src/lbs_firmware_studio/gui/main_window.py`

**Interfaces:**
- Consumes: `host_state_changed` from MonitorPage, `run_toggle_requested` from ScriptEditorPage, `CMD_RUN_TOGGLE` / `build_frame` from protocol_frame
- Produces: 无新公开接口

- [ ] **Step 1: 导入 protocol_frame**

在文件顶部 import 区添加：

```python
from ..backend import protocol_frame as pf
```

- [ ] **Step 2: 在 __init__ 中接线信号**

在 `self._editor_page.deploy_requested.connect(self._start_script)` 之后添加：

```python
        # 监控运行状态 → 编辑页按钮状态
        self._monitor.host_state_changed.connect(self._editor_page.on_host_state_changed)
        # 编辑页运行/暂停按钮 → 发 0xB6 命令
        self._editor_page.run_toggle_requested.connect(self._on_run_toggle)
```

- [ ] **Step 3: 添加 _on_run_toggle 方法**

```python
    def _on_run_toggle(self):
        """发送运行/暂停切换命令 (0xB6) 到设备。"""
        transport = self._conn.persistent_transport()
        if transport is None:
            return
        try:
            transport.write(pf.build_frame(pf.CMD_RUN_TOGGLE, b"\x01"))
        except Exception:
            pass  # 静默失败，等下一帧监控数据修正按钮状态
```

- [ ] **Step 4: 扩展 _update_deploy_buttons 包含运行/暂停按钮**

在 `_update_deploy_buttons` 方法末尾添加：

```python
        # 运行/暂停按钮仅在连接目标存在时启用初始态（实际状态由监控驱动）
        can_run = has_target and not self._busy
        self._editor_page._run_btn.setEnabled(can_run)
        self._editor_page._pause_btn.setEnabled(False)  # 初始未知状态，暂停禁用
```

- [ ] **Step 5: 导航到编辑页时保持监控运行**

修改 `_on_nav` 方法，离开监控页时仅当目标不是编辑页才停监控：

```python
    def _on_nav(self, key: str):
        # 离开监控页且目标不是编辑页时停监控（编辑页依赖监控数据驱动运行/暂停按钮）
        if key != "monitor" and key != "editor" and self._pages.get("monitor") is self._stack.currentWidget():
            self._monitor.stop_monitor()
        self._stack.setCurrentWidget(self._pages[key])
```

- [ ] **Step 6: Commit**

```bash
git add src/lbs_firmware_studio/gui/main_window.py
git commit -m "feat(main): 接线运行/暂停信号，导航到编辑页时保持监控运行"
```

---

### Task 6: 测试 — protocol_frame CMD_RUN_TOGGLE

**Files:**
- Modify: `tests/test_protocol_frame.py`

- [ ] **Step 1: 添加测试用例**

在文件末尾添加：

```python
from lbs_firmware_studio.backend.protocol_frame import CMD_RUN_TOGGLE, build_frame


def test_run_toggle_frame_matches_device_protocol():
    """验证 0xB6 帧与真机协议逐字节一致：5A 97 98 01 B6 01 41 A5"""
    frame = build_frame(CMD_RUN_TOGGLE, b"\x01")
    expected = bytes([0x5A, 0x97, 0x98, 0x01, 0xB6, 0x01, 0x41, 0xA5])
    assert frame == expected
    assert len(frame) == 8


def test_run_toggle_cmd_value():
    assert CMD_RUN_TOGGLE == 0xB6
```

- [ ] **Step 2: 运行测试**

```bash
python -m pytest tests/test_protocol_frame.py::test_run_toggle_frame_matches_device_protocol tests/test_protocol_frame.py::test_run_toggle_cmd_value -v
```

Expected: 2 PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_protocol_frame.py
git commit -m "test(protocol): 验证 CMD_RUN_TOGGLE 帧与真机协议一致"
```

---

### Task 7: 测试 — monitor_profiles get_host_state_path

**Files:**
- Modify: `tests/gui/test_monitor_profiles.py`

- [ ] **Step 1: 添加测试用例**

在文件末尾添加：

```python
from lbs_firmware_studio.gui.pages.monitor_profiles import get_host_state_path


def test_get_host_state_path_new_ai():
    assert get_host_state_path("NEW-AI") == "NewAiState"


def test_get_host_state_path_spark_ai():
    assert get_host_state_path("SPARK-AI") == "WillAiState"


def test_get_host_state_path_next_ai():
    assert get_host_state_path("NEXT-AI") == "State"


def test_get_host_state_path_unknown_product():
    assert get_host_state_path("UNKNOWN") is None


def test_get_host_state_path_none():
    assert get_host_state_path(None) is None
```

- [ ] **Step 2: 运行测试**

```bash
python -m pytest tests/gui/test_monitor_profiles.py -v -k "host_state"
```

Expected: 5 PASS

- [ ] **Step 3: Commit**

```bash
git add tests/gui/test_monitor_profiles.py
git commit -m "test(monitor): 验证 get_host_state_path 各产品路径正确"
```

---

### Task 8: 测试 — MonitorPage host_state_changed 信号

**Files:**
- Modify: `tests/gui/test_monitor_page.py`

- [ ] **Step 1: 添加测试用例**

在文件末尾添加：

```python
from PySide6.QtCore import Signal


def test_host_state_changed_emits_on_start(qtbot):
    """监控帧中运行状态为 start 时 emit host_state_changed("start")"""
    p = MonitorPage(); qtbot.addWidget(p)
    p.set_profile(_profile("NEW-AI"))
    states = []
    p.host_state_changed.connect(lambda s: states.append(s))
    frame = dict(NEW_AI_FRAME)
    frame["NewAiState"] = "start"
    p._on_frame(frame)
    p._render()
    assert states == ["start"]


def test_host_state_changed_emits_on_stop(qtbot):
    """监控帧中运行状态为 stop 时 emit host_state_changed("stop")"""
    p = MonitorPage(); qtbot.addWidget(p)
    p.set_profile(_profile("NEW-AI"))
    # 先发一次 start 建立初始状态
    frame_start = dict(NEW_AI_FRAME)
    frame_start["NewAiState"] = "start"
    p._on_frame(frame_start)
    p._render()
    states = []
    p.host_state_changed.connect(lambda s: states.append(s))
    frame_stop = dict(NEW_AI_FRAME)
    frame_stop["NewAiState"] = "stop"
    p._on_frame(frame_stop)
    p._render()
    assert states == ["stop"]


def test_host_state_changed_not_emitted_on_same_state(qtbot):
    """状态与上次相同时不重复 emit"""
    p = MonitorPage(); qtbot.addWidget(p)
    p.set_profile(_profile("NEW-AI"))
    frame = dict(NEW_AI_FRAME)
    frame["NewAiState"] = "stop"
    p._on_frame(frame)
    p._render()
    states = []
    p.host_state_changed.connect(lambda s: states.append(s))
    # 再发一次相同状态
    p._on_frame(frame)
    p._render()
    assert states == []  # 未变化，不 emit


def test_host_state_changed_emits_empty_on_stop_monitor(qtbot):
    """监控停止时 emit host_state_changed("")"""
    p = MonitorPage(); qtbot.addWidget(p)
    p.set_profile(_profile("NEW-AI"))
    frame = dict(NEW_AI_FRAME)
    frame["NewAiState"] = "start"
    p._on_frame(frame)
    p._render()
    states = []
    p.host_state_changed.connect(lambda s: states.append(s))
    p.stop_monitor()
    assert states == [""]


def test_host_state_changed_unknown_product_no_emit(qtbot):
    """未知产品不 emit host_state_changed"""
    p = MonitorPage(); qtbot.addWidget(p)
    p.set_profile(_profile("MYSTERY"))
    states = []
    p.host_state_changed.connect(lambda s: states.append(s))
    p._on_frame({"version": 1})
    p._render()
    assert states == []
```

- [ ] **Step 2: 运行测试**

```bash
python -m pytest tests/gui/test_monitor_page.py -v -k "host_state"
```

Expected: 5 PASS

- [ ] **Step 3: Commit**

```bash
git add tests/gui/test_monitor_page.py
git commit -m "test(monitor): 验证 host_state_changed 信号 emit 时机与去重"
```

---

### Task 9: 测试 — ScriptEditorPage 运行/暂停按钮

**Files:**
- Modify: `tests/gui/test_script_editor_page.py`

- [ ] **Step 1: 添加测试用例**

在文件末尾添加：

```python
def test_run_pause_buttons_exist(qtbot, tmp_path):
    """运行和暂停按钮在页面创建后存在。"""
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    assert hasattr(page, "_run_btn")
    assert hasattr(page, "_pause_btn")
    assert "运行" in page._run_btn.toolTip()
    assert "暂停" in page._pause_btn.toolTip()


def test_run_pause_buttons_initially_disabled(qtbot, tmp_path):
    """初始状态（未知）两个按钮均禁用。"""
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    assert page._run_btn.isEnabled() is False
    assert page._pause_btn.isEnabled() is False


def test_run_pause_buttons_are_children_of_editor(qtbot, tmp_path):
    """运行/暂停按钮是编辑器子控件（浮动定位）。"""
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    assert page._run_btn.parent() is page._editor
    assert page._pause_btn.parent() is page._editor


def test_on_host_state_changed_start_enables_pause_disables_run(qtbot, tmp_path):
    """监控状态 start → 运行禁用、暂停启用。"""
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    page.on_host_state_changed("start")
    assert page._run_btn.isEnabled() is False
    assert page._pause_btn.isEnabled() is True


def test_on_host_state_changed_stop_enables_run_disables_pause(qtbot, tmp_path):
    """监控状态 stop → 运行启用、暂停禁用。"""
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    page.on_host_state_changed("stop")
    assert page._run_btn.isEnabled() is True
    assert page._pause_btn.isEnabled() is False


def test_on_host_state_changed_empty_disables_both(qtbot, tmp_path):
    """监控状态 "" → 两按钮均禁用。"""
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    page.on_host_state_changed("stop")   # 先设一个有效状态
    page.on_host_state_changed("")        # 再清空
    assert page._run_btn.isEnabled() is False
    assert page._pause_btn.isEnabled() is False


def test_run_button_click_emits_run_toggle(qtbot, tmp_path):
    """点击运行按钮 emit run_toggle_requested 信号，并乐观切换状态。"""
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    page.on_host_state_changed("stop")   # 初始：已暂停
    fired = []
    page.run_toggle_requested.connect(lambda: fired.append(True))
    page._run_btn.click()
    assert fired == [True]
    # 乐观更新：运行按钮禁用、暂停按钮启用
    assert page._run_btn.isEnabled() is False
    assert page._pause_btn.isEnabled() is True


def test_pause_button_click_emits_run_toggle(qtbot, tmp_path):
    """点击暂停按钮 emit run_toggle_requested 信号，并乐观切换状态。"""
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    page.on_host_state_changed("start")  # 初始：运行中
    fired = []
    page.run_toggle_requested.connect(lambda: fired.append(True))
    page._pause_btn.click()
    assert fired == [True]
    # 乐观更新：暂停按钮禁用、运行按钮启用
    assert page._pause_btn.isEnabled() is False
    assert page._run_btn.isEnabled() is True


def test_set_busy_disables_run_pause_buttons(qtbot, tmp_path):
    """下发忙碌时运行/暂停按钮均禁用。"""
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    page.on_host_state_changed("stop")   # 运行按钮应启用
    assert page._run_btn.isEnabled() is True
    page.set_busy(True)
    assert page._run_btn.isEnabled() is False
    assert page._pause_btn.isEnabled() is False
    page.set_busy(False)
    assert page._run_btn.isEnabled() is True   # 恢复


def test_set_busy_false_restores_run_state(qtbot, tmp_path):
    """忙碌结束后恢复为运行状态对应的按钮启用态。"""
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    page.on_host_state_changed("start")  # 运行中
    page.set_busy(True)
    assert page._run_btn.isEnabled() is False
    page.set_busy(False)
    assert page._run_btn.isEnabled() is False   # 运行中，运行按钮仍禁用
    assert page._pause_btn.isEnabled() is True  # 运行中，暂停按钮启用
```

- [ ] **Step 2: 运行测试**

```bash
python -m pytest tests/gui/test_script_editor_page.py -v -k "run_pause or host_state"
```

Expected: 10 PASS

- [ ] **Step 3: 确保原有测试仍通过**

```bash
python -m pytest tests/gui/test_script_editor_page.py -v
```

Expected: 全部 PASS（原有 17 个 + 新增 10 个 = 27 个）

- [ ] **Step 4: Commit**

```bash
git add tests/gui/test_script_editor_page.py
git commit -m "test(editor): 运行/暂停按钮状态管理与信号 emit 测试"
```

---

### Task 10: 测试 — MainWindow 信号接线与 toggle 发送

**Files:**
- Modify: `tests/gui/test_main_window_buttons.py`

- [ ] **Step 1: 添加测试用例**

在文件末尾添加：

```python
from lbs_firmware_studio.backend import protocol_frame as pf


class _FakeTransport:
    """模拟 transport.write，记录写入的字节。"""
    def __init__(self):
        self.written = []
    def write(self, data: bytes):
        self.written.append(data)


def test_run_pause_buttons_disabled_without_target(qtbot, tmp_path):
    """未选目标时运行/暂停按钮禁用。"""
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    assert not w._editor_page._run_btn.isEnabled()
    assert not w._editor_page._pause_btn.isEnabled()


def test_run_pause_buttons_enabled_after_port_selected(qtbot, tmp_path):
    """选中串口后运行/暂停按钮初始启用（暂停按钮因未知状态仍禁用）。"""
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w._conn._port.inject_ports([_FakePort("COM3", "LBS Serial (COM3)", 0x0483, 0x5740)])
    qtbot.waitUntil(lambda: w._editor_page._run_btn.isEnabled(), timeout=1000)
    # 暂停按钮初始禁用（未知状态）
    assert not w._editor_page._pause_btn.isEnabled()


def test_run_toggle_sends_0xb6_frame(qtbot, tmp_path, monkeypatch):
    """点击运行按钮后 MainWindow 发送正确的 0xB6 帧。"""
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w._conn._port.inject_ports([_FakePort("COM3", "LBS Serial (COM3)", 0x0483, 0x5740)])
    qtbot.waitUntil(lambda: w._editor_page._run_btn.isEnabled(), timeout=1000)
    # 注入假 transport
    fake = _FakeTransport()
    monkeypatch.setattr(w._conn, "persistent_transport", lambda: fake)
    # 让编辑页处于"已暂停"状态以确保运行按钮可用
    w._editor_page.on_host_state_changed("stop")
    w._editor_page._run_btn.click()
    assert len(fake.written) == 1
    expected = pf.build_frame(pf.CMD_RUN_TOGGLE, b"\x01")
    assert fake.written[0] == expected


def test_run_toggle_no_transport_silent(qtbot, tmp_path, monkeypatch):
    """无持久链路时点击运行按钮静默返回，不崩溃。"""
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w._conn._port.inject_ports([_FakePort("COM3", "LBS Serial (COM3)", 0x0483, 0x5740)])
    qtbot.waitUntil(lambda: w._editor_page._run_btn.isEnabled(), timeout=1000)
    monkeypatch.setattr(w._conn, "persistent_transport", lambda: None)
    w._editor_page.on_host_state_changed("stop")
    # 不应崩溃
    w._editor_page._run_btn.click()


def test_host_state_signal_forwarded_to_editor(qtbot, tmp_path):
    """MonitorPage.host_state_changed 信号正确转发到 ScriptEditorPage。"""
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w._conn._port.inject_ports([_FakePort("COM3", "LBS Serial (COM3)", 0x0483, 0x5740)])
    qtbot.waitUntil(lambda: w._editor_page._run_btn.isEnabled(), timeout=1000)
    # 直接 emit 监控页信号
    w._monitor.host_state_changed.emit("start")
    assert w._editor_page._run_btn.isEnabled() is False
    assert w._editor_page._pause_btn.isEnabled() is True
    w._monitor.host_state_changed.emit("stop")
    assert w._editor_page._run_btn.isEnabled() is True
    assert w._editor_page._pause_btn.isEnabled() is False
```

- [ ] **Step 2: 运行测试**

```bash
python -m pytest tests/gui/test_main_window_buttons.py -v -k "run_pause or run_toggle or host_state"
```

Expected: 5 PASS

- [ ] **Step 3: 确保原有测试仍通过**

```bash
python -m pytest tests/gui/test_main_window_buttons.py -v
```

Expected: 全部 PASS

- [ ] **Step 4: Commit**

```bash
git add tests/gui/test_main_window_buttons.py
git commit -m "test(main): 运行/暂停信号接线与 0xB6 帧发送测试"
```

---

### Task 11: 回归测试 — 全量 GUI 测试套件

- [ ] **Step 1: 运行全部 GUI 测试**

```bash
python -m pytest tests/gui/ -v
```

Expected: 全部 PASS，无回归

- [ ] **Step 2: 运行全部后端测试**

```bash
python -m pytest tests/ --ignore=tests/gui -v
```

Expected: 全部 PASS

- [ ] **Step 3: 如有失败，修复后重新运行**

- [ ] **Step 4: Commit（如有修复）**

```bash
git add -u
git commit -m "fix: 回归修复"
```