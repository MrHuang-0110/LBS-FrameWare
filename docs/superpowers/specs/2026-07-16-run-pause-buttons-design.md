# 运行/暂停程序按钮 · 设计文档

> 状态：设计已与用户确认，待写实施计划。

## 目标

在代码编辑器页面增加「运行程序」和「暂停程序」两个按钮，通过串口/BLE 发送切换命令
控制设备端脚本的执行状态，按钮状态由设备监控数据流中的实际运行状态驱动。

## 协议命令

设备端运行/暂停切换命令（三产品通用）：

```
5A 97 98 01 B6 01 41 A5
```

- `CMD_RUN_TOGGLE = 0xB6`，data=`b"\x01"`
- 主机发送后设备自动根据当前状态切换运行 ↔ 暂停
- 发送方不等 ACK，不读响应

## 架构与组件

### 1. 协议层 `backend/protocol_frame.py`

新增命令常量：

```python
CMD_RUN_TOGGLE = 0xB6
```

帧构建复用现有 `build_frame(CMD_RUN_TOGGLE, b"\x01")`，无需新函数。

### 2. 编排层 `backend/deployer.py`

无需改动。`toggle_run` 命令仅 8 字节，由 MainWindow 直接调 `transport.write()` 发送，
不经过 DeviceDeployer。

### 3. 监控页 `gui/pages/monitor_page.py`

- 新增信号 `host_state_changed = Signal(str)`，值为 `"start"` / `"stop"` / `""`
- 在 `_render()` 中从当前帧提取运行状态字段（按产品取路径：NEW-AI→`NewAiState`，
  SPARK-AI→`WillAiState`，NEXT-AI→`State`），与上次缓存值比较，变化时 emit
- 监控停止时（`stop_monitor()` / `_on_worker_state("disconnected")`）emit `""`
- 运行状态字段路径随产品配置，从 `MONITOR_PROFILES[product].status_fields` 中
  找到 label 为"运行状态"的路径

### 4. 脚本编辑器页 `gui/pages/script_editor_page.py`

**新增两个浮动按钮**，排在编辑器右上角现有按钮左侧：

```
[▶ 运行] [⏸ 暂停]    [槽位 N] [⬆ 下发]
```

- **运行按钮**：图标 `fa5s.play`，强调色。点击 → 调 `deployer.toggle_run()` →
  乐观切换到"运行中"状态（运行禁用、暂停启用）
- **暂停按钮**：图标 `fa5s.stop`。点击 → 同样发 0xB6 → 乐观切换到"已暂停"
- **按钮样式**：复用现有 `#floatbtn` 样式，图标色取 `theme.ACCENT`（运行）/ `theme.WARNING`（暂停）
- **reposition**：在 `_reposition_float_buttons()` 中扩展定位逻辑，四按钮右上排列

**状态管理**：

| 条件 | 运行按钮 | 暂停按钮 |
|------|---------|---------|
| 监控状态 `"stop"` | 启用 | 禁用 |
| 监控状态 `"start"` | 禁用 | 启用 |
| 监控状态 `""`（未知/监控未开） | 禁用 | 禁用 |
| 下发忙碌中 `set_busy(True)` | 禁用 | 禁用 |
| 无连接目标 | 禁用 | 禁用 |

**新增信号**：
- `run_toggle_requested = Signal()` — 点击运行/暂停按钮时 emit，由 MainWindow 接线处理

**发送路径**（在 MainWindow 中）：
- 收到 `run_toggle_requested` → 取 `_conn.persistent_transport()`（必须已连接，否则按钮禁用）
- 直接 `transport.write(pf.build_frame(pf.CMD_RUN_TOGGLE, b"\x01"))`，不经过 DeviceDeployer
- 8 字节命令主线程直接写，不建线程，不等 ACK

**新增公开方法**：
- `on_host_state_changed(state: str)` — 接收监控帧确认的运行状态，以帧值为准覆盖乐观状态
- `set_run_buttons_enabled(enabled: bool)` — 由 MainWindow 按连接状态控制

**乐观更新逻辑**：
- 点击运行 → 立即 `_running = True`，按钮切换到运行中态
- 点击暂停 → 立即 `_running = False`，按钮切换到已暂停态
- 收到 `on_host_state_changed("start")` → 以帧值为准（通常一致，仅在设备异常时修正）
- 收到 `on_host_state_changed("stop")` → 同上

### 5. 主窗 `gui/main_window.py`

- `MonitorPage.host_state_changed` 信号连接 `ScriptEditorPage.on_host_state_changed`
- `ScriptEditorPage.run_toggle_requested` 信号连接 MainWindow 处理函数：
  取 `_conn.persistent_transport()`，直接 `write(build_frame(CMD_RUN_TOGGLE, b"\x01"))`，
  不经过 DeviceDeployer
- `_update_deploy_buttons()` 扩展：无连接目标时同时禁用运行/暂停按钮
- 编辑页 `set_busy(True)` 时运行/暂停按钮也被禁用（与现有按钮一致）

## 数据流与交互

```
用户点击运行按钮
  → 乐观更新 UI：运行禁用、暂停启用
  → toggle_run() → transport.write(0xB6 帧)
  → 设备收到命令，切换为运行状态
  → 设备 JSON 帧中 NewAiState/WillAiState/State 变为 "start"
  → MonitorParser → MonitorWorker.frame_parsed → MonitorPage._render()
  → 检测状态变化 → host_state_changed.emit("start")
  → ScriptEditorPage.on_host_state_changed("start")
  → 以帧值为准确认运行态（与乐观状态一致，无变化）
```

暂停流程对称，状态值变为 `"stop"`。

## 错误处理

- 无连接目标时按钮禁用，不发送命令（由 `_update_deploy_buttons()` 保证）
- 下发忙碌时按钮禁用（由 `set_busy(True)` 保证）
- 监控未开启时按钮禁用（状态为 `""`）
- 发送失败（串口异常）→ 静默失败，等下一帧监控数据修正按钮状态（乐观更新会被监控帧覆盖）

## 非目标（YAGNI）

- 不做运行/暂停的 CLI 支持
- 不做超时回退逻辑（乐观更新后被监控帧自然修正即可）
- 不做运行状态的持久化存储
- 不改变 DeployWorker 线程模型（8 字节命令不走线程）