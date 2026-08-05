# 阶段2 前端重构 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 去掉独立产品选择页面，改为顶栏 ProductSelector（下拉+卡片视觉）窗内切换；按新设计令牌全面翻新 GUI 视觉；清理 startup/placeholder 遗留。

**Architecture:** 分层不变（GUI 不碰协议/串口/BLE）。改动集中在 `src/lbs_firmware_studio/gui/`：`theme.py` 令牌演进 → 新增 `widgets/product_selector.py` → `app.py` 简化（删 StartupWindow 流转）→ `main_window.py` 集成选择器与窗内切换 → 各页面/组件按令牌翻新。测试同步更新（设计文档 §7 已枚举影响面）。

**Tech Stack:** Python 3.13 / PySide6 6.11 / qtawesome（fa5s.* 图标族）/ pytest-qt

## Global Constraints

- 设计唯一来源：`docs/superpowers/designs/2026-08-04-ui-refactor-design.md`（令牌表 §3、布局/组件规格 §4、页面线框 §5、测试影响 §7、附录 A 迁移映射）。
- 已定决策（2026-08-05 用户）：①监控页移除本页 PortSelector 统一顶栏连接；②切换产品 baud 一致保持链路+自动重启监控，否则断开提示；③编辑页浮动按钮保留浮动；④状态栏保留 #007ACC 蓝。
- 深色主题不硬编码色值，全部走 `theme.*` 令牌；图标统一 qta `fa5s.*`，禁止文本符号当图标。
- GUI 层不碰协议/串口/BLE；设备操作仍经 worker → deployer。
- 测试访问器签名（`header_text()`/`nav_labels()`/`current_page_name()`/`status_bar_text()`/`is_busy()` 等）尽量保持，减少测试破坏面（§6.2 兼容表）。
- 测试命令 `python -m pytest`；GUI 测试按文件单独跑（pytest-qt 退出段错误 -1073740791 为已知环境坑，`doc/pitfalls.md:23-26`，全量收尾容忍）。
- 提交到 `main-work`，完成后合并回 `main` 并推送。

---

### Task 1: theme.py 设计令牌演进

**Files:**
- Modify: `src/lbs_firmware_studio/gui/theme.py`
- Test: `tests/gui/test_theme.py`

**Interfaces:**
- Consumes: 设计文档 §3.1-3.5 令牌表 + 附录 A 迁移映射。
- Produces: 新令牌常量（颜色/字号/间距/圆角/图标）、`STAGE_TEXT` 唯一化、`app_qss()` 补 QScrollBar/QMenu/QMessageBox 深色样式、`WEIGHT_*` 字重常量。

- [ ] **Step 1: 写失败测试**

更新 `tests/gui/test_theme.py`：
- `test_dark_colors_defined`：旧 hex 断言改为新值（`BG_BAR=#2D2D30`、`TEXT_PRIMARY=#E0E0E0`、`TEXT_SECONDARY=#A8A8A8`、`TEXT_DISABLED=#7A7A7A`、`BORDER=#45454A`、`BG_HOVER=#37373D`、`WARNING=#D7BA3F`、`ICON_IDLE=#9BA3AF`、`ICON_DISABLED=#5A5A5E`、`ACCENT_HOVER=#1A8AD4`；不变项 `BG_EDITOR=#1E1E1E`/`BG_SIDEBAR=#252526`/`BG_INPUT=#3C3C3C`/`BG_SELECTED=#094771`/`STATUSBAR=#007ACC`/`TEXT_ON_ACCENT=#FFFFFF`/`ACCENT=#007ACC`/`SUCCESS=#4EC9B0`/`ERROR=#F14C4C`）。
- `test_state_color_dark_mapping`：WARNING 断言 `#CCA700` → `#D7BA3F`（SUCCESS/ERROR 不变）。
- 新增 `test_new_tokens_defined`：断言新令牌存在（`ACCENT_FOCUS`/`BG_RAISED`/`BG_SUBTLE`/`TEXT_COMMENT`/`BORDER_STRONG`/`ICON_HOVER`/`PRODUCT_GREEN == SUCCESS`/`RADIUS_FULL`/`RADIUS_PANEL`/`SPACE_XXL`/`ICON_XS..XL`/`WEIGHT_*`/`SUCCESS_BG`/`WARNING_BG`/`ERROR_BG`/`STATUSBAR_ON`）。
- 新增 `test_stage_text_single_source`：断言 `status_bar` 无独立 `_STATE_TEXT`（或 theme.STAGE_TEXT 覆盖状态栏用词，见 §3.6 表）。

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/gui/test_theme.py -v` → FAIL（旧断言命中旧值/新令牌不存在）。

- [ ] **Step 3: 实现**

按设计文档 §3.1-3.5 + 附录 A 更新 `theme.py` 全部令牌值并新增令牌；`PRODUCT_GREEN = SUCCESS`（引用）；新增 `STAGE_TEXT` 统一文案（§3.6 表：idle=就绪/compiling=编译中/connecting=连接中/entering_upgrade=进入升级模式/reconnecting=等待设备重连/transfering=传输中/done=完成/error=出错）；`app_qss()` 补 QScrollBar/QMenu/QMessageBox 深色样式与 `ACCENT_FOCUS` 焦点环（§2 走查 A1/E3）；新增 `WEIGHT_REGULAR/MEDIUM/BOLD`。

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/gui/test_theme.py -v` → PASS。
Run: `python -m pytest tests/gui/test_status_bar.py tests/gui/test_activity_bar.py -v` → PASS（若 STAGE_TEXT 改动波及 status_bar 断言则本步先跑；若 Test 6 才删 `_STATE_TEXT` 则此处只验证 theme 自身）。

- [ ] **Step 5: 提交**

```bash
git add src/lbs_firmware_studio/gui/theme.py tests/gui/test_theme.py
git commit -m "style(theme): 设计令牌演进（新色/圆角/图标令牌 + STAGE_TEXT 唯一化 + 控件深色样式）"
```

---

### Task 2: ProductSelector 组件（核心新增）

**Files:**
- Create: `src/lbs_firmware_studio/gui/widgets/product_selector.py`
- Test: `tests/gui/test_product_selector.py`（新建）

**Interfaces:**
- Consumes: 设计文档 §4.2 组件规格（结构/交互/尺寸/建议接口）。
- Produces: `ProductSelector(QWidget)`，接口：
```python
class ProductSelector(QWidget):
    product_changed = Signal(str)
    def __init__(self, profiles: dict, current: str, parent=None): ...
    def current_product(self) -> str: ...
    def product_names(self) -> list[str]: ...
    def select_product(self, name: str) -> bool: ...
    def trigger_button(self) -> QPushButton: ...
    def is_popup_open(self) -> bool: ...
    def set_locked(self, locked: bool) -> None: ...
```

- [ ] **Step 1: 写失败测试**

新建 `tests/gui/test_product_selector.py`（qtbot）：
- `test_init_shows_current_product`：current="NEW-AI" 时触发器文本含 "NEW-AI"；`current_product()=="NEW-AI"`。
- `test_click_trigger_opens_popup`：`trigger_button().click()` → `is_popup_open()` True；再次点击/Esc → False。
- `test_select_product_emits_and_closes`：点产品项（如 "SPARK-AI"）→ `product_changed` 发出且 name 正确、弹层关闭、`current_product()=="SPARK-AI"`。
- `test_current_item_highlighted`：列表当前项有 `BG_SELECTED` 背景（断言 item 的 QSS/属性或 `selected` 状态）。
- `test_programmatic_select`：`select_product("NEXT-AI")` 返回 True 且 current 更新；不存在名字返回 False。
- `test_set_locked_disables_trigger`：`set_locked(True)` → 触发器 `isEnabled()` False；弹层若开着被关闭。
- `test_keyboard_navigation`：弹层打开后 ↓ 键移动选择、Enter 确认发出信号。

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/gui/test_product_selector.py -v` → FAIL（ModuleNotFoundError: product_selector）。

- [ ] **Step 3: 实现**

按设计文档 §4.2 实现 `widgets/product_selector.py`：
- 触发器 `QPushButton#product-trigger`（16px 产品图标 `fa5s.microchip` + 产品名 + chevron `fa5s.chevron-down`；最小宽 168px 高 30px；`ACCENT_FOCUS` 焦点环）。
- 弹层 `QFrame#popup`（`BG_RAISED` + 1px `BORDER` + `RADIUS_PANEL`，宽 220px）+ `QListWidget`（无边框、行高 36px、最多 6 行可见；每项 = 16px 图标 + 产品名；当前项 `BG_SELECTED` 底 + 左侧 3px `ACCENT` 条 + 右侧 `fa5s.check`（`SUCCESS` 色）+ 产品名 `PRODUCT_GREEN`，其它项 `TEXT_PRIMARY`）。
- 交互：点击触发器展开/收起、Esc/点击外部关闭、单击即选并 emit、QListWidget 原生键盘导航、`set_locked` 禁用触发器并强制关弹层、空列表显示「无可用产品」禁用态。
- 弹层实现建议 `QFrame` 作为 child popup 用 `Qt.Popup` 或覆盖式定位（以 qtbot 测试可断言为准）；若用原生 `QMenu` 替代也可（测试接口不变）。

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/gui/test_product_selector.py -v` → PASS。

- [ ] **Step 5: 提交**

```bash
git add src/lbs_firmware_studio/gui/widgets/product_selector.py tests/gui/test_product_selector.py
git commit -m "feat(ui): ProductSelector 顶栏产品选择器（下拉+卡片视觉）"
```

---

### Task 3: AppController 简化 + 删除 StartupWindow/PlaceholderPage

**Files:**
- Modify: `src/lbs_firmware_studio/gui/app.py`
- Delete: `src/lbs_firmware_studio/gui/startup_window.py`、`src/lbs_firmware_studio/gui/pages/placeholder_page.py`
- Test: `tests/gui/test_app_smoke.py`（重写）、`tests/gui/test_startup_window.py`（删除）、`tests/gui/test_placeholder_page.py`（删除）

**Interfaces:**
- Consumes: Task 2 的 ProductSelector。
- Produces: `AppController.launch()` 直入主窗（默认产品 NEW-AI）；删除 startup 流转与 placeholder 页。

- [ ] **Step 1: 写失败测试**

- 删除 `tests/gui/test_startup_window.py`、`tests/gui/test_placeholder_page.py`。
- 重写 `tests/gui/test_app_smoke.py`：`AppController(profiles, raw, path).launch()` → `current_window_kind()` 返回 `"main"`（或新语义 `is_main_open()`）；MainWindow 存在且 `header_text()` 为默认产品名；无 startup 态可切。

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/gui/test_app_smoke.py -v` → FAIL（launch 不存在/流转语义不符）。

- [ ] **Step 3: 实现**

- `app.py`：`AppController` 简化——构造接收全部 profiles；`launch()`（或保留 `main()` 内直接建主窗）创建 `MainWindow`（首参为全部 profiles 或默认产品，见 Task 4 接口）；删除 `show_startup`/`on_product_selected`/`on_switch_product`/`current_window_kind`（或其保留为测试兼容的薄包装，以 §6.2 兼容表为准）；启动默认产品 NEW-AI。
- 删除 `startup_window.py`、`placeholder_page.py`（先确认无其他引用：grep `startup_window|StartupWindow|placeholder_page|PlaceholderPage`）。
- `main_window.py` 的 `_make_page` 删除 placeholder 死分支（`return PlaceholderPage(...)` 去掉；`_NAV` 无未覆盖 key 时该分支不可达）。

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/gui/test_app_smoke.py -v` → PASS。
Run: `python -m pytest tests/gui/test_main_window.py tests/gui/test_main_window_buttons.py tests/gui/test_main_window_ble_gate.py -v` → PASS（若 Task 4 未完成导致构造签名变化，此处可推迟到 Task 4 后跑；Task 顺序上 Task 3/4 同批验证）。

- [ ] **Step 5: 提交**

```bash
git add -A src/lbs_firmware_studio/gui tests/gui
git commit -m "refactor(ui): 删除产品选择页/占位页，AppController 直入主窗"
```

---

### Task 4: MainWindow 集成 ProductSelector + 窗内产品切换

**Files:**
- Modify: `src/lbs_firmware_studio/gui/main_window.py`
- Modify: `src/lbs_firmware_studio/gui/widgets/status_bar.py`（仅产品名去除部分可在此或 Task 6 做，若测试耦合则同步）
- Test: `tests/gui/test_main_window.py`（更新+新增）

**Interfaces:**
- Consumes: Task 1 令牌、Task 2 ProductSelector、Task 3 AppController 简化。
- Produces: `MainWindow(profiles: dict, current: str, raw_config, config_path)`（或 `MainWindow(profile, raw, path)` + `set_profiles(profiles)` 二选一，以测试兼容最小为准）；`switch_product_requested` 信号删除，改 `_on_product_change(name)` 窗内重建；`header_text()` 返回 `self._product_selector.current_product()`。

- [ ] **Step 1: 写失败测试**

更新 `tests/gui/test_main_window.py`：
- `test_switch_product_button_emits` → 改为 `test_product_switch_rebuilds_pages`：`header_text()` 为当前产品；`selector.select_product("SPARK-AI")` 后 `header_text()=="SPARK-AI"`、`current_page_name()` 回到默认页、监控/固件页重新接线。
- 新增 `test_switch_blocked_when_busy`：置 `_busy=True`（或经状态）后 `select_product` 失败、产品名不变。
- 新增 `test_switch_baud_same_keeps_link`（决策点 2）：连接建立（baud=新产品一致）后切换 → 链路保持、监控自动重启（以现有 `_conn`/`_monitor` 测试模式实现；若过于复杂可降级为断言 `_on_product_change` 不调用 disconnect）。
- 保留 `header_text/nav_labels/is_nav_enabled/navigate/current_page_name/click_switch_product/is_busy/status_bar_text` 既有断言（签名不变项）。

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/gui/test_main_window.py -v` → FAIL。

- [ ] **Step 3: 实现**

按设计文档 §4.1/§4.2「MainWindow 集成」：
- 顶栏改 48px（`BG_BAR`）；左 = `ProductSelector(profiles, current)` + 与连接区之间 1px `BORDER` 竖分隔线（`QFrame.VLine`）；`addStretch`；右 = `ConnectionSelector`。
- `_on_product_change(name)`：`_busy` 守卫（回滚选择）；停监控；重建页面栈（`_make_page` 去死分支后重建 Firmware/Monitor/Editor 页并重接全部信号：`start_requested`/`deploy_requested`/`host_state_changed`/`run_toggle_requested`/`connection_changed`/`target_changed`）；`set_profile`/`set_port_getter`/`set_baud_getter`；状态栏阶段重置「就绪」；连接处理：新产品 baud 与当前链路一致 → 保持链路+自动重启监控，否则断开+提示「产品波特率变化，请重新连接」。
- `header_text()` → `self._product_selector.current_product()`；`switch_product_requested` 信号删除（或保留为兼容别名）。
- 删除 `_switch_btn` 切换按钮（被 ProductSelector 取代）。

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/gui/test_main_window.py tests/gui/test_main_window_buttons.py tests/gui/test_main_window_ble_gate.py tests/gui/test_app_smoke.py -v` → PASS。

- [ ] **Step 5: 提交**

```bash
git add src/lbs_firmware_studio/gui/main_window.py tests/gui/test_main_window.py
git commit -m "feat(ui): MainWindow 集成 ProductSelector，窗内重建切换产品"
```

---

### Task 5: 监控页移除本页 PortSelector + 提示条

**Files:**
- Modify: `src/lbs_firmware_studio/gui/pages/monitor_page.py`
- Test: `tests/gui/test_monitor_page.py`

**Interfaces:**
- Consumes: 设计文档 §6.3 决策点 1（已定：移除）+ §4.4 右栏线框。
- Produces: MonitorPage 仅依赖顶栏连接（`set_transport_getter`）；移除 `_port`/`_port_lbl`/`_sync_conn_ui` 双入口；新增 `SUCCESS_BG` 提示条「使用顶栏连接」。

- [ ] **Step 1: 写失败测试**

- `tests/gui/test_monitor_page.py` 中引用 `_port` 的用例改为断言提示条存在（`has_connection_hint()` 或直接断言含「使用顶栏连接」文本）。
- 保留 `card_count/card_at/has_sensor_update_button/latest_frame/field_text` 断言不变。
- 新增 `test_connection_hint_shown`：页初始化即显示提示条。

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/gui/test_monitor_page.py -v` → FAIL（`_port` 引用报错/提示条缺失）。

- [ ] **Step 3: 实现**

`monitor_page.py`：删除本页 PortSelector 相关（`_port`/`_port_lbl`/`_sync_conn_ui` 及未连接回退逻辑）；页顶加 `SUCCESS_BG` 提示条（`QFrame`+图标 `fa5s.link`+文案「使用顶栏连接」）；`set_transport_getter` 行为保持（复用顶栏持久链路）；`_start_btn` 死控件移除（§2 走查 B6）。

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/gui/test_monitor_page.py -v` → PASS。
Run: `python -m pytest tests/gui/test_main_window.py -v` → PASS（联动）。

- [ ] **Step 5: 提交**

```bash
git add src/lbs_firmware_studio/gui/pages/monitor_page.py tests/gui/test_monitor_page.py
git commit -m "feat(ui): 监控页移除本页端口选择，统一顶栏连接（提示条）"
```

---

### Task 6: 状态栏 + 连接选择器微调

**Files:**
- Modify: `src/lbs_firmware_studio/gui/widgets/status_bar.py`
- Modify: `src/lbs_firmware_studio/gui/widgets/connection_selector.py`
- Test: `tests/gui/test_status_bar.py`、`tests/gui/test_connection_selector.py`、`tests/gui/test_connection_selector_signals.py`

**Interfaces:**
- Consumes: Task 1 STAGE_TEXT + STATUSBAR_ON 令牌。
- Produces: 状态栏去产品名、`STATUSBAR_ON` 前景组、阶段文案用 `theme.STAGE_TEXT`；连接选择器适配 48px 顶栏、indicator 16px、`_RADIO_QSS` 收敛进 `app_qss()`、扫描中占位禁用、状态点矢量图标。

- [ ] **Step 1: 写失败测试**

- `tests/gui/test_status_bar.py`：`test_set_product`/`test_state_text_and_color` 中产品名断言移除；`state_text` 只含阶段文案；新增 `test_statusbar_on_colors`（STATUSBAR_ON 组存在且用在新前景）。
- `tests/gui/test_connection_selector*.py`：既有接口断言保留（`selected_kind/selected_target/set_kind/scan_ble/make_transport`）；新增/调整：占位项「扫描中...」`isEnabled()` False；indicator 尺寸变化不影响断言。

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/gui/test_status_bar.py tests/gui/test_connection_selector.py tests/gui/test_connection_selector_signals.py -v` → FAIL。

- [ ] **Step 3: 实现**

- `status_bar.py`：删除 `set_product`/`_product_lbl`（或改存内部字段不影响显示）；删除 `_STATE_TEXT` 改用 `theme.STAGE_TEXT`；前景改 `STATUSBAR_ON` 组；状态色点矢量图标（`fa5s.circle` 等）。
- `connection_selector.py`：控件尺寸适配 48px 顶栏；indicator 升 16px；`_RADIO_QSS` 收进 `theme.app_qss()`（删局部 QSS）；「扫描中...」占位项 `setEnabled(False)`；状态点改矢量图标；颜色全走新令牌。

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/gui/test_status_bar.py tests/gui/test_connection_selector.py tests/gui/test_connection_selector_signals.py -v` → PASS。
Run: `python -m pytest tests/gui/test_main_window.py tests/gui/test_main_window_buttons.py -v` → PASS（联动）。

- [ ] **Step 5: 提交**

```bash
git add src/lbs_firmware_studio/gui/widgets/status_bar.py src/lbs_firmware_studio/gui/widgets/connection_selector.py tests/gui/test_status_bar.py tests/gui/test_connection_selector*.py
git commit -m "style(ui): 状态栏去产品名/统一阶段文案 + 连接选择器顶栏适配"
```

---

### Task 7: 固件页视觉翻新

**Files:**
- Modify: `src/lbs_firmware_studio/gui/pages/firmware_page.py`
- Test: `tests/gui/test_firmware_page.py`

**Interfaces:**
- Consumes: 设计文档 §4.4 左栏线框。
- Produces: 主色「开始固件更新」按钮（宽度限 180px + 二次确认框 `confirm_start`）、阶段 chip（色点+`STAGE_TEXT`）、进度条 `setFormat(f"{pct}%")`、日志行数裁剪、全部新令牌。

- [ ] **Step 1: 写失败测试**

- 保留 `start_button/summary_text/firmware_dir_text/progress_value/stage_text/log_text` 访问器断言。
- 新增 `test_confirm_start_required`：点击开始先弹确认（monkeypatch `QMessageBox.question` 返回 No → 不触发 `start_requested`；返回 Yes → 触发）。
- 新增 `test_progress_format_shows_percent`：`progress_value` 不变 + 进度条 `format()` 含 `%`。
- 若实现 `confirm_start()` 直通方法供测试：`test_confirm_start_direct`。

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/gui/test_firmware_page.py -v` → FAIL。

- [ ] **Step 3: 实现**

按 §4.4 左栏：按钮改主色（`ACCENT`）+ 图标 `fa5s.download`（`ICON_MD`）+ 宽度 180px + 点击二次确认（`QMessageBox.question`，No 则不发）；阶段 chip（色点 `state_color` 矢量图标 + `STAGE_TEXT` 文案，`_stage` 文字随状态变色）；进度条 `setFormat(f"{pct}%")`；LogView 行数裁剪（`LogView` 增加上限，见走查 E6）；颜色全部走新令牌。

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/gui/test_firmware_page.py -v` → PASS。
Run: `python -m pytest tests/gui/test_main_window_buttons.py tests/gui/test_worker.py -v` → PASS（联动：确认框是否影响 worker 触发的 start 路径——若 `_start_firmware` 是 MainWindow 内联确认，确认框加在 MainWindow 而非 FirmwarePage，则本任务只在页内加视觉，确认逻辑见 Task 4 的 `_on_product_change` 无关；以实际接线为准，避免双重确认）。

- [ ] **Step 5: 提交**

```bash
git add src/lbs_firmware_studio/gui/pages/firmware_page.py tests/gui/test_firmware_page.py
git commit -m "style(ui): 固件页主色按钮/确认框/阶段chip/进度格式/日志裁剪"
```

---

### Task 8: 代码编辑页视觉翻新

**Files:**
- Modify: `src/lbs_firmware_studio/gui/pages/script_editor_page.py`
- Modify: `src/lbs_firmware_studio/gui/widgets/code_editor.py`（注释色 TEXT_COMMENT，如需）
- Test: `tests/gui/test_script_editor_page.py`

**Interfaces:**
- Consumes: 设计文档 §4.4 编辑页 + 决策点 3（保留浮动）。
- Produces: dirty 高亮改 `setProperty+repolish`（根治 A2）、浮动按钮保留但规范间距/圆角/顺序（`RADIUS_FULL`）、运行/暂停按钮图标与色板、注释色 `TEXT_COMMENT`。

- [ ] **Step 1: 写失败测试**

- 保留既有断言（含 `test_run_pause_buttons_are_children_of_editor`：`parent() is page._editor`）。
- 新增 `test_dirty_highlight_via_property`：`_save_btn` 的 property（如 `dirty`）随编辑状态切换（`setProperty` 后断言 `property("dirty")` 值，而非仅 QSS 字符串）。
- 新增 `test_float_buttons_radius_token`：浮动按钮样式含 `RADIUS_FULL`（或等价断言）。

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/gui/test_script_editor_page.py -v` → FAIL（dirty 断言新写法不通过）。

- [ ] **Step 3: 实现**

- dirty 高亮：删除全局 QSS 覆盖（`#save_btn[dirty=true]` 类规则移入 theme.app_qss 或组件内），改 `setProperty("dirty", v)` + `style().unpolish/polish` 刷新。
- 浮动按钮：保留父控件 `_editor`；规范间距/圆角（`RADIUS_FULL`=16）/顺序；按钮图标/颜色走新令牌（`SUCCESS` 运行、`WARNING` 暂停）。
- `code_editor.py`：注释高亮色改 `TEXT_COMMENT`（如现有高亮表有注释色）。

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/gui/test_script_editor_page.py tests/gui/test_code_editor.py -v` → PASS。
Run: `python -m pytest tests/gui/test_main_window.py tests/gui/test_main_window_buttons.py -v` → PASS（联动）。

- [ ] **Step 5: 提交**

```bash
git add src/lbs_firmware_studio/gui/pages/script_editor_page.py src/lbs_firmware_studio/gui/widgets/code_editor.py tests/gui/test_script_editor_page.py
git commit -m "style(ui): 编辑页 dirty 高亮 property 化 + 浮动按钮规范化 + 注释色令牌"
```

---

### Task 9: 设置页/传感器卡片/日志/主机状态栏样式收尾

**Files:**
- Modify: `src/lbs_firmware_studio/gui/pages/settings_page.py`
- Modify: `src/lbs_firmware_studio/gui/widgets/sensor_card.py`、`src/lbs_firmware_studio/gui/widgets/log_view.py`、`src/lbs_firmware_studio/gui/widgets/host_status_bar.py`、`src/lbs_firmware_studio/gui/widgets/activity_bar.py`（focus 环）、`src/lbs_firmware_studio/gui/dialogs/sensor_update_dialog.py`
- Test: `tests/gui/test_settings_page.py`、`tests/gui/test_sensor_card.py`、`tests/gui/test_log_view.py`、`tests/gui/test_host_status_bar.py`、`tests/gui/test_activity_bar.py`、`tests/gui/test_sensor_update_dialog.py`

**Interfaces:**
- Consumes: Task 1 令牌 + 设计文档 §4.4/§2 走查项。
- Produces: 上述组件样式全部走新令牌；SensorCard 空态「无设备」提示；LogView 行数裁剪上限；ActivityBar 焦点环。

- [ ] **Step 1: 写失败测试**

- 各既有访问器断言保留（§7 均 ○ 或 ★ 少量）。
- `test_sensor_card.py` 新增：空态含「无设备」提示断言。
- `test_log_view.py` 新增：append 超上限行后 `plain_text` 行数被裁剪。
- `test_activity_bar.py` 新增：focus 样式不影响 `icon_color` 既有断言（可只跑既有）。

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/gui/test_sensor_card.py tests/gui/test_log_view.py -v` → FAIL（新增断言）。

- [ ] **Step 3: 实现**

- `sensor_card.py`：空态显示「无设备」提示（`TEXT_SECONDARY`）；行内刷新时间戳字段（视觉）。
- `log_view.py`：行数裁剪上限（如 500 行，超出丢弃最旧）。
- `host_status_bar.py`：等宽字体/滚动样式、字段颜色走令牌。
- `activity_bar.py`：新增 focus 环（`ACCENT_FOCUS`）样式（不影响既有断言）。
- `settings_page.py`/`sensor_update_dialog.py`：布局与颜色全走新令牌（页面统一 margins `SPACE_LG`/spacing `SPACE_MD`）。

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/gui/test_settings_page.py tests/gui/test_sensor_card.py tests/gui/test_log_view.py tests/gui/test_host_status_bar.py tests/gui/test_activity_bar.py tests/gui/test_sensor_update_dialog.py -v` → PASS。

- [ ] **Step 5: 提交**

```bash
git add src/lbs_firmware_studio/gui tests/gui
git commit -m "style(ui): 设置页/传感器卡片/日志/主机状态栏/ActivityBar 令牌化收尾"
```

---

### Task 10: 全量回归与收尾

**Files:**
- Test: `tests/`（全量，GUI 按文件单独跑）

**Interfaces:**
- Consumes: Task 1-9 全部改动。
- Produces: 阶段 2 完成结论：全部测试绿（段错误容忍）、无遗留改动。

- [ ] **Step 1: 非 GUI 全量**

Run: `python -m pytest tests/ -q --ignore=tests/gui`
Expected: PASS。

- [ ] **Step 2: GUI 按文件逐一跑**

Run: `Get-ChildItem tests/gui/test_*.py | ForEach-Object { python -m pytest $_.FullName -q }`
Expected: 每文件 PASS（容忍个别文件收尾段错误 -1073740791，以断言结果为准）。

- [ ] **Step 3: 检查无遗留**

- grep 确认 `startup_window|StartupWindow|placeholder_page|PlaceholderPage|_STATE_TEXT` 无引用残留；
- grep 确认 gui/ 无硬编码色值（`#1E1E1E` 等旧值除 theme.py 外不出现）。

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -m "test(ui): 阶段2 全量回归收尾"  # 若无可提交改动则跳过
```

---

### Task 11: 最终审查、推送与合并

**Files:**
- Git: 分支操作

- [ ] **Step 1: 生成分支审查包并派最终 reviewer**（同阶段 1 流程：`git merge-base main HEAD` 起全分支 diff，最终整体审查 Ready to merge 才合并）。
- [ ] **Step 2: 推送 main-work**

```bash
git push origin main-work
```

- [ ] **Step 3: 合并回 main 并推送**

```bash
git checkout main
git merge main-work
git push origin main
git checkout main-work
```

---

## Self-Review 结论（对照设计文档）

- **Spec 覆盖**：设计文档 §3 令牌 → Task 1；§4.2 ProductSelector → Task 2；§4.1/4.2 MainWindow 集成 + 决策点 2 → Task 4；决策点 1 → Task 5；§4.3 连接选择器 + §3.6 文案 + 决策点 4 → Task 6；§4.4 左栏 → Task 7；§4.4 编辑页 + 决策点 3 → Task 8；§4.4 设置/卡片/日志/状态栏 + 走查项 → Task 9；§7 测试影响（◆ 删 3 文件、★ 微调、＋ 新增）→ Task 2/3/4/5/6/7/8/9；收尾合并 → Task 10/11。结构重构（删 startup/placeholder/死分支）→ Task 3/4。
- **占位符扫描**：无 TBD/TODO；实现要点均指向设计文档具体章节 + 既有代码结构，GUI 视觉任务以"读现有代码 + 按设计实现"为粒度（与阶段 1 审查类任务一致）。
- **类型一致性**：ProductSelector 接口（Task 2 产出）被 Task 4 消费，签名一致；`header_text()` 语义保留；MainWindow 构造参数变更在 Task 3/4 内闭环，测试同步。
