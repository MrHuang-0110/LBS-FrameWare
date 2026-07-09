# LBS Firmware Studio · Phase 1b GUI 视觉返工设计（VS Code 深色风格）

- 日期：2026-07-09
- 状态：待复审
- 范围：把现有浅色"App Store 风格"GUI 重做为 VS Code Dark+ 深色风格；纯视觉+交互返工，业务逻辑保留复用

---

## 1. 背景与范围

用户反馈现有浅色 App Store 风格不对，明确要求改为 **VS Code 深色风格**（左侧图标功能栏、右侧功能操作区、顶部设备信息、底部状态栏）。这是 Phase 1b GUI 的视觉层返工，不改业务逻辑。

### 1.1 纳入
- `theme.py` 重写为 VS Code Dark+ 深色令牌 + 深色全局 QSS
- 主窗口重构：左 Activity Bar（纯图标竖条）+ 顶栏（设备信息）+ 主内容区 + 底部状态栏
- 启动产品选择界面：单击框选高亮、双击进入
- 现有控件/页面适配深色主题
- 新增 qtawesome 依赖做图标

### 1.2 不纳入（保留复用，零改动）
- `worker.py`（DeployWorker）、全部 `backend/`（DeviceDeployer、协议、串口、profile）
- 固件更新业务流程、串口 LBS 自动识别逻辑（PortSelector 内部逻辑保留，仅样式变深色）
- 功能范围不变：仅固件更新可用；脚本下发/代码编辑/数据监控置灰"即将推出"；设置可用

### 1.3 成功标准
1. 界面呈现 VS Code Dark+ 深色观感：Activity Bar + 顶栏 + 底部蓝色状态栏。
2. 底部状态栏清晰显示连接状态（解决"看不到已连接提示"）。
3. 产品选择：单击框选、双击进入。
4. 固件更新功能与之前一致（不卡死、进度/日志/状态实时），只是外观变深色。
5. GUI 逻辑测试更新并通过。

---

## 2. 设计令牌（VS Code Dark+，精确 hex）

集中在 `theme.py`。基于 VS Code 官方 Dark+ 主题色值。

### 2.1 背景分层
| 令牌 | Hex | 用途 |
|---|---|---|
| BG_EDITOR | `#1E1E1E` | 主内容区 |
| BG_SIDEBAR | `#252526` | 次级面板 / 产品卡片 |
| BG_BAR | `#333333` | Activity Bar、顶栏 |
| BG_INPUT | `#3C3C3C` | 输入框、下拉框、进度轨道 |
| BG_HOVER | `#2A2D2E` | 列表/项悬停 |
| BG_SELECTED | `#094771` | 选中项深蓝 |
| STATUSBAR | `#007ACC` | 底部状态栏 |

### 2.2 文字（对 #1E1E1E 已验证对比度）
| 令牌 | Hex | 对比度 |
|---|---|---|
| TEXT_PRIMARY | `#CCCCCC` | ≈9.5:1（AAA） |
| TEXT_SECONDARY | `#9D9D9D` | ≈5.3:1（AA） |
| TEXT_DISABLED | `#6A6A6A` | 禁用态 |
| TEXT_ON_ACCENT | `#FFFFFF` | 蓝底上文字 |

### 2.3 强调与语义色
| 令牌 | Hex | 用途 |
|---|---|---|
| ACCENT | `#007ACC` | 主按钮/焦点/进度/选中亮条 |
| ACCENT_HOVER | `#1177BB` | 主按钮悬停 |
| SUCCESS | `#4EC9B0` | 成功（深色适配青绿） |
| WARNING | `#CCA700` | 操作中/警告 |
| ERROR | `#F14C4C` | 错误 |
| BORDER | `#3E3E42` | 边框/分割线 |
| ICON_IDLE | `#858585` | Activity Bar 未选中图标 |
| ICON_DISABLED | `#4A4A4A` | Activity Bar 禁用图标 |

### 2.4 尺寸与节奏
- 全局圆角 **2px**（VS Code 近直角简约感，禁用大圆角）
- 间距节奏 4 / 8 / 12 / 16px
- 字号 11 / 13(默认) / 16 / 20 px
- UI 字体 `Segoe UI`；等宽 `Cascadia Code` / `Consolas`（日志/串口/文件名）

### 2.5 state → 颜色（状态灯/状态栏）
idle=`#858585`；compiling/connecting/entering_upgrade/reconnecting/transfering=`#CCA700`；done=`#4EC9B0`；error=`#F14C4C`；未知→idle 灰。

---

## 3. 布局

```
┌──┬──────────────────────────────────────────────────┐
│  │ ◆ NEW-AI          LBS Serial (COM9) ▾  ⟳   切换产品 │ 顶栏 36px #333
│⬇ ├──────────────────────────────────────────────────┤
│▶ │   固件更新                                          │
│⟨⟩│   固件源: ./products/NEW-AI/fwlib      [浏览]        │ 主内容区 #1E1E1E
│📊│   待发送: app, music, boot, config, version         │
│  │   [ ▶ 开始固件更新 ]                                │
│  │   传输中 · 文件 12/40 · music/A.wav                 │
│  │   ████████████░░░░  62%                            │
│  │   日志: [深色等宽着色滚动区]                          │
│⚙ │                                                   │
├──┴──────────────────────────────────────────────────┤
│ ● 已连接 COM9 · 115200            NEW-AI · 空闲        │ 底栏 22px 蓝 #007ACC
└──────────────────────────────────────────────────────┘
 ↑ Activity Bar 48px #333
```

### 3.1 Activity Bar（左，48px，#333333）
- 纯图标竖条，图标 24px 居中，项高 48px，图标来自 qtawesome。
- 上组（功能）：固件更新、脚本下发、代码编辑、数据监控。底部沉底：设置齿轮（VS Code 惯例，与上组间用 addStretch 分隔）。
- 交互态：
  - 未选中：图标 `#858585`
  - 悬停：图标 `#CCCCCC` + tooltip 显示功能名
  - 选中：图标 `#FFFFFF` + 左侧 2px 蓝亮条 `#007ACC`
  - 禁用：图标 `#4A4A4A`，无 hover，tooltip "即将推出"
- 图标建议（qtawesome，Font Awesome / Material）：固件更新=下载云、脚本下发=上传、代码编辑=代码括号、数据监控=折线图、设置=齿轮。具体图标名实现时定。

### 3.2 顶栏（36px，#333333）
左到右：产品图标+名（如 "◆ NEW-AI"）、弹性空隙、串口下拉（LBS 自动识别）+ 刷新按钮、切换产品按钮。精简，不放波特率/版本。

### 3.3 主内容区（#1E1E1E）
QStackedWidget，随 Activity Bar 切换页面。复用现有 firmware_page/settings_page/placeholder_page，改深色样式。内边距 16px。

### 3.4 底部状态栏（22px，#007ACC 蓝，白字 12px）
- 左：连接状态。未连接 `○ 未连接`；已选串口但空闲 `● COM9 · 115200`；操作中/完成/错误随 state 文字变化。
- 右：产品名 · 操作状态（空闲/编译中/连接中/传输中/完成/错误）。
- 这是 VS Code 招牌蓝状态栏，一眼可见连接与运行状态，解决"看不到已连接提示"。

---

## 4. 产品选择界面（双击 + 框选）

启动界面改 VS Code 深色，三个产品卡片（#252526 底、#3E3E42 边框）：
- **单击** = 框选高亮（加 2px 蓝边框 `#007ACC`），不进入。同一时刻仅一张高亮。
- **双击** = 选定并进入主窗口（发 product_selected 信号）。
- 悬停微亮（#2A2D2E）。
- 卡片内容不变：产品图标、名称、端口数（display_ports）、协议标签。

---

## 5. 组件改动清单

| 文件 | 操作 | 说明 |
|---|---|---|
| `theme.py` | 重写 | VS Code Dark+ 令牌 + 深色 app_qss()；state_color 改深色值 |
| `main_window.py` | 重构 | 用 ActivityBar 替换 QListWidget 导航；加顶栏、底部 StatusBar；QStackedWidget 保留；worker 接线不动 |
| `startup_window.py` | 改交互 | 单击框选、双击进入；深色卡片 |
| `widgets/activity_bar.py` | 新增 | 纯图标竖条控件：项(图标/名称/是否启用)、选中态左亮条、tooltip、禁用态；current_changed 信号 |
| `widgets/status_bar.py` | 新增 | 底部蓝色状态栏：set_connection(port,baud)/set_state(state)/set_product(name) |
| `widgets/status_badge.py` | 微调/可能弃用 | 连接状态移到底部 StatusBar；若顶栏不再需要圆点徽章可弃用，否则改深色 |
| `widgets/port_selector.py` | 样式 | 逻辑不动，深色下拉样式（全局 QSS 覆盖） |
| `widgets/log_view.py` | 微调 | 深色底 + 级别色改深色适配值 |
| `pages/firmware_page.py` | 微调 | 深色样式；stage 文字/进度条继承 QSS |
| `pages/settings_page.py` | 微调 | 深色样式 |
| `pages/placeholder_page.py` | 微调 | 深色样式 |
| `worker.py`、`backend/**` | 不动 | 业务逻辑保留 |
| `pyproject.toml` | 改 | 加 qtawesome 依赖 |

> status_badge 去留在实现时定：若底部 StatusBar 已完整承载连接+运行状态，顶栏可不再放圆点徽章，status_badge 可弃用（减冗余）；实现计划里明确。

---

## 6. 交互与状态流（不变的部分）

固件更新的线程模型、信号流保持 Phase 1b 已修复的版本：DeployWorker 在 QThread 里跑（set_job + started 直连无参 run_firmware 槽，已修卡死），四信号回主线程。UI 消费信号的去向调整为：
- `state_changed` → Activity Bar/顶栏控件锁定 + 底部 StatusBar 状态文字/色 + firmware_page stage
- `progress` → firmware_page 进度条
- `log` → firmware_page 日志区
- `error` → 错误对话框（深色）+ StatusBar 红

操作中锁定：禁用开始按钮、串口下拉、切换产品、Activity Bar 切换（防止操作中切走）。

---

## 7. 测试策略

沿用 pytest-qt + 手动 emit 信号，不碰真串口。

- **activity_bar**（新）：项渲染、启用/禁用、点击可用项发 current_changed、禁用项不切换、选中态。
- **status_bar**（新）：set_connection 显示端口+波特率、set_state 文字与颜色映射、未连接态。
- **theme**（更新）：深色令牌值、state_color 深色映射、app_qss 含深色关键色。
- **startup_window**（更新）：单击框选（发 selection-changed，不进入）、双击发 product_selected。
- **main_window**（更新）：新布局——Activity Bar 项存在/锁定、切页、顶栏产品名、底部状态栏随 state 更新、busy 锁定含 Activity Bar。
- **firmware_page/settings_page/port_selector/log_view**：现有测试基本保留（逻辑不变），个别断言若依赖旧样式则更新。
- **手动真机验证**：GUI 观感 + 固件更新端到端（沿用 HITL 清单），确认深色观感、连接状态可见、不卡死。

---

## 8. 待定项与风险

- **qtawesome 图标名**：具体图标（fa5s.download 等）在实现时挑选，缺失时用近似图标；不阻塞。
- **QSS 观感微调**：深色 QSS 需实现后目测微调（正常前端迭代）；VS Code 有成熟参考，风险低。
- **status_badge 去留**：实现时按底部 StatusBar 是否完整承载来定，倾向弃用以减冗余。
- **系统深色跟随**：本次按固定 VS Code Dark+ 深色实现（不做明暗自动切换）；用户诉求核心是"深色不刺眼"，固定深色即满足。若后续要跟随系统明暗，另开范围。
- **真机观感**：深色 QSS 在真实 Windows 上的最终观感需手动确认，可能需一轮微调。
