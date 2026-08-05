# 布局重构 v2 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 顶栏只显示主机状态；产品选择/连接/传感器更新全部收进侧边栏点击弹浮窗；固件页去日志+单行进度；监控页移走主机信息与传感器按钮。

**Architecture:** 改动集中在 gui/。新组件 `widgets/connection_popup.py`（设备浮窗）；ActivityBar 支持「浮窗触发」图标（device/sensor 点击发专用信号而非切页）；MainWindow 顶栏换 HostStatusBar、挂接浮窗与传感器对话框；固件页/监控页按需裁剪。

**Tech Stack:** PySide6 / qtawesome / pytest-qt

## Global Constraints
- 深色主题不硬编码色值（theme.* 令牌）；图标 qta fa5s.*。
- GUI 层不碰协议/串口/BLE；设备操作仍经 worker → deployer。
- 测试访问器签名尽量保持（header_text/nav_labels/current_page_name/is_busy/status_bar_text 等，§语义保持）。
- GUI 测试按文件单独跑（pytest-qt 退出段错误环境坑）；提交到 main-work，完成后合并回 main 并推送。

---

### Task 1: ActivityBar 扩展（浮窗触发图标）

**Files:**
- Modify: `src/lbs_firmware_studio/gui/widgets/activity_bar.py`
- Test: `tests/gui/test_activity_bar.py`

**Interfaces:**
- Consumes: 现有 `ActivityBar(items)`（key, icon, enabled）+ `current_changed` 信号。
- Produces: 新增 `action_triggered = Signal(str)`（浮窗类图标专用，key ∈ {"device","sensor"}）；`set_action_keys(keys)` 或构造参数区分「切页图标」与「浮窗图标」——浮窗图标点击只发 `action_triggered(key)` 不发 `current_changed`；其余行为（选中态/禁用/锁定）不变。

- [ ] **Step 1: 写失败测试**：`tests/gui/test_activity_bar.py` 新增——构造含 device（浮窗类）与 device(页面类) 混合列表：点 device 图标 → `action_triggered` 收到且 `current_changed` 未发；点页面图标 → `current_changed` 收到且 `action_triggered` 未发。
- [ ] **Step 2: 运行确认失败**：`python -m pytest tests/gui/test_activity_bar.py -v` → FAIL。
- [ ] **Step 3: 实现**：ActivityBar 增加浮窗类 key 集合（`_POPUP_KEYS = {"device","sensor"}` 或构造传入）；点击逻辑分支：浮窗类 → `action_triggered.emit(key)`；页面类 → 现有 `current_changed`。
- [ ] **Step 4: 验证通过**：`python -m pytest tests/gui/test_activity_bar.py -v` → PASS。
- [ ] **Step 5: 提交**：`git commit -m "feat(ui): ActivityBar 支持浮窗触发图标（action_triggered）"`

---

### Task 2: ConnectionPopup 组件（设备浮窗）

**Files:**
- Create: `src/lbs_firmware_studio/gui/widgets/connection_popup.py`
- Test: `tests/gui/test_connection_popup.py`（新建）

**Interfaces:**
- Consumes: `ProductSelector`、`ConnectionSelector`（竖向布局）、`theme` 令牌。
- Produces: `ConnectionPopup(QWidget)`——`Qt.Popup` 窗口（BG_RAISED + BORDER + RADIUS_PANEL），竖向堆叠：标题「设备连接」+ ProductSelector + 分隔线 + 连接区（串口/蓝牙 radio 一行 + 端口下拉+刷新 一行 + 连接按钮+状态点 一行）；接口：`current_product()/product_changed`（透传）、`connection() -> ConnectionSelector`、`set_locked(busy)`。

- [ ] **Step 1: 写失败测试**：新建 `tests/gui/test_connection_popup.py`——构造 popup：产品选择显示当前名；点产品项发出 `product_changed`；连接区控件存在（radio/下拉/刷新/连接按钮）；`set_locked(True)` 禁用产品选择与连接按钮。
- [ ] **Step 2: 运行确认失败**：→ FAIL（ModuleNotFoundError）。
- [ ] **Step 3: 实现**：按上述规格实现（ConnectionSelector 复用，竖向重排——ConnectionSelector 现为横排，popup 内用其控件重组或加 `vertical` 模式；以最少改动为准，report 说明）。
- [ ] **Step 4: 验证通过**：`python -m pytest tests/gui/test_connection_popup.py -v` → PASS。
- [ ] **Step 5: 提交**：`git commit -m "feat(ui): ConnectionPopup 设备连接浮窗（产品+连接竖向）"`

---

### Task 3: MainWindow 集成（顶栏主机信息/设备浮窗/传感器对话框）

**Files:**
- Modify: `src/lbs_firmware_studio/gui/main_window.py`
- Modify: `src/lbs_firmware_studio/gui/app.py`（如需）
- Test: `tests/gui/test_main_window.py`、`tests/gui/test_main_window_buttons.py`、`tests/gui/test_app_smoke.py`

**Interfaces:**
- Consumes: Task 1 ActivityBar 扩展、Task 2 ConnectionPopup、HostStatusBar（从 monitor_page 移到顶栏挂载）。
- Produces: 顶栏 48px = HostStatusBar（横向紧凑）；移除顶栏 ProductSelector/ConnectionSelector/VLine/连接按钮；ActivityBar 图标列表改为 [device(浮窗), device-page, editor, sensor(浮窗), settings]；device 图标 → `action_triggered("device")` 弹 ConnectionPopup（产品切换/连接联动保持）；sensor 图标 → `action_triggered("sensor")` 弹 sensor_update_dialog；`header_text()` 语义保留（从 `self._popup.current_product()` 取）。

- [ ] **Step 1: 写失败测试**：`test_main_window.py` 更新——顶栏含主机信息（`host_bar()` 访问器或断言字段）；点 device 图标弹浮窗（`popup_visible()`）；点 sensor 图标触发对话框（monkeypatch）；产品切换仍重建页面；连接联动（`_on_connection_changed` 仍驱动监控）。
- [ ] **Step 2: 运行确认失败**：→ FAIL。
- [ ] **Step 3: 实现**：MainWindow 重构顶栏与 ActivityBar 接线（`_NAV` 列表扩展为含浮窗键；`action_triggered` 处理弹浮窗/对话框；ConnectionPopup 挂到 `self` 用 `Qt.Popup` 定位）；HostStatusBar 实例挂顶栏（数据源由监控页提供——`monitor_page` 现有 host_state_changed 信号转发到顶栏 HostStatusBar；report 说明接线）。
- [ ] **Step 4: 验证通过**：`python -m pytest tests/gui/test_main_window.py tests/gui/test_app_smoke.py tests/gui/test_main_window_buttons.py tests/gui/test_monitor_page.py -v` → PASS。
- [ ] **Step 5: 提交**：`git commit -m "feat(ui): MainWindow 顶栏主机信息 + 设备/传感器浮窗入口"`

---

### Task 4: 固件页去日志 + 单行当前进度

**Files:**
- Modify: `src/lbs_firmware_studio/gui/pages/firmware_page.py`
- Test: `tests/gui/test_firmware_page.py`

**Interfaces:**
- Consumes: 现有 start_requested/进度/阶段信号。
- Produces: 删除日志窗口（LogView）；新增单行当前进度文本（`current_progress_text()` 访问器，如「正在发送 app/ 45%」——从最后一条 log + 进度合成）；进度条保留。

- [ ] **Step 1: 写失败测试**：`test_firmware_page.py` 更新——`log_text` 相关断言删除/改 `current_progress_text()`；新增：log 信号到达后进度文本更新为最后一条日志；进度更新时文本含百分比。
- [ ] **Step 2: 运行确认失败**：→ FAIL。
- [ ] **Step 3: 实现**：删 LogView 挂载；单行 QLabel 显示当前进度（接收 log 信号取末条 + progress 信号百分比；无活动时显示「就绪」）。
- [ ] **Step 4: 验证通过**：`python -m pytest tests/gui/test_firmware_page.py -v` → PASS；联动 `tests/gui/test_main_window.py`。
- [ ] **Step 5: 提交**：`git commit -m "feat(ui): 固件页去日志窗口，改单行当前进度"`

---

### Task 5: 监控页移主机信息/删传感器按钮

**Files:**
- Modify: `src/lbs_firmware_studio/gui/pages/monitor_page.py`
- Test: `tests/gui/test_monitor_page.py`

**Interfaces:**
- Consumes: Task 3（HostStatusBar 移到顶栏）、MainWindow 转发 host_state_changed。
- Produces: 监控页删除底部 HostStatusBar 挂载与顶部「传感器更新」按钮（按钮逻辑移到侧边栏 sensor 图标）；保留提示条/传感器卡片网格/传感器更新入口由 MainWindow 提供。

- [ ] **Step 1: 写失败测试**：`test_monitor_page.py` 更新——`has_sensor_update_button` 相关断言改为 `has_sensor_update_action`（或删除后由 MainWindow 测试覆盖）；host_status 字段断言改到 MainWindow 层。
- [ ] **Step 2: 运行确认失败**：→ FAIL。
- [ ] **Step 3: 实现**：删 HostStatusBar 与传感器更新按钮；host_state_changed 信号保持（MainWindow 转发到顶栏）。
- [ ] **Step 4: 验证通过**：`python -m pytest tests/gui/test_monitor_page.py tests/gui/test_main_window.py -v` → PASS。
- [ ] **Step 5: 提交**：`git commit -m "feat(ui): 监控页移走主机信息与传感器按钮到顶栏/侧边栏"`

---

### Task 6: 全量回归与合并

- [ ] **Step 1**: 非 GUI 全量 + GUI 按文件全跑，全绿（段错误容忍）。
- [ ] **Step 2**: 无遗留检查（grep 旧顶栏控件/日志窗口残留）。
- [ ] **Step 3**: 最终审查（Ready to merge）→ 推送 main-work → 合并 main → 推送。
