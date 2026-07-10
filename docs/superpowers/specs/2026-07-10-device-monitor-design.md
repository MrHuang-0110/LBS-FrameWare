# 设备数据监控页 + NEW-AI 传感器更新 · 设计文档

> 状态：设计已与用户确认（架构 / 数据流 / 产品参数化 / 传感器更新交互 / 错误处理与测试 五段均通过），待写实施计划。

## 目标

在 LBS Firmware Studio 新增一个独立的 **设备数据监控页**，实时接收设备通过 USB CDC
持续流式输出的 JSON 行（设备端 `USB_printf("%s\r\n", json)`），解析后以卡片形式展示各
端口传感器数据，底部状态栏展示主机信息。三个产品（NEW-AI / SPARK-AI / NEXT-AI）都支持，
卡片数与状态字段随当前产品参数化。此外 NEW-AI 独有 **传感器更新** 功能：通过对话框为
8 个端口分别指定目标设备类型，组帧下发。

## 全局约束（沿用项目既定）

- Python 3.13、Windows、解释器用 `python`；PySide6、qtawesome、pytest-qt。
- **GUI 层只做界面**：串口读写经 worker 调后端，纯逻辑（解析 / 组帧）放 `backend/`，零 GUI 依赖。
- 深色主题：颜色 / 圆角一律取 `theme.*` 常量，禁止硬编码色值。
- 事件处理器中先 `super()` 再 `emit`（避免 use-after-delete）。
- 测试用 pytest-qt + 手动 emit / qtbot 真实事件，**不碰真串口**；GUI 测试按文件单独跑，
  容忍多 QThread 同进程 teardown 段错误（以断言结果为准）。
- 监控串口连接**独立于部署**：点「开始监控」才 open，「停止」才 close；同一物理端口不能同时
  被部署与监控占用（物理限制）。

## 数据触发方式

设备**一直自动流式输出** JSON 行，GUI 只需打开端口、按 `\r\n` 切行解析。无需发送启动/轮询命令。

## 产品监控数据样例（已核实）

**NEW-AI**（8 端口）：
```json
{"deviceList":[{"port":0},...,{"port":7}],"flash":{"total":"0.00 mb","free":"0.00 mb"},
"version":317,"mem":{"yaw":"60.31","pitch":"179.39","roll":"-0.34"},"heap":"236624",
"bat":"100.00","voic":"0.07","MAC":"EC230905AA48","NewAiState":"stop"}
```
支持传感器类型（deviceList 项内的对象 key）：`big_motor` / `small_motor`（circly/speed/angle/dt/version/SoftwareVersion）、
`ultrasion`（cm）、`touch`（state）、`gray`（1-4/b1-b4/version/Softwareversion）、
`color`（r/g/b/lux/version/SoftwareVersion）、`nfc`（id/version）、
`gray_v2`（1-7/b1-b7/t1-t7/version/Softwareversion）、`camer`（mode + 4 组 id/x/y/w/h/pp）。

**SPARK-AI**（4 端口）：
```json
{"deviceList":[{"port":0,"ultrasion":{"cm":"255"}},{"port":1,"color":{...}},
{"port":2,"touch":{"state":0}},{"port":3}],"flash":{"total":"960 kb","free":"736 kb"},
"adc":{"bat":"82%"},"version":109,"heap":"145","WillAiState":"stop"}
```

**NEXT-AI**（2 端口）：
```json
{"deviceList":[{"port":0},{"port":1}],"adc":{"bat":"100%","ir":"298"},
"version":108,"heap":"36","btName":"LBS_NEXT_AI","btAdvData":"F1F2F3","State":"stop"}
```

## 架构与组件

### 后端（纯逻辑，零 GUI）

**`backend/monitor_parser.py`（新增）**
- `MonitorParser` 类：维护字节缓冲以处理跨 chunk 的半行。
  - `feed(data: bytes) -> list[dict]`：把新字节接入缓冲，按 `\r\n`（兼容 `\n`）切出完整行，
    每行 `json.loads`；返回本次解析出的所有完整 dict。
  - 坏行（非法 JSON）**静默丢弃**，不抛异常，继续处理后续行。
  - **缓冲上限保护**：缓冲累积超过 64KB 仍无换行 → 清空缓冲，防内存膨胀。

**`backend/sensor_update.py`（新增）**
- 设备类型 ID 常量（源码核实自 `e:/LBS-NEW-AI/Drivers/DataFile/*`）：

  | 常量 | 值 | 含义 |
  |---|---|---|
  | `DEV_ID_BIG_MOTOR` | 0xA1 | 大电机 |
  | `DEV_ID_SMALL_MOTOR` | 0xA6 | 中电机（小电机） |
  | `DEV_ID_COLOR` | 0xA2 | 颜色传感器 |
  | `DEV_ID_ULTRASION` | 0xA3 | 超声波传感器 |
  | `DEV_ID_TOUCH` | 0xA4 | 触摸传感器 |
  | `DEV_ID_CAMER` | 0xA7 | 摄像头传感器 |
  | `DEV_ID_GRAY` | 0xA9 | 灰度传感器 |
  | `DEV_ID_GRAY_V2` | 0xB0 | 第二代灰度传感器 |
  | `DEV_ID_NFC` | 0xB2 | NFC 传感器 |

- `KEEP = 0xFF`（保持不动）。
- `build_sensor_update_frame(port_ids: list[int]) -> bytes`：
  - 校验 `len(port_ids) == 8`，否则 `ValueError`。
  - 直接调用现有 `protocol_frame.build_frame(0x32, bytes(port_ids))`。
  - 帧格式：`5A 97 98 08 32 [8字节] [checksum] A5`，checksum = `sum(head) & 0xFF`，
    与现有 `protocol_frame` 完全一致。全 0xFF 样例校验字节 = 0xBB（已验证）。
- `SENSOR_UPDATE_OPTIONS`：供对话框用的 `[(显示名, id值)]` 列表，首项为「保持不动」。

### GUI 层

**`gui/monitor_worker.py`（新增）**
- QThread worker，生命周期独立于部署 worker。
- `start(port, baud)`：打开 `SerialTransport` → `set_data_handler` 接原始字节 →
  喂 `MonitorParser` → 每得到一帧 emit `frame_parsed(dict)`。
- `send_frame(frame: bytes)`：复用当前连接 `write()`，供传感器更新下发。
- signals：`frame_parsed(dict)`、`error(str)`、`state_changed(str)`（connected/disconnected 等）。
- 解析在 RX 后台线程完成（轻量 json.loads），只把结果 dict 经 signal 送主线程；
  **绝不在后台线程碰 Qt widget**。

**`gui/pages/monitor_page.py`（新增）**
- 跟随当前选定产品（启动窗口所选），查 `MONITOR_PROFILES` 得卡片数 / 状态字段 / 是否显示传感器更新。
- 顶部：串口选择（复用 `PortSelector`）+ 开始 / 停止监控按钮；NEW-AI 额外一个「传感器更新」按钮。
- 中部：左 4 + 右 4（或按产品 4/2）张 `SensorCard`，两列布局。
- 底部：`HostStatusBar`。
- **节流刷新**：`frame_parsed` 只写「最新帧」缓存；`QTimer`（100ms）定时把最新缓存渲染到卡片 +
  状态栏，避免高频上报导致重绘卡顿。
- 遍历 `deviceList`，按 `port` 号定位卡片；缺失 port 或无传感器对象 → 卡片显示「空」占位。

**`gui/widgets/sensor_card.py`（新增）**
- 通用键值卡片（MVP 方案）：标题 = `端口 N · <中文类型名>`；下方把该传感器对象的字段按
  `键: 值` 逐行列出。字段增改无需改代码。定制可视化（色块 / 表盘 / 目标框）留作后续迭代。
- 空状态：标题 `端口 N`，内容显示「空」。

**`gui/widgets/host_status_bar.py`（新增）**
- 按产品的 `status_fields`（label + json 点路径）显示主机信息；取不到显示 `--`。
- 电量等带 `%` 与否各产品原样显示，不做单位换算。IMU（`mem`）组合显示 yaw/pitch/roll。

**`gui/dialogs/sensor_update_dialog.py`（新增，或置于 pages 下）`SensorUpdateDialog`**
- 8 行，每行：`端口 N` + 下拉框（选项 = `SENSOR_UPDATE_OPTIONS`，默认「保持不动」）。
- 「下发」按钮 → `build_sensor_update_frame([...])` → `MonitorWorker.send_frame()` → 提示「已下发」。
- 即发即忘（fire-and-forget），不等 ACK；效果在后续监控帧体现（卡片类型变化）。

### 产品参数化表 `MONITOR_PROFILES`

```python
MONITOR_PROFILES = {
  "NEW-AI": {
    "ports": 8,
    "status_fields": [
      ("主机", "MAC"), ("版本", "version"), ("电量", "bat"),
      ("运行状态", "NewAiState"), ("IMU", "mem"), ("音量", "voic"), ("Heap", "heap"),
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
```
- 状态字段用简单点路径（如 `adc.bat`）取嵌套值。
- 传感器类型名映射（JSON key → 中文名）也在此模块统一维护：
  `big_motor`→大电机、`small_motor`→中电机、`color`→颜色、`ultrasion`→超声波、
  `touch`→触摸、`camer`→摄像头、`gray`→灰度、`gray_v2`→灰度V2、`nfc`→NFC。

## 数据流

```
设备 (USB CDC 持续 USB_printf JSON 行)
   │ 原始字节
   ▼
SerialTransport (已有: RX 线程 + set_data_handler)
   │ data_handler(bytes)   ← RX 后台线程
   ▼
MonitorParser.feed(bytes) → list[dict]   (缓冲半行, 按 \r\n 切, json.loads)
   │
   ▼
MonitorWorker: 每帧 emit frame_parsed(dict)   ← Qt 跨线程 signal 切回主线程
   │
   ▼
MonitorPage: signal 只更新「最新帧」缓存；QTimer(100ms) 渲染
   ├─ 遍历 deviceList → 更新 SensorCard（按 port 定位，空端口占位）
   └─ 顶层字段 → 更新 HostStatusBar（按产品点路径映射）
```

## 错误处理

- 坏 JSON 行 → `MonitorParser` 静默丢弃，继续解析后续。
- 半行 / 跨 chunk → 缓冲保留未完成部分，等下个 chunk 补齐。
- 缓冲上限（64KB 无换行）→ 清空缓冲防膨胀。
- 串口断开 / 打开失败 → worker emit `error(str)`，页面提示并回到未连接状态，按钮复位。
- 未知产品 / 缺 profile → 页面显示提示，不崩溃。
- 传感器更新：未连接（未监控中）时下发按钮禁用，根本发不出。

## 测试（遵循 TDD）

**纯后端单测（不需 Qt）：**
- `MonitorParser`：整行、多行、半行跨 chunk、坏行丢弃、缓冲上限保护、`\n` 与 `\r\n` 兼容。
- `sensor_update`：全 0xFF 组帧 checksum=0xBB；混合类型帧正确；帧头尾 / len / index(0x32) 正确；
  非 8 长度报 `ValueError`。

**GUI 单测（pytest-qt，参照现有 gui 测试）：**
- 产品参数化：切换产品 → 卡片数、状态字段、传感器更新入口显隐正确。
- 帧渲染：喂一帧 NEW-AI JSON → 对应卡片字段、空端口占位、状态栏字段（含 IMU 组合、点路径）正确。
- 节流：快速喂多帧 → timer 仅渲染最新帧。
- `SensorUpdateDialog`：选映射 → 下发 → `send_frame` 收到正确字节序列。

## 交付范围（YAGNI）

- MVP 只做通用键值卡片，不做定制可视化。
- 不做监控数据录制 / 导出（未来迭代）。
- 不做产品页内切换（跟随启动所选产品）。
- 传感器更新仅 NEW-AI，仅即发即忘，不做 ACK 确认。
