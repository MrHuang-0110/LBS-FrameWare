# VS Code 深色风格 UI 返工 · 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把现有浅色 App Store 风格 GUI 重做为 VS Code Dark+ 深色风格（左 Activity Bar + 顶栏 + 底部蓝状态栏），业务逻辑零改动。

**Architecture:** 重写 theme.py 为深色令牌+QSS；新增 ActivityBar（纯图标竖条）和 StatusBar（底部蓝条）两个控件；重构 main_window 用它们替换旧 QListWidget 导航并加顶栏/底栏；startup_window 改单击框选+双击进入；worker/backend 完全不动。

**Tech Stack:** Python 3.13、PySide6 6.11.1、qtawesome（新增）、pytest + pytest-qt。

## Global Constraints

- Python 3.13；Windows；解释器用 `python`。
- 业务逻辑零改动：`gui/worker.py`、`backend/**` 不得修改。
- VS Code Dark+ 精确色值（spec §2）：BG_EDITOR `#1E1E1E`、BG_SIDEBAR `#252526`、BG_BAR `#333333`、BG_INPUT `#3C3C3C`、BG_HOVER `#2A2D2E`、BG_SELECTED `#094771`、STATUSBAR `#007ACC`；TEXT_PRIMARY `#CCCCCC`、TEXT_SECONDARY `#9D9D9D`、TEXT_DISABLED `#6A6A6A`；ACCENT `#007ACC`、ACCENT_HOVER `#1177BB`、SUCCESS `#4EC9B0`、WARNING `#CCA700`、ERROR `#F14C4C`、BORDER `#3E3E42`、ICON_IDLE `#858585`、ICON_DISABLED `#4A4A4A`。
- 全局圆角 2px（VS Code 近直角简约）。
- state→color：idle=`#858585`；compiling/connecting/entering_upgrade/reconnecting/transfering=`#CCA700`；done=`#4EC9B0`；error=`#F14C4C`；未知→idle 灰。
- 测试用 pytest-qt + 手动 emit 信号，不碰真串口。
- **已知环境问题**：多个 QThread 测试在同一 pytest 进程 teardown 时可能段错误（exit 9），但测试本身通过——GUI 测试**按文件单独跑**验证（`pytest tests/gui/test_X.py -v`），不要求一次性全绿。
- MainWindow 测试访问器签名保持稳定：`header_text()`、`nav_labels()`、`is_nav_enabled(label)`、`navigate(label)`、`current_page_name()`、`click_switch_product()`、`is_busy()`；信号 `switch_product_requested`。
- Activity Bar 项：固件更新(启用)、脚本下发/代码编辑/数据监控(禁用)、设置(启用，沉底)。

---

## File Structure

```
src/lbs_firmware_studio/gui/
  theme.py            # 重写：VS Code Dark+ 令牌 + 深色 QSS
  widgets/
    activity_bar.py   # 新增：纯图标竖条
    status_bar.py     # 新增：底部蓝色状态栏
    status_badge.py   # 弃用（删除；连接状态移到 status_bar）
    port_selector.py  # 不改逻辑（深色靠全局 QSS）
    log_view.py       # 微调：级别色改深色适配值
  pages/
    firmware_page.py  # 微调：移除对 status_badge._STATE_TEXT 的依赖(内联)
    settings_page.py  # 不改（深色靠全局 QSS）
    placeholder_page.py # 不改
  main_window.py      # 重构：ActivityBar + 顶栏 + StatusBar
  startup_window.py   # 改交互：单击框选 + 双击进入
  app.py              # 不改
pyproject.toml        # 加 qtawesome 依赖
tests/gui/
  test_theme.py           # 更新：深色令牌值
  test_activity_bar.py    # 新增
  test_status_bar.py      # 新增
  test_startup_window.py  # 更新：双击进入 + 单击框选
  test_main_window.py     # 更新：新布局访问器
  test_log_view.py        # 保留（级别色断言若变则更新）
  test_status_badge.py    # 删除（控件弃用）
```

## 接口契约

```python
# theme.py（重写，新增/变更常量）
BG_EDITOR="#1E1E1E"; BG_SIDEBAR="#252526"; BG_BAR="#333333"; BG_INPUT="#3C3C3C"
BG_HOVER="#2A2D2E"; BG_SELECTED="#094771"; STATUSBAR="#007ACC"
TEXT_PRIMARY="#CCCCCC"; TEXT_SECONDARY="#9D9D9D"; TEXT_DISABLED="#6A6A6A"; TEXT_ON_ACCENT="#FFFFFF"
ACCENT="#007ACC"; ACCENT_HOVER="#1177BB"; SUCCESS="#4EC9B0"; WARNING="#CCA700"
ERROR="#F14C4C"; BORDER="#3E3E42"; ICON_IDLE="#858585"; ICON_DISABLED="#4A4A4A"
def state_color(state: str) -> str      # 深色映射
def app_qss() -> str                    # 深色全局 QSS

# widgets/activity_bar.py
class ActivityBar(QWidget):
    current_changed = Signal(str)        # 发出当前选中项 key
    def __init__(self, items: list[tuple[str, str, bool]]): ...  # [(key, icon_name, enabled)]
    def set_current(self, key: str) -> None
    def current_key(self) -> str
    def keys(self) -> list[str]
    def is_enabled(self, key: str) -> bool
    def set_locked(self, locked: bool) -> None   # busy 时锁全部切换

# widgets/status_bar.py
class StatusBar(QWidget):
    def set_connection(self, port: str | None, baud: int | None) -> None
    def set_product(self, name: str) -> None
    def set_state(self, state: str) -> None
    def connection_text(self) -> str     # 测试用
    def state_text(self) -> str          # 测试用
    def state_color(self) -> str         # 测试用(当前 state 对应色)

# main_window.py（访问器签名不变，内部换实现）
class MainWindow(QWidget):
    switch_product_requested = Signal()
    # header_text/nav_labels/is_nav_enabled/navigate/current_page_name/click_switch_product/is_busy 保持

# startup_window.py
class StartupWindow(QWidget):
    product_selected = Signal(str)       # 双击发出
    selection_changed = Signal(str)      # 单击框选发出(新增)
    def selected_product(self) -> str | None   # 当前框选(新增)
    def click_product(self, name: str) -> None    # 单击框选(测试)
    def double_click_product(self, name: str) -> None  # 双击进入(测试)
```

---

### Task 1: 加 qtawesome 依赖 + 装

**Files:**
- Modify: `pyproject.toml`

**Interfaces:** Produces: qtawesome 可导入

- [ ] **Step 1: 改 pyproject 依赖**

`pyproject.toml` 的 `dependencies` 增加 `qtawesome>=1.3`：
```toml
dependencies = ["pyserial>=3.5", "PyYAML>=6.0", "PySide6>=6.5", "qtawesome>=1.3"]
```
（若现有 dependencies 没列 PySide6 就按现状加 qtawesome 一项即可，别删已有项。）

- [ ] **Step 2: 安装并验证**

Run: `python -m pip install qtawesome && python -c "import qtawesome; print(qtawesome.__version__)"`
Expected: 打印版本号（如 1.3.1），无错误

- [ ] **Step 3: 验证图标能取（冒烟）**

Run: `python -c "import qtawesome as qta; from PySide6.QtWidgets import QApplication; app=QApplication([]); ic=qta.icon('fa5s.download'); print('ok', ic is not None)"`
Expected: `ok True`（确认 qtawesome + Font Awesome 5 solid 图标可用）

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "build: add qtawesome dependency for VS Code style icons"
```

---

### Task 2: theme.py 重写为 VS Code Dark+（TDD）

**Files:**
- Modify: `src/lbs_firmware_studio/gui/theme.py`
- Modify: `tests/gui/test_theme.py`

**Interfaces:** Produces: 深色令牌常量、`state_color`、`app_qss`

- [ ] **Step 1: 更新测试为深色值**

覆盖 `tests/gui/test_theme.py` 全文：
```python
from lbs_firmware_studio.gui import theme


def test_dark_colors_defined():
    assert theme.BG_EDITOR == "#1E1E1E"
    assert theme.BG_BAR == "#333333"
    assert theme.STATUSBAR == "#007ACC"
    assert theme.ACCENT == "#007ACC"
    assert theme.TEXT_PRIMARY == "#CCCCCC"
    assert theme.BORDER == "#3E3E42"


def test_state_color_dark_mapping():
    assert theme.state_color("idle") == "#858585"
    assert theme.state_color("transfering") == "#CCA700"
    assert theme.state_color("reconnecting") == "#CCA700"
    assert theme.state_color("done") == "#4EC9B0"
    assert theme.state_color("error") == "#F14C4C"
    assert theme.state_color("unknown_x") == "#858585"


def test_app_qss_is_dark():
    qss = theme.app_qss()
    assert isinstance(qss, str) and len(qss) > 0
    assert "#1E1E1E" in qss     # 深色底进了 QSS
    assert "#007ACC" in qss     # 强调蓝进了 QSS
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/gui/test_theme.py -v`
Expected: FAIL（旧的浅色常量 BG/ACCENT 值不符 / 缺 BG_EDITOR 等）

- [ ] **Step 3: 重写 theme.py**

```python
"""VS Code Dark+ 深色主题：配色令牌 + 全局 QSS。集中管理。"""
from __future__ import annotations

# 背景分层
BG_EDITOR = "#1E1E1E"
BG_SIDEBAR = "#252526"
BG_BAR = "#333333"
BG_INPUT = "#3C3C3C"
BG_HOVER = "#2A2D2E"
BG_SELECTED = "#094771"
STATUSBAR = "#007ACC"
# 文字
TEXT_PRIMARY = "#CCCCCC"
TEXT_SECONDARY = "#9D9D9D"
TEXT_DISABLED = "#6A6A6A"
TEXT_ON_ACCENT = "#FFFFFF"
# 强调 / 语义
ACCENT = "#007ACC"
ACCENT_HOVER = "#1177BB"
SUCCESS = "#4EC9B0"
WARNING = "#CCA700"
ERROR = "#F14C4C"
BORDER = "#3E3E42"
ICON_IDLE = "#858585"
ICON_DISABLED = "#4A4A4A"

_STATE_COLORS = {
    "idle": ICON_IDLE,
    "compiling": WARNING, "connecting": WARNING, "entering_upgrade": WARNING,
    "reconnecting": WARNING, "transfering": WARNING,
    "done": SUCCESS,
    "error": ERROR,
}


def state_color(state: str) -> str:
    return _STATE_COLORS.get(state, ICON_IDLE)


def app_qss() -> str:
    return f"""
    QWidget {{ background: {BG_EDITOR}; color: {TEXT_PRIMARY};
        font-family: 'Segoe UI', 'Microsoft YaHei UI', sans-serif; font-size: 13px; }}
    QFrame#card {{ background: {BG_SIDEBAR}; border: 1px solid {BORDER}; border-radius: 2px; }}
    QLabel {{ background: transparent; }}
    QPushButton#primary {{ background: {ACCENT}; color: {TEXT_ON_ACCENT}; border: none;
        border-radius: 2px; padding: 6px 14px; }}
    QPushButton#primary:hover {{ background: {ACCENT_HOVER}; }}
    QPushButton#primary:disabled {{ background: {BG_INPUT}; color: {TEXT_DISABLED}; }}
    QPushButton {{ background: transparent; color: {TEXT_PRIMARY};
        border: 1px solid {BORDER}; border-radius: 2px; padding: 5px 12px; }}
    QPushButton:hover {{ background: {BG_HOVER}; }}
    QPushButton:disabled {{ color: {TEXT_DISABLED}; border-color: {BG_INPUT}; }}
    QComboBox {{ background: {BG_INPUT}; color: {TEXT_PRIMARY};
        border: 1px solid {BORDER}; border-radius: 2px; padding: 4px 8px; }}
    QComboBox QAbstractItemView {{ background: {BG_INPUT}; color: {TEXT_PRIMARY};
        selection-background-color: {BG_SELECTED}; }}
    QLineEdit {{ background: {BG_INPUT}; color: {TEXT_PRIMARY};
        border: 1px solid {BORDER}; border-radius: 2px; padding: 4px 8px; }}
    QPlainTextEdit, QTextEdit {{ background: {BG_EDITOR}; color: {TEXT_PRIMARY};
        border: 1px solid {BORDER}; border-radius: 2px;
        font-family: 'Cascadia Code', 'Consolas', monospace; }}
    QProgressBar {{ border: none; border-radius: 2px; background: {BG_INPUT};
        height: 6px; text-align: center; color: {TEXT_PRIMARY}; }}
    QProgressBar::chunk {{ background: {ACCENT}; border-radius: 2px; }}
    QToolTip {{ background: {BG_SIDEBAR}; color: {TEXT_PRIMARY}; border: 1px solid {BORDER}; }}
    """
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/gui/test_theme.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/gui/theme.py tests/gui/test_theme.py
git commit -m "feat: rewrite theme as VS Code Dark+ dark palette + QSS"
```

---

### Task 3: ActivityBar 控件（TDD）

**Files:**
- Create: `src/lbs_firmware_studio/gui/widgets/activity_bar.py`
- Test: `tests/gui/test_activity_bar.py`

**Interfaces:**
- Consumes: qtawesome, theme
- Produces: `ActivityBar(items)`、`current_changed(str)`、`set_current`、`current_key`、`keys`、`is_enabled`、`set_locked`

- [ ] **Step 1: 写失败测试**

`tests/gui/test_activity_bar.py`:
```python
from lbs_firmware_studio.gui.widgets.activity_bar import ActivityBar

# items: (key, icon_name, enabled)
_ITEMS = [
    ("firmware", "fa5s.download", True),
    ("scripts", "fa5s.upload", False),
    ("settings", "fa5s.cog", True),
]


def test_keys_and_enabled(qtbot):
    w = ActivityBar(_ITEMS); qtbot.addWidget(w)
    assert w.keys() == ["firmware", "scripts", "settings"]
    assert w.is_enabled("firmware") is True
    assert w.is_enabled("scripts") is False


def test_click_enabled_emits_current_changed(qtbot):
    w = ActivityBar(_ITEMS); qtbot.addWidget(w)
    with qtbot.waitSignal(w.current_changed, timeout=500) as blocker:
        w.set_current("settings")
    assert blocker.args == ["settings"]
    assert w.current_key() == "settings"


def test_disabled_item_not_selectable(qtbot):
    w = ActivityBar(_ITEMS); qtbot.addWidget(w)
    w.set_current("firmware")
    w.set_current("scripts")   # 禁用项：忽略
    assert w.current_key() == "firmware"


def test_set_locked_blocks_switch(qtbot):
    w = ActivityBar(_ITEMS); qtbot.addWidget(w)
    w.set_current("firmware")
    w.set_locked(True)
    w.set_current("settings")  # 锁定中：忽略
    assert w.current_key() == "firmware"
    w.set_locked(False)
    w.set_current("settings")
    assert w.current_key() == "settings"
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/gui/test_activity_bar.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 activity_bar.py**

```python
"""VS Code 风格 Activity Bar：纯图标竖条，悬停 tooltip，选中左侧 2px 蓝亮条。"""
from __future__ import annotations
import qtawesome as qta
from PySide6.QtWidgets import QWidget, QVBoxLayout, QToolButton
from PySide6.QtCore import Signal, Qt, QSize
from .. import theme

# 功能名 tooltip
_LABELS = {
    "firmware": "固件更新", "scripts": "脚本下发", "editor": "代码编辑",
    "monitor": "数据监控", "settings": "设置",
}


class ActivityBar(QWidget):
    current_changed = Signal(str)

    def __init__(self, items: list[tuple[str, str, bool]], parent=None):
        super().__init__(parent)
        self.setFixedWidth(48)
        self.setStyleSheet(f"background: {theme.BG_BAR};")
        self._items = items
        self._buttons: dict[str, QToolButton] = {}
        self._current: str | None = None
        self._locked = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 4); lay.setSpacing(0)
        for key, icon_name, enabled in items:
            if key == "settings":
                lay.addStretch(1)   # 设置沉底
            btn = self._make_button(key, icon_name, enabled)
            self._buttons[key] = btn
            lay.addWidget(btn, 0, Qt.AlignHCenter)

    def _make_button(self, key, icon_name, enabled):
        btn = QToolButton()
        btn.setFixedSize(48, 48)
        btn.setIconSize(QSize(24, 24))
        btn.setToolTip(_LABELS.get(key, key) + ("" if enabled else " · 即将推出"))
        btn.setCursor(Qt.PointingHandCursor if enabled else Qt.ArrowCursor)
        color = theme.ICON_IDLE if enabled else theme.ICON_DISABLED
        btn.setIcon(qta.icon(icon_name, color=color))
        btn.setStyleSheet("QToolButton { border: none; background: transparent; }")
        btn.setEnabled(enabled)
        if enabled:
            btn.clicked.connect(lambda _=False, k=key: self.set_current(k))
        self._icon_names = getattr(self, "_icon_names", {})
        self._icon_names[key] = icon_name
        return btn

    def set_current(self, key: str) -> None:
        if self._locked:
            return
        if key not in self._buttons or not self._buttons[key].isEnabled():
            return
        if key == self._current:
            return
        self._current = key
        self._restyle()
        self.current_changed.emit(key)

    def _restyle(self) -> None:
        for key, btn in self._buttons.items():
            if not btn.isEnabled():
                continue
            selected = (key == self._current)
            color = theme.TEXT_ON_ACCENT if selected else theme.ICON_IDLE
            btn.setIcon(qta.icon(self._icon_names[key], color=color))
            # 选中：左侧 2px 蓝亮条 + 轻背景
            if selected:
                btn.setStyleSheet(
                    f"QToolButton {{ border: none; background: {theme.BG_HOVER};"
                    f" border-left: 2px solid {theme.ACCENT}; }}")
            else:
                btn.setStyleSheet("QToolButton { border: none; background: transparent; }")

    def current_key(self) -> str:
        return self._current

    def keys(self) -> list[str]:
        return [k for k, _, _ in self._items]

    def is_enabled(self, key: str) -> bool:
        return self._buttons[key].isEnabled()

    def set_locked(self, locked: bool) -> None:
        self._locked = locked
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/gui/test_activity_bar.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/gui/widgets/activity_bar.py tests/gui/test_activity_bar.py
git commit -m "feat: ActivityBar (icon-only, tooltip, selected accent bar, lock)"
```

---

### Task 4: StatusBar 控件（TDD）

**Files:**
- Create: `src/lbs_firmware_studio/gui/widgets/status_bar.py`
- Test: `tests/gui/test_status_bar.py`

**Interfaces:**
- Consumes: theme
- Produces: `StatusBar`：`set_connection`/`set_product`/`set_state`/`connection_text`/`state_text`/`state_color`

- [ ] **Step 1: 写失败测试**

`tests/gui/test_status_bar.py`:
```python
from lbs_firmware_studio.gui.widgets.status_bar import StatusBar
from lbs_firmware_studio.gui import theme


def test_default_disconnected(qtbot):
    w = StatusBar(); qtbot.addWidget(w)
    assert "未连接" in w.connection_text()


def test_set_connection(qtbot):
    w = StatusBar(); qtbot.addWidget(w)
    w.set_connection("COM9", 115200)
    txt = w.connection_text()
    assert "COM9" in txt and "115200" in txt


def test_set_connection_none_shows_disconnected(qtbot):
    w = StatusBar(); qtbot.addWidget(w)
    w.set_connection("COM9", 115200)
    w.set_connection(None, None)
    assert "未连接" in w.connection_text()


def test_state_text_and_color(qtbot):
    w = StatusBar(); qtbot.addWidget(w)
    w.set_state("transfering")
    assert "传输" in w.state_text()
    assert w.state_color() == theme.WARNING
    w.set_state("done")
    assert w.state_color() == theme.SUCCESS


def test_set_product(qtbot):
    w = StatusBar(); qtbot.addWidget(w)
    w.set_product("NEW-AI")
    assert "NEW-AI" in w.state_text() or "NEW-AI" in w._product_lbl.text()
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/gui/test_status_bar.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 status_bar.py**

```python
"""VS Code 风格底部状态栏：蓝色条，左连接状态，右产品名+运行状态。"""
from __future__ import annotations
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from .. import theme

_STATE_TEXT = {
    "idle": "空闲", "compiling": "编译中", "connecting": "连接中",
    "entering_upgrade": "进入升级", "reconnecting": "重连中",
    "transfering": "传输中", "done": "完成", "error": "错误",
}


class StatusBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(22)
        self.setStyleSheet(f"background: {theme.STATUSBAR};")
        self._conn = QLabel("○ 未连接")
        self._product_lbl = QLabel("")
        self._state = "idle"
        self._product = ""
        for lbl in (self._conn, self._product_lbl):
            lbl.setStyleSheet(f"color: {theme.TEXT_ON_ACCENT}; font-size: 12px; background: transparent;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.addWidget(self._conn)
        lay.addStretch(1)
        lay.addWidget(self._product_lbl)
        self._refresh_product()

    def set_connection(self, port, baud) -> None:
        if port:
            self._conn.setText(f"● {port} · {baud}")
        else:
            self._conn.setText("○ 未连接")

    def set_product(self, name: str) -> None:
        self._product = name
        self._refresh_product()

    def set_state(self, state: str) -> None:
        self._state = state
        self._refresh_product()

    def _refresh_product(self) -> None:
        st = _STATE_TEXT.get(self._state, self._state)
        self._product_lbl.setText(f"{self._product} · {st}" if self._product else st)

    def connection_text(self) -> str:
        return self._conn.text()

    def state_text(self) -> str:
        return self._product_lbl.text()

    def state_color(self) -> str:
        return theme.state_color(self._state)
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/gui/test_status_bar.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/gui/widgets/status_bar.py tests/gui/test_status_bar.py
git commit -m "feat: bottom StatusBar (connection + product/state)"
```

---

### Task 5: 移除 status_badge 依赖 + 删除该控件

**Files:**
- Modify: `src/lbs_firmware_studio/gui/pages/firmware_page.py`（去掉对 `status_badge._STATE_TEXT` 的 import）
- Delete: `src/lbs_firmware_studio/gui/widgets/status_badge.py`
- Delete: `tests/gui/test_status_badge.py`

**Interfaces:** Produces: firmware_page 不再依赖 status_badge

- [ ] **Step 1: 查 firmware_page 对 status_badge 的引用**

Run: `grep -n "status_badge\|_STATE_TEXT" src/lbs_firmware_studio/gui/pages/firmware_page.py`
Expected: 找到 `from ..widgets.status_badge import _STATE_TEXT`（未使用的 import，之前评审标记过 F401）

- [ ] **Step 2: 删除该 import**

在 firmware_page.py 删除 `from ..widgets.status_badge import _STATE_TEXT` 这一行（它本就未被使用；firmware_page 自带 `_STAGE_TEXT`）。

- [ ] **Step 3: 删除 status_badge 控件与测试**

```bash
rm src/lbs_firmware_studio/gui/widgets/status_badge.py
rm tests/gui/test_status_badge.py
```

- [ ] **Step 4: 确认无其它引用**

Run: `grep -rn "status_badge\|StatusBadge" src/ tests/`
Expected: 无输出（除非 main_window 还引用——若有，Task 7 会一并处理；此处应为空）

- [ ] **Step 5: 跑 firmware_page 测试确认未破坏**

Run: `python -m pytest tests/gui/test_firmware_page.py -v`
Expected: 全部 passed（firmware_page 逻辑未变）

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: remove unused StatusBadge (connection moves to StatusBar)"
```

---

### Task 6: startup_window 单击框选 + 双击进入（TDD）

**Files:**
- Modify: `src/lbs_firmware_studio/gui/startup_window.py`
- Modify: `tests/gui/test_startup_window.py`

**Interfaces:**
- Produces: `product_selected(str)`（双击）、`selection_changed(str)`（单击）、`selected_product()`、`click_product`、`double_click_product`

- [ ] **Step 1: 更新测试**

覆盖 `tests/gui/test_startup_window.py`:
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
    assert w.all_text().count("-AI") >= 3 or all(
        n in w.all_text() for n in ("NEW-AI", "SPARK-AI", "NEXT-AI"))


def test_single_click_selects_not_enter(qtbot):
    w = StartupWindow(_profiles()); qtbot.addWidget(w)
    with qtbot.waitSignal(w.selection_changed, timeout=500) as blocker:
        w.click_product("SPARK-AI")
    assert blocker.args == ["SPARK-AI"]
    assert w.selected_product() == "SPARK-AI"


def test_double_click_enters(qtbot):
    w = StartupWindow(_profiles()); qtbot.addWidget(w)
    with qtbot.waitSignal(w.product_selected, timeout=500) as blocker:
        w.double_click_product("NEXT-AI")
    assert blocker.args == ["NEXT-AI"]
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/gui/test_startup_window.py -v`
Expected: FAIL（selection_changed / selected_product / double_click_product 不存在）

- [ ] **Step 3: 重写 startup_window.py**

```python
"""启动产品选择：单击框选高亮，双击进入。VS Code 深色卡片。"""
from __future__ import annotations
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Signal, Qt
from . import theme

_PROTO_LABEL = {"custom_frame": "自定义帧", "ymodem": "YMODEM"}


class _Card(QFrame):
    clicked = Signal(str)
    double_clicked = Signal(str)

    def __init__(self, name, prof, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self._name = name
        self.setFixedSize(180, 200)
        self._selected = False
        lay = QVBoxLayout(self)
        title = QLabel(name); title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"font-size:16px; font-weight:600; color:{theme.TEXT_PRIMARY}; background:transparent;")
        ports = QLabel(f"{prof.display_ports} 端口"); ports.setAlignment(Qt.AlignCenter)
        ports.setStyleSheet(f"color:{theme.TEXT_SECONDARY}; background:transparent;")
        proto = QLabel(_PROTO_LABEL.get(prof.protocol, prof.protocol)); proto.setAlignment(Qt.AlignCenter)
        proto.setStyleSheet(f"color:{theme.TEXT_SECONDARY}; background:transparent;")
        lay.addStretch(); lay.addWidget(title); lay.addWidget(ports); lay.addWidget(proto); lay.addStretch()
        self._apply()

    def set_selected(self, sel: bool) -> None:
        self._selected = sel; self._apply()

    def _apply(self) -> None:
        border = theme.ACCENT if self._selected else theme.BORDER
        width = 2 if self._selected else 1
        self.setStyleSheet(
            f"QFrame#card {{ background: {theme.BG_SIDEBAR}; border: {width}px solid {border};"
            f" border-radius: 2px; }}")

    def mousePressEvent(self, e):
        self.clicked.emit(self._name); super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        self.double_clicked.emit(self._name); super().mouseDoubleClickEvent(e)


class StartupWindow(QWidget):
    product_selected = Signal(str)     # 双击进入
    selection_changed = Signal(str)    # 单击框选

    def __init__(self, profiles: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LBS Firmware Studio")
        self._cards: dict[str, _Card] = {}
        self._selected: str | None = None
        outer = QVBoxLayout(self)
        t = QLabel("LBS Firmware Studio"); t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet(f"font-size:22px; color:{theme.TEXT_PRIMARY}; background:transparent;")
        sub = QLabel("双击选择要操作的产品"); sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(f"font-size:13px; color:{theme.TEXT_SECONDARY}; background:transparent;")
        outer.addWidget(t); outer.addWidget(sub)
        row = QHBoxLayout(); row.setSpacing(20)
        for name, prof in profiles.items():
            card = _Card(name, prof)
            card.clicked.connect(self._on_click)
            card.double_clicked.connect(self.product_selected.emit)
            self._cards[name] = card
            row.addWidget(card)
        outer.addLayout(row); outer.addStretch()

    def _on_click(self, name: str) -> None:
        self._selected = name
        for k, c in self._cards.items():
            c.set_selected(k == name)
        self.selection_changed.emit(name)

    def selected_product(self):
        return self._selected

    def click_product(self, name: str) -> None:
        self._cards[name].clicked.emit(name)

    def double_click_product(self, name: str) -> None:
        self._cards[name].double_clicked.emit(name)

    def all_text(self) -> str:
        return " ".join(self._cards.keys())
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/gui/test_startup_window.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/gui/startup_window.py tests/gui/test_startup_window.py
git commit -m "feat: startup single-click select + double-click enter (dark cards)"
```

---

### Task 7: main_window 重构（Activity Bar + 顶栏 + StatusBar）（TDD）

**Files:**
- Modify: `src/lbs_firmware_studio/gui/main_window.py`
- Modify: `tests/gui/test_main_window.py`

**Interfaces:**
- Consumes: ActivityBar、StatusBar、PortSelector、页面、DeployWorker（不动）
- Produces: MainWindow 访问器不变；内部用 ActivityBar + StatusBar

- [ ] **Step 1: 更新测试为新布局**

覆盖 `tests/gui/test_main_window.py`:
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
    assert "固件更新" in labels and "脚本下发" in labels and "设置" in labels
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


def test_state_updates_statusbar_and_locks(qtbot, tmp_path):
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w._on_state("transfering")
    assert w.is_busy() is True
    assert "传输" in w.status_bar_text()
    w._on_state("done")
    assert w.is_busy() is False
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/gui/test_main_window.py -v`
Expected: FAIL（status_bar_text 不存在 / 或旧 QListWidget 断言不符）

- [ ] **Step 3: 重构 main_window.py**

关键：`nav_labels/is_nav_enabled/navigate/current_page_name` 改为走 ActivityBar 的 key↔中文标签映射；加顶栏和底部 StatusBar；worker 接线（`_start_firmware`/`_on_state`/`_on_error`/`_on_finished`）保留，`_on_state` 增加驱动 StatusBar + 锁 ActivityBar。

```python
"""主窗口：左 Activity Bar + 顶栏 + 右内容区 + 底部 StatusBar（VS Code 风格）。
固件更新走 DeployWorker(QThread)，信号回主线程。业务接线沿用已修复版本。"""
from __future__ import annotations
from pathlib import Path
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QStackedWidget, QMessageBox)
from PySide6.QtCore import Signal, QThread
from . import theme
from .widgets.activity_bar import ActivityBar
from .widgets.status_bar import StatusBar
from .widgets.port_selector import PortSelector
from .pages.firmware_page import FirmwarePage
from .pages.settings_page import SettingsPage
from .pages.placeholder_page import PlaceholderPage
from .worker import DeployWorker
from ..backend.serial_transport import SerialTransport
from ..backend.deployer import DeviceDeployer

# (key, 中文标签, icon, enabled)
_NAV = [
    ("firmware", "固件更新", "fa5s.download", True),
    ("scripts", "脚本下发", "fa5s.upload", False),
    ("editor", "代码编辑", "fa5s.code", False),
    ("monitor", "数据监控", "fa5s.chart-line", False),
    ("settings", "设置", "fa5s.cog", True),
]
_KEY2LABEL = {k: lbl for k, lbl, _, _ in _NAV}
_LABEL2KEY = {lbl: k for k, lbl, _, _ in _NAV}
_BUSY_STATES = {"compiling", "connecting", "entering_upgrade", "reconnecting", "transfering"}


class MainWindow(QWidget):
    switch_product_requested = Signal()

    def __init__(self, profile, raw_config: dict, config_path: Path, parent=None):
        super().__init__(parent)
        self._profile = profile
        self._raw = raw_config
        self._path = Path(config_path)
        self._busy = False
        self._thread = None
        self._worker = None
        self.setWindowTitle(f"LBS Firmware Studio - {profile.name}")

        # 顶栏
        self._product_lbl = QLabel(f"◆ {profile.name}")
        self._product_lbl.setStyleSheet(f"font-size:14px; font-weight:600; color:{theme.TEXT_PRIMARY}; background:transparent;")
        self._port = PortSelector()
        self._switch_btn = QPushButton("切换产品")
        self._switch_btn.clicked.connect(self.switch_product_requested.emit)
        top = QWidget(); top.setFixedHeight(36); top.setStyleSheet(f"background: {theme.BG_BAR};")
        toplay = QHBoxLayout(top); toplay.setContentsMargins(12, 0, 12, 0)
        toplay.addWidget(self._product_lbl); toplay.addStretch(1)
        toplay.addWidget(self._port); toplay.addWidget(self._switch_btn)

        # Activity Bar + 页面栈
        self._activity = ActivityBar([(k, icon, en) for k, _, icon, en in _NAV])
        self._activity.current_changed.connect(self._on_nav)
        self._stack = QStackedWidget()
        self._pages: dict[str, QWidget] = {}
        for key, label, _icon, _en in _NAV:
            page = self._make_page(key)
            self._pages[key] = page
            self._stack.addWidget(page)

        # 底部状态栏
        self._status = StatusBar()
        self._status.set_product(profile.name)
        self._status.set_state("idle")

        # 组装
        mid = QWidget()
        midlay = QHBoxLayout(mid); midlay.setContentsMargins(0, 0, 0, 0); midlay.setSpacing(0)
        midlay.addWidget(self._activity)
        midlay.addWidget(self._stack, 1)

        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)
        outer.addWidget(top); outer.addWidget(mid, 1); outer.addWidget(self._status)

        # 固件页接线
        self._firmware.set_profile(profile)
        self._firmware.start_requested.connect(self._start_firmware)
        self._activity.set_current("firmware")

    def _make_page(self, key):
        if key == "firmware":
            self._firmware = FirmwarePage(); return self._firmware
        if key == "settings":
            return SettingsPage(self._raw, self._path)
        return PlaceholderPage(_KEY2LABEL[key])

    def _on_nav(self, key: str):
        self._stack.setCurrentWidget(self._pages[key])

    # ---- 固件更新流程（沿用已修复版本）----
    def _start_firmware(self):
        if self._busy or (self._thread is not None and self._thread.isRunning()):
            return
        port = self._port.selected_port()
        if not port:
            QMessageBox.warning(self, "提示", "未选择串口"); return
        self._busy = True
        self._firmware.set_busy(True)
        self._transport = SerialTransport()
        self._deployer = DeviceDeployer(self._transport)
        self._deployer.progress.connect(self._firmware.on_progress)
        self._deployer.state_changed.connect(self._on_state)
        self._deployer.log.connect(self._firmware.on_log)
        self._deployer.error.connect(self._on_error)
        self._thread = QThread()
        self._worker = DeployWorker(self._transport, self._deployer)
        self._worker.set_job(self._profile, port)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run_firmware)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._on_finished)
        self._status.set_connection(port, self._profile.baud)
        self._thread.start()

    def _on_state(self, state: str):
        self._firmware.on_state(state)
        self._status.set_state(state)
        self._busy = state in _BUSY_STATES
        self._firmware.set_busy(self._busy)
        self._port.setEnabled(not self._busy)
        self._switch_btn.setEnabled(not self._busy)
        self._activity.set_locked(self._busy)

    def _on_error(self, msg: str):
        QMessageBox.critical(self, "错误", msg)

    def _on_finished(self):
        self._busy = False
        self._firmware.set_busy(False)
        self._port.setEnabled(True)
        self._switch_btn.setEnabled(True)
        self._activity.set_locked(False)

    # ---- 测试访问器（签名不变）----
    def header_text(self): return self._product_lbl.text()
    def nav_labels(self): return [lbl for _, lbl, _, _ in _NAV]
    def is_nav_enabled(self, label): return self._activity.is_enabled(_LABEL2KEY[label])
    def navigate(self, label): self._activity.set_current(_LABEL2KEY[label])
    def current_page_name(self):
        for key, page in self._pages.items():
            if page is self._stack.currentWidget():
                return _KEY2LABEL[key]
        return ""
    def click_switch_product(self): self._switch_btn.click()
    def is_busy(self): return self._busy
    def status_bar_text(self): return self._status.state_text()
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/gui/test_main_window.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/gui/main_window.py tests/gui/test_main_window.py
git commit -m "feat: rework MainWindow with ActivityBar + top bar + StatusBar"
```

---

### Task 8: log_view 深色级别色微调（TDD）

**Files:**
- Modify: `src/lbs_firmware_studio/gui/widgets/log_view.py`
- Modify: `tests/gui/test_log_view.py`（若断言依赖颜色）

**Interfaces:** Consumes: theme（深色级别色）

- [ ] **Step 1: 查现有 log_view 级别色**

Run: `grep -n "_LEVEL_COLOR\|theme\." src/lbs_firmware_studio/gui/widgets/log_view.py`
Expected: 看到 `_LEVEL_COLOR` 用 theme.TEXT/SUCCESS/ACCENT/ERROR

- [ ] **Step 2: 确认测试仍适用**

Run: `python -m pytest tests/gui/test_log_view.py -v`
Expected: 现有测试（append 显示消息、时间戳、多行）应仍 passed——log_view 只用 theme 常量，Task 2 已把常量改深色，级别色自动变深色。若测试断言了具体旧色值则更新为新常量引用（用 `theme.SUCCESS` 而非硬编码）。

- [ ] **Step 3: 如需微调**

若 `_LEVEL_COLOR` 里 info 用的是 `theme.TEXT`（旧名），改为 `theme.TEXT_PRIMARY`（Task 2 重写后的名字）。确认所有引用的 theme 常量名在新 theme.py 中存在：
```python
_LEVEL_COLOR = {
    "info": theme.TEXT_PRIMARY, "success": theme.SUCCESS,
    "progress": theme.ACCENT, "error": theme.ERROR,
}
```
（注意：Task 2 把 `TEXT` 改名为 `TEXT_PRIMARY`，log_view 若引用旧名 `theme.TEXT` 会 AttributeError——必须改。）

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/gui/test_log_view.py -v`
Expected: 全部 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/gui/widgets/log_view.py tests/gui/test_log_view.py
git commit -m "fix: log_view uses renamed dark theme tokens"
```

---

### Task 9: 集成收尾 —— firmware_page 深色 + 全量按文件验证 + 手动启动

**Files:**
- Modify: `src/lbs_firmware_studio/gui/pages/firmware_page.py`（若引用旧 theme 常量名）
- 验证全部

**Interfaces:** 无新接口；收尾

- [ ] **Step 1: 扫描所有对旧 theme 常量名的引用**

Run: `grep -rn "theme\.BG\b\|theme\.TEXT\b\|theme\.PANEL\|theme\.MUTED\|theme\.AMBER" src/lbs_firmware_studio/gui/`
Expected: 列出所有引用旧常量名（BG/TEXT/PANEL/MUTED/AMBER 等 Task 2 之前的名字）的地方。

- [ ] **Step 2: 逐个改为新常量名**

把找到的旧名改为新名：`theme.BG`→`theme.BG_EDITOR`、`theme.PANEL`→`theme.BG_SIDEBAR`、`theme.TEXT`→`theme.TEXT_PRIMARY`、`theme.MUTED`→`theme.TEXT_SECONDARY`、`theme.AMBER`→`theme.WARNING`。确保每个被引用的常量在新 theme.py 存在。

- [ ] **Step 3: 冒烟导入所有 GUI 模块**

Run: `python -c "from lbs_firmware_studio.gui import app, main_window, startup_window, theme; from lbs_firmware_studio.gui.widgets import activity_bar, status_bar, port_selector, log_view; from lbs_firmware_studio.gui.pages import firmware_page, settings_page, placeholder_page; print('all import ok')"`
Expected: `all import ok`（无 AttributeError/ImportError——证明没有残留的旧常量名/已删控件引用）

- [ ] **Step 4: 按文件跑全部 GUI 测试（容忍多线程 teardown 段错误）**

分文件跑，逐个确认 passed（避免同进程多 QThread teardown 段错误）：
```bash
for f in theme activity_bar status_bar startup_window main_window firmware_page settings_page port_selector log_view placeholder_page; do
  echo "=== $f ==="; python -m pytest tests/gui/test_$f.py -q 2>&1 | tail -2
done
```
Expected: 每个文件都 `passed`（个别文件末尾可能因 QThread teardown 打印段错误，但断言全过即可）。

- [ ] **Step 5: 跑后端测试确认零影响**

Run: `python -m pytest tests/ --ignore=tests/gui -q`
Expected: 全部 passed（后端未动，应与之前一致）

- [ ] **Step 6: 手动启动验证（非自动化）**

Run: `python -m lbs_firmware_studio.gui.app`
Expected（人工确认）：深色 VS Code 观感；启动界面双击产品进入、单击框选；主窗左侧图标竖条（悬停出名称、设置沉底）；顶栏产品名+串口+切换；底部蓝色状态栏显示连接/状态；切固件更新页正常。

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "fix: migrate remaining refs to dark theme tokens; integration polish"
```

---

## Self-Review 记录

- **Spec 覆盖**：深色令牌(T2)、深色 QSS(T2)、ActivityBar 图标/tooltip/选中亮条/禁用/锁定(T3)、底部 StatusBar 连接+状态(T4)、status_badge 弃用(T5)、startup 双击+框选(T6)、main_window 重构 ActivityBar+顶栏+StatusBar(T7)、log_view 深色(T8)、页面深色适配+收尾(T9)、qtawesome 依赖(T1) —— 均有任务。系统明暗跟随明确不做(spec §8)。
- **占位扫描**：无 TBD；每步含完整代码或确切命令。图标名用了具体 fa5s.* 值（非占位）。
- **类型/命名一致性**：theme 新常量名(BG_EDITOR/TEXT_PRIMARY/WARNING 等)在 T2 定义，T7/T8/T9 一致引用；**关键风险**：旧 theme 常量名(BG/TEXT/PANEL/MUTED/AMBER)被现有页面/控件引用，T2 改名后会 AttributeError——T8/T9 专门扫描并迁移(grep + 冒烟导入)。ActivityBar 的 key↔中文标签映射(_KEY2LABEL/_LABEL2KEY)在 T7 保证 MainWindow 访问器 nav_labels/is_nav_enabled/navigate 用中文标签对外、内部用 key。MainWindow 访问器签名与既有测试一致(header_text/nav_labels/is_nav_enabled/navigate/current_page_name/click_switch_product/is_busy)，新增 status_bar_text。
- **已知风险**：qtawesome 图标名(fa5s.*)需真实存在——T1 Step3 冒烟验证 fa5s.download 可用；其余图标同族。QSS 观感需 T9 手动确认微调。多 QThread teardown 段错误按文件跑规避(T9 Step4)。
