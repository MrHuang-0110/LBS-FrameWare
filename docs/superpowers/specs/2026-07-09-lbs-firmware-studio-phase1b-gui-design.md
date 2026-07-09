# LBS Firmware Studio · Phase 1b 设计文档（GUI · 固件更新）

- 日期：2026-07-09
- 状态：待复审
- 范围：Phase 1b —— App Store 风格 PySide6 GUI，本阶段只落地**固件更新**功能 + 完整界面骨架
- 前置：Phase 1a 后端已完成并真机验证通过

---

## 1. 概述与范围

### 1.1 目标

用 PySide6 构建 App Store 风格的桌面 GUI，调用已验证的 Phase 1a 后端。遵循「一个功能一个功能来」，**本阶段只落地固件更新**，但把整个界面骨架（启动产品选择、左功能栏、左上角状态、右操作区、设置页）搭完整，后续功能只需填充右侧页面。

### 1.2 纳入 Phase 1b

- 启动产品选择界面（三产品卡片 + 图标，动态由 products.yaml 生成）
- 主窗口骨架：顶栏（产品名 + 状态灯 + 串口选择）+ 左功能栏 + 右内容区（QStackedWidget）
- 固件更新页：串口自动识别、固件源、开始、阶段进度、日志
- 设置页：可编辑编译器路径 / 固件目录 / 波特率，保存写回 yaml
- 后端 `DeviceDeployer` 在 QThread 里运行，四个信号回主线程更新 UI

### 1.3 不纳入（左栏置灰"即将推出"占位）

- 脚本下发（含圆形点阵槽位控件——留待后续，可能与编辑器整合）
- 代码编辑器（Phase 2）
- 数据监控（Phase 3）

### 1.4 成功标准

1. 启动 → 选产品 → 固件更新页 → 对三款真机各完成一次固件更新。
2. 进度条 + 阶段文字 + 日志实时更新，操作中控件锁定，出错有提示。
3. 串口下拉自动识别 "LBS Serial" 设备并默认选中。
4. GUI 逻辑有 pytest-qt 自动化测试；worker 用设备模拟器测试。

---

## 2. 架构

### 2.1 目录结构（全部在 `src/lbs_firmware_studio/gui/` 下）

```
gui/
  __init__.py
  app.py              # 入口：QApplication，加载 products.yaml，启动 StartupWindow
  startup_window.py   # 产品选择界面（三卡片）
  main_window.py      # 主窗口：顶栏 + 左导航 + 右内容区(QStackedWidget)
  worker.py           # DeployWorker(QObject)：DeviceDeployer 放 QThread 跑，转发信号
  theme.py            # App Store 浅色主题 QSS + 配色常量
  pages/
    __init__.py
    firmware_page.py    # 固件更新页
    settings_page.py    # 设置页
    placeholder_page.py # "即将推出"占位页（脚本下发/编辑/监控共用）
  widgets/
    __init__.py
    port_selector.py    # 串口下拉 + 刷新 + 自动识别 LBS Serial
    status_badge.py     # 左上角状态灯（灰/琥珀/绿/红）
    log_view.py         # 日志区（时间戳 + 级别着色）
  icons/                # 产品图标 + 功能栏图标（SVG）
```

### 2.2 关键设计原则

- **GUI 层不碰协议**：所有设备操作经 `worker.py` 调 `DeviceDeployer`；GUI 只连信号、更新控件。
- **后端近零改动**：仅两处小增强（见 §6），不改协议逻辑。
- **配置驱动**：产品列表、串口波特率、固件目录均来自 `products.yaml`，不硬编码。
- **文件聚焦**：每个页面/控件一个文件、单一职责，便于独立测试与后续扩展。

### 2.3 入口与生命周期

`app.py` → 创建 QApplication、应用 `theme.py` 全局 QSS、`load_profiles` → 显示 `StartupWindow` → 用户选产品 → 关闭启动窗、打开 `MainWindow(profile)`。「切换产品」按钮 → 关主窗、回启动窗。

---

## 3. 线程模型与信号流

后端串口操作阻塞，必须在工作线程运行，绝不阻塞 Qt 事件循环。

```
主线程(Qt事件循环)              工作线程(QThread)
   │ 点"开始固件更新"              │
   ├──worker.start()──────────▶  │ DeviceDeployer.update_firmware(profile, port)
   │                              │   打开串口→复位→等重枚举→逐文件传输→关闭
   │  ◀── progress(done,total) ───┤   （每帧 / 每文件发信号）
   │  ◀── log(str) ───────────────┤
   │  ◀── state_changed(str) ─────┤
   │  ◀── error(str) ─────────────┤
   │  ◀── finished ───────────────┤   操作结束
   │  更新进度/日志/状态灯          │
   │  操作中锁控件，结束解锁         │
```

- `DeployWorker(QObject)` 持有 `SerialTransport` + `DeviceDeployer`，`moveToThread(QThread)`。提供 `run_firmware(profile, port)` 槽，内部 `open→start_rx→update_firmware→close`，末尾发 `finished`。
- 后端四信号（progress/log/state_changed/error）本就是 Qt Signal，跨线程连到主线程槽，Qt 自动队列连接，线程安全。
- **控件锁定**：`state_changed` 进入非 idle → 禁用「开始」按钮 / 串口下拉 / 切换产品；`finished` 或 error → 恢复。
- **状态灯映射**：idle=灰；connecting/reconnecting/transfering/entering_upgrade/compiling=琥珀；done=绿；error=红。

---

## 4. 界面布局与控件

### 4.1 启动产品选择界面

```
              LBS Firmware Studio
                 选择要操作的产品

   ┌──────────┐   ┌──────────┐   ┌──────────┐
   │  [图标]   │   │  [图标]   │   │  [图标]   │
   │  NEW-AI  │   │ SPARK-AI │   │  NEXT-AI │
   │  8 端口   │   │  4 端口   │   │  2 端口   │
   │ 自定义帧  │   │ 自定义帧  │   │  YMODEM  │
   └──────────┘   └──────────┘   └──────────┘
```

- 浅色底 `#F5F5F7`，白卡片圆角 12px、轻阴影、悬停轻微浮起。
- 卡片信息来自 profile：名称、端口数（NEW-AI 8 / SPARK-AI 4 / NEXT-AI 2，作为展示元数据写进 products.yaml）、协议。
- 点卡片 → 进入主窗口，设为当前产品。

### 4.2 主窗口

```
┌────────────────────────────────────────────────────────────┐
│ [图标] NEW-AI   ● 空闲   LBS Serial (COM9) ▾  🔄  [切换产品]  │ 顶栏
├───────────────┬────────────────────────────────────────────┤
│ ⬇ 固件更新 ◀  │  固件更新                                    │
│ ▶ 脚本下发🔒  │  固件源: ./products/NEW-AI/fwlib   [浏览]     │
│ ⟨⟩ 代码编辑🔒 │  待发送: app, music, boot, config, version   │
│ 📊 数据监控🔒 │                                            │
│ ───────       │  [ ▶ 开始固件更新 ]                          │
│ ⚙ 设置        │  阶段: 传输中 · 文件 12/40 · music/A.wav    │
│               │  ████████████░░░░░░░░  62%                  │
│               │  日志: [时间戳 + 着色滚动区]                  │
└───────────────┴────────────────────────────────────────────┘
```

- **顶栏**：产品图标 + 名；状态灯（● 空闲/操作中/成功/错误）；串口下拉（LBS Serial 置顶自动选中，显示友好名）+ 刷新按钮；切换产品按钮。
- **左导航**：图标 + 文字，当前项浅蓝底蓝字。固件更新可用；脚本下发/代码编辑/数据监控带 🔒 置灰，点击提示"即将推出"；设置可用。分组用细分割线。
- **右内容区**：QStackedWidget，随导航切页。

### 4.3 固件更新页

- **固件源**：只读文本框显示 `profile.firmware_dir` + "浏览"按钮（临时覆盖本次操作使用的目录，不写回配置）。
- **待发送**：显示 `profile.folders`（NEW-AI 5 / SPARK-AI 2 / NEXT-AI 单文件）。
- **开始按钮**：Apple 蓝主按钮。前置校验失败（串口未选 / 固件目录不存在）→ 禁用并提示原因。操作中禁用。
- **进度区**：阶段文字（融合 state + 当前文件名）+ 进度条 + 百分比。
- **日志区**：可滚动，时间戳 + 级别图标着色（✓成功 / →过程 / ↓传输 / ✗错误），内容来自 `log` 信号。

### 4.4 串口选择控件（port_selector）

- 下拉列出所有端口；`description` 含 "LBS Serial"（或 VID:PID=0483:5740）的排最前并默认选中；显示友好名 "LBS Serial (COM9)"。
- 刷新按钮 🔄 重新扫描（`serial.tools.list_ports.comports()`）。
- 无 LBS 设备时显示全部端口，不默认选中，提示"未检测到 LBS 设备"。

### 4.5 设置页

- 可编辑：编译器路径（文本框 + 浏览）、各产品固件目录、默认波特率。
- "保存" → 写回 `products.yaml`（后端新增 `save_profiles`，见 §6）。保存后提示"已保存，重启后生效"。

### 4.6 视觉规范

- 背景 `#F5F5F7`，面板/卡片 `#FFFFFF`；强调色 Apple 蓝 `#0071E3`；状态色 绿/琥珀/红/灰。
- 圆角 ~12px、极轻阴影；UI 字体 Segoe UI Variable / Inter，日志/端口/文件名用等宽（Cascadia Code / JetBrains Mono）。
- 图标：产品专属图标 + 功能栏线条图标（固件更新=下载箭头、脚本下发=上传、代码编辑=代码括号、数据监控=折线图、设置=齿轮）。图标集用 SVG（qtawesome 可选）；具体图标在实现阶段用 ui-ux-pro-max 定。
- 主题集中在 `theme.py`（QSS + 配色常量），便于统一调整。

---

## 5. 错误处理

| 场景 | 处理 |
|------|------|
| 后端 error 信号 | 弹错误对话框（原因文字）+ 状态灯红 + 日志红色记录 |
| 串口打开失败（未插/被占用/权限） | 友好中文提示（后端已区分类型）；操作不启动 |
| 前置校验（串口未选/固件目录不存在） | 开始按钮禁用 + 页面提示原因 |
| 操作中重复点击/切换产品 | 控件锁定，不可操作 |
| 设备重连超时（真拔出） | 后端抛错 → error 信号 → 上述错误流程 |

---

## 6. 需要的后端小改动（GUI 依赖）

1. **当前文件名日志**：让 GUI 能显示正在更新的文件。接口明确定义如下（不推迟到计划阶段）：
   - `CustomFrameProtocol.__init__` 增加可选参数 `log_cb: Callable[[str], None] | None = None`（默认 None，保持协议层可独立单测、零副作用）。
   - `_send_file_with_cmd` / `send_folder` 在发送每个文件前，若 `log_cb` 非 None 则调用 `log_cb(f"发送 {folder_or_name}/{filename}")`。
   - `DeviceDeployer._make_protocol` 构造 `CustomFrameProtocol` 时传入 `log_cb=self.log.emit`，把当前文件名转成 `log` 信号。
   - YmodemProtocol 同理加 `log_cb`（单文件，发送前 log 一次文件名）。
2. **配置保存**：`profile.py` 新增 `save_profiles(raw: dict, path: Path)`，把设置页修改写回 `products.yaml`。用 PyYAML `safe_dump`，**接受丢失注释**（关键字段正确即可）；设置页只写编译器路径 / 固件目录 / 波特率这几个字段。

> 不加 `max_slot`（脚本下发才需要，本阶段 YAGNI）。

---

## 7. 测试策略

- **GUI 逻辑单测（pytest-qt）**：产品卡片点击切换、导航切页、串口下拉自动选中 LBS Serial、控件随 state 锁定/解锁、进度条随 progress 更新、错误对话框触发。用假 worker / 手动 emit 信号驱动，不碰真串口。
- **worker 线程测试**：用 Phase 1a 的 DeviceSimulator + FakeSerial 驱动 DeployWorker，验证 open→update_firmware→信号转发→close 全流程，进度/状态/日志信号正确到达。
- **手动真机验证**：GUI 对三款产品各做一次固件更新（沿用 HITL 清单）。

---

## 8. 待定项与风险

- **图标资源**：产品图标与功能栏图标需准备 SVG；实现阶段用 ui-ux-pro-max 出具体图标，缺失时先用占位/文字。
- **QSS 与真实观感**：App Store 观感靠 QSS 调，需实现后目测微调（属正常前端迭代）。
- **设置页写 yaml**：PyYAML `safe_dump` 会丢注释；本阶段接受（关键字段正确即可）。
- **端口数展示元数据**：启动卡片显示的"8/4/2 端口"需作为展示字段写进 products.yaml（如 `display_ports: 8`），不影响协议。
