# 布局重构 v3 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** ActivityBar 精简为 设备/代码编辑 两图标 + 左下角设置；设备浮窗内嵌固件更新（固件源保留）+ 传感器更新；监控数据改主内容区右侧栏；移除固件与监控页/设置页。

**Architecture:** 改动集中在 gui/。ActivityBar 减图标并加底部设置键；ConnectionPopup 内嵌固件更新区（复用 FirmwarePage 的固件源/进度/单行文本逻辑——抽成可复用组件）；新建右侧 MonitorPanel（从 monitor_page 提取传感器卡片网格）；MainWindow 主内容区改 页面栈+右侧栏 布局，移除固件与监控页/设置页。

**Tech Stack:** PySide6 / qtawesome / pytest-qt

## Global Constraints
- 深色主题不硬编码色值（theme.* 令牌）；图标 qta fa5s.*。
- GUI 层不碰协议/串口/BLE；设备操作仍经 worker → deployer。
- 测试访问器签名尽量保持；`_firmware`/`_monitor`/`_editor_page` 属性保留（若有仍存在）。
- GUI 测试按文件单独跑（pytest-qt 退出段错误环境坑）；提交到 main-work，完成后合并回 main 并推送。

---

### Task 1: ActivityBar 精简（device/editor + 底部设置按钮）

**Files:**
- Modify: `src/lbs_firmware_studio/gui/widgets/activity_bar.py`
- Test: `tests/gui/test_activity_bar.py`

**Interfaces:**
- Consumes: Task 1 已加 `action_triggered`/`popup_keys`。
- Produces: `ActivityBar(items)` 支持「底部设置键」——新增 `settings_key`（如 `"settings"`）渲染在最底部（stretch 分隔），点击发 `action_triggered("settings")`（浮窗类语义或独立信号，以最少改动为准）；`nav_keys()` 只含非底部键。

- [ ] **Step 1: 写失败测试**：`test_activity_bar.py` 新增——构造 `ActivityBar([...], settings_key="settings")`：`nav_keys()` 不含 settings；点 settings 图标 → `action_triggered("settings")` 且不改变 current_key。
- [ ] **Step 2: 运行确认失败** → FAIL。
- [ ] **Step 3: 实现**：底部设置键（stretch 后渲染，图标 `fa5s.cog`），点击发 `action_triggered("settings")`；`nav_keys()` 过滤。
- [ ] **Step 4: 验证通过**：`python -m pytest tests/gui/test_activity_bar.py -v` → PASS。
- [ ] **Step 5: 提交**：`git commit -m "feat(ui): ActivityBar 底部设置键（settings_key）"`

---

### Task 2: 设备浮窗扩充（固件源+固件更新+传感器更新内嵌）

**Files:**
- Modify: `src/lbs_firmware_studio/gui/widgets/connection_popup.py`
- Modify: `src/lbs_firmware_studio/gui/pages/firmware_page.py`（若固件更新区抽组件）
- Create: `src/lbs_firmware_studio/gui/widgets/firmware_update_section.py`（可选：可复用固件更新区）
- Test: `tests/gui/test_connection_popup.py`、`tests/gui/test_firmware_update_section.py`

**Interfaces:**
- Consumes: FirmwarePage 现有固件源/进度/单行文本逻辑、SensorUpdateDialog。
- Produces: ConnectionPopup 内嵌：分隔线后 **固件更新区**（固件源选择 `set_firmware_dir_getter`/开始按钮 `start_firmware_requested`/进度条/单行进度文本）+ **传感器更新按钮**（`sensor_update_requested` 信号）；FirmwarePage 若不再独立存在则其固件更新区逻辑抽为 `FirmwareUpdateSection` 复用（report 说明抽法）。

- [ ] **Step 1: 写失败测试**：`test_connection_popup.py` 新增——浮窗含固件源控件/开始按钮/进度条/单行文本；点开始按钮发 `start_firmware_requested`；点传感器按钮发 `sensor_update_requested`；`set_locked` 禁用全部。
- [ ] **Step 2: 运行确认失败** → FAIL。
- [ ] **Step 3: 实现**：按上述规格（固件源选择用现有 FirmwarePage 的目录选择逻辑——`firmware_dir_text`/选择按钮，report 说明复用方式）。
- [ ] **Step 4: 验证通过**：`python -m pytest tests/gui/test_connection_popup.py tests/gui/test_firmware_update_section.py -v` → PASS。
- [ ] **Step 5: 提交**：`git commit -m "feat(ui): 设备浮窗内嵌固件更新（固件源/进度/单行文本）与传感器更新"`

---

### Task 3: MainWindow 主内容区右侧监控栏 + 移除固件监控/设置页

**Files:**
- Modify: `src/lbs_firmware_studio/gui/main_window.py`
- Modify: `src/lbs_firmware_studio/gui/pages/monitor_page.py`（或新建 `widgets/monitor_panel.py` 提取传感器卡片）
- Modify: `src/lbs_firmware_studio/gui/app.py`（如需）
- Test: `tests/gui/test_main_window.py`、`tests/gui/test_monitor_page.py`、`tests/gui/test_app_smoke.py`

**Interfaces:**
- Consumes: Task 1/2、MonitorPanel（传感器卡片网格从 monitor_page 提取）、SensorUpdateDialog。
- Produces: 主内容区 = QHBox[ 页面栈（代码编辑页） | 右侧 MonitorPanel（传感器卡片，宽 ~280px） ]；ActivityBar = [device(浮窗), editor(页面)] + settings_key；`action_triggered("settings")` → 左下角设置按钮（弹设置页/对话框——report 说明：设置内容少则对话框，多则保留 settings_page 以对话框或子窗口展示）；移除固件与监控页（FirmwarePage/MonitorPage 从 `_make_page` 移除——固件更新逻辑已在浮窗、监控数据在右侧栏）；`header_text()`/`nav_labels()` 语义调整。

- [ ] **Step 1: 写失败测试**：`test_main_window.py` 更新——`nav_labels()` == [设备, 代码编辑]；主内容区含右侧监控栏（`monitor_panel()` 访问器）；设备浮窗含固件更新区；设置按钮在左下角（`settings_button()`）；固件更新从浮窗发起仍走 `start_firmware_requested` → worker 链路；监控数据经 monitor_panel 更新。
- [ ] **Step 2: 运行确认失败** → FAIL。
- [ ] **Step 3: 实现**：按上述规格重构 MainWindow（MonitorPanel 提取传感器卡片网格+提示条；固件与监控页从页面栈移除；FirmwarePage 的固件更新逻辑由浮窗内 FirmwareUpdateSection 承担——若 FirmwarePage 不再被引用则删除文件与测试，report 说明）。
- [ ] **Step 4: 验证通过**：`python -m pytest tests/gui/test_main_window.py tests/gui/test_app_smoke.py tests/gui/test_monitor_page.py tests/gui/test_main_window_buttons.py tests/gui/test_main_window_ble_gate.py -v` → PASS。
- [ ] **Step 5: 提交**：`git commit -m "feat(ui): 主内容区右侧监控栏 + ActivityBar 精简 + 移除固件监控/设置页"`

---

### Task 4: 全量回归与合并

- [ ] **Step 1**: 非 GUI 全量 + GUI 按文件全跑，全绿（段错误容忍）。
- [ ] **Step 2**: 无遗留检查（grep 固件与监控页/设置页入口残留）。
- [ ] **Step 3**: 最终审查（Ready to merge）→ 推送 main-work → 合并 main → 推送。
