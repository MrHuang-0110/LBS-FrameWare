# ECB02 蓝牙(BLE)传输通道 — 设计文档

- 日期：2026-07-14
- 状态：已确认，待实现
- 相关：`docs/superpowers/plans/`（实现计划另出）

## 1. 背景与目标

为 LBS Firmware Studio 增加通过 **ECB02 蓝牙芯片(BLE / GATT)** 连接设备的能力，把蓝牙作为与串口**等价的传输通道**，用于烧录固件 / 下发脚本 / 数据监控。

**能力矩阵（按产品）：**

| 产品 | 协议 | 蓝牙支持范围 |
|---|---|---|
| NEW-AI | custom_frame | 数据监控 + 脚本下发（**不含**固件更新） |
| SPARK-AI | custom_frame | 数据监控 + 脚本下发（**不含**固件更新） |
| NEXT-AI | ymodem | 数据监控 + 脚本下发 + **固件更新**（全支持） |

约束来源：custom_frame 的脚本下发/监控本就不复位、不重连，BLE 上可直接适配；只有 NEXT-AI 固件更新涉及"复位后重连"，BLE 上实现较复杂，故仅 NEXT-AI 蓝牙全开。

**核心设计约束（项目铁律）：**
- 协议字节必须与真机逐字一致（自定义帧头/checksum、YMODEM CRC16-XMODEM，保留 `"ymodem update fmware"` 拼写）。
- 协议层保持纯净、零 IO 耦合，可独立单测。
- 绝不碰真硬件（串口/蓝牙）做测试。
- 串口功能不受蓝牙引入影响。

## 2. 架构总览

采用**鸭子类型对等类**方案（方案 A）：新建 `BleTransport`，方法签名与现有 `SerialTransport` 逐一对等。协议层（`CustomFrameProtocol` / `YmodemProtocol`）与编排层（`DeviceDeployer`）当前就靠鸭子类型接收 transport，因此**协议层与编排层零改动**。

不引入 `Transport` 抽象基类（方案 B）——现有代码无此层，抽 ABC 要改动 `serial_transport.py`/`transfer_protocol.py`/`deployer.py`，在本项目规模下收益有限（YAGNI）。系统级 BLE→虚拟串口（方案 C）在 Windows 上对 BLE 无稳定方案，排除。

```
GUI 层
  connection_selector (串口/蓝牙统一入口, make_transport())
        │ 注入
        ▼
  DeployWorker / MonitorWorker  (已是"传入 transport"构造，天然支持注入)
        │ 鸭子类型
        ▼
  DeviceDeployer  ──►  CustomFrameProtocol / YmodemProtocol   (零改动)
        │ t.write() / t.read_byte()
        ▼
  SerialTransport  或  BleTransport   (方法签名对等)
                              │
                              ▼
                        专用 asyncio 循环线程 + bleak
```

## 3. 组件设计

### 3.1 BleTransport（新建 `backend/ble_transport.py`）

与 `SerialTransport` 方法签名逐一对等：

| 方法 | BleTransport 语义 |
|---|---|
| `open(port, baud)` | `port` 复用为 **BLE 地址字符串**，`baud` 忽略；异步连接 + 自动发现透传特征值 + 订阅 notify |
| `write(data)` | `run_coroutine_threadsafe(write_gatt_char 分片)`，按 MTU 拆分，等完成 |
| `read_byte(timeout)` | 从 `_rx_queue` 取，与 SerialTransport **完全相同** |
| `set_data_handler(h)` | 切换到回调模式（监控页用），notify → `_data_handler(bytes)` |
| `start_rx()` / `stop_rx()` | notify 在订阅时启动；管理状态与队列武装 |
| `close()` | 断开连接 → stop asyncio loop → join 线程（对应 stop_rx 的 join 语义） |
| `is_open` | 是否已连接 |
| `wait_for_reopen(...)` | BLE 版重连：断开→重扫→重连（仅 NEXT-AI 固件更新用），复用 profile 的 reopen_retries/reopen_delay |

**内部机制：**
- 持有一个专用 asyncio 事件循环，跑在独立线程（bleak 是 async 库）。
- 主线程的同步 API（write/open/close）用 `run_coroutine_threadsafe` 把协程投进循环并等待结果。
- bleak notify 回调在循环线程触发，直接把字节 `put` 进 `_rx_queue`（无 handler）或调 `_data_handler(bytes)`（监控模式）——**复用与 SerialTransport 完全相同的队列/回调模型**，故协议层 `read_byte` 拉取逻辑一字不改。

**写分片（BLE 特有）：** 单次 `write_gatt_char` 受 MTU 限制（~20–244 字节）。`write` 内部按协商 MTU 把大 `data` 拆多次 GATT 写。此为**链路层分片，与协议层 chunk_size(248/1024) 正交**——协议层照常发帧，transport 负责安全送达每次 write 的字节。

### 3.2 BleScanner（新建 `backend/ble_scanner.py`）

- `scan(timeout=5.0) -> list[BleDevice]`：内部用 `bleak.BleakScanner.discover()`，返回附近**所有**可连接设备（**不做名称过滤**）。
- `BleDevice`：纯数据类 `(name, address, rssi)`，不含 bleak 对象，便于测试与跨线程传递。
- 扫描跑在 asyncio 循环里，对外暴露同步 `scan()`。

### 3.3 ConnectionSelector（新建 `gui/widgets/connection_selector.py`）

组合控件，串口/蓝牙统一入口：
- 顶部「串口 / 蓝牙」二选一；下方按选择显示：
  - 串口 → 复用现有 `PortSelector`
  - 蓝牙 → BLE 列表（下拉 + 「扫描」按钮，列出 `name (address) RSSI`）
- 对外访问器：
  - `selected_kind() -> "serial" | "ble"`
  - `selected_target() -> str | None`（串口返 COM 名，蓝牙返地址）
  - `make_transport()` → 按 kind 构造 `SerialTransport` 或 `BleTransport`，worker 拿到的永远是鸭子对等 transport，后续流程无分支。
- **共存语义**：同一页面同一时刻用一个 transport，但可自由切换 kind；监控/脚本页各自独立持有 transport，故串口与蓝牙可同时使用。

### 3.4 现有页面接入

- `main_window.py:128` 写死的 `SerialTransport()` → 改为从连接选择器 `make_transport()` 获取。
- `worker.py` / `monitor_worker.py` 已是"传入 transport"构造，**逻辑几乎不动**，仅构造点改由选择器决定。

### 3.5 profile 配置扩展

`products.yaml` 每产品加可选 `ble` 段，`DeviceProfile` 加对应字段（能力**配置驱动**，非硬编码）：

```yaml
NEW-AI:
  # ...现有字段...
  ble:
    enabled: true
    firmware_over_ble: false   # custom_frame 蓝牙不做固件更新
NEXT-AI:
  ble:
    enabled: true
    firmware_over_ble: true    # NEXT-AI 蓝牙全支持
```

## 4. 数据流

**正常收发（脚本下发/监控，所有产品）：**
```
协议层 t.write(frame)
  → BleTransport.write: run_coroutine_threadsafe(write_gatt_char 分片) → 等完成
设备 notify 推送字节
  → bleak 回调(循环线程) → _rx_queue.put(每字节)  [或 _data_handler(bytes) 监控模式]
  → 协议层 t.read_byte(timeout) 从队列取  ← 与串口完全相同
```
协议字节逐字不变——协议层不知道底层是串口还是 BLE。

**NEXT-AI 固件更新的重连（wait_for_reopen 的 BLE 版）：**
1. 发固件进入命令（`ymodem update fmware\r\n`）后，设备复位 → BLE 连接断开（bleak disconnected 回调）。
2. 等待断开确认（对应"端口消失"）。
3. 按同一地址重新扫描 + 重连，带 reopen_retries/reopen_delay 重试。
4. 重连成功后重新订阅 notify、清空队列（对应 start_rx 重新武装）。

## 5. 错误处理

**依赖降级：** `bleak` 加入 `pyproject.toml`。仿 `serial_transport.py` 的 `try: import serial except ImportError`，`ble_transport.py`/`ble_scanner.py` 对 `import bleak` 做保护——未安装时不 crash，UI 选「蓝牙」时提示"未安装蓝牙支持"，串口功能完全不受影响。

**分层错误映射（全部转成走 deployer 的 error 信号）：**

| BLE 失败 | 处理 |
|---|---|
| 扫描超时/无设备 | 返回空列表，UI 提示"未发现设备，请确认已开启并在范围内" |
| 连接失败/超时 | `open()` 抛异常 → worker 现有 except 补发 `error.emit("蓝牙连接失败: ...")`（与"打开串口失败"同路径） |
| 找不到透传特征值 | `open()` 抛明确异常"未发现可透传特征值"，不静默 |
| 传输中途断连 | notify 停止 → `read_byte` 超时 → 协议层现有重传/超时逻辑接管；transport 记断连状态，后续 `write` 立即抛错 |
| MTU 写失败 | `write` 内协程异常上抛 → 协议层 `_send_and_wait` 重传覆盖 |

**NEXT-AI 复位后地址变化风险：** BLE 重连按原地址找不到时，退化为"扫描 + 按设备名匹配"兜底；仍找不到则 `wait_for_reopen` 返回 False → 编排层抛 `device did not re-enumerate`（复用现有错误语义）。兜底策略"地址优先、名字兜底"，需实测校准。

**线程/循环生命周期：** `close()` 必须干净停 asyncio 循环线程（先断连、再 stop loop、再 join），避免退出悬挂线程——对应 SerialTransport stop_rx 的 join 语义。

## 6. 测试策略

延续项目铁律——**绝不碰真蓝牙硬件**，全部用 fake 驱动。

**核心思路：复用现有协议测试资产。** `BleTransport` 与 `SerialTransport` 队列/回调模型相同，做一个 `FakeBleClient`（模拟 bleak 的 connect/notify/write_gatt_char），把现有 `tests/simulator.py` 的 `DeviceSimulator` 应答字节经 notify 回调喂入——**同一套协议一致性测试在 BLE transport 上再跑一遍**，证明协议字节逐字不变。

| 层 | 测试文件 | 验证点 |
|---|---|---|
| Transport 对等性 | `tests/test_ble_transport.py` | write→read_byte 队列往返、set_data_handler 回调、MTU 分片后字节完整、close 干净停线程、is_open 状态 |
| 扫描器 | `tests/test_ble_scanner.py` | fake discover 映射为 BleDevice、空结果、异常降级 |
| 协议复跑 | 复用 `DeviceSimulator` | custom_frame 脚本下发 + YMODEM 在 BleTransport 上字节一致 |
| 重连 | `tests/test_ble_transport.py` | wait_for_reopen BLE 版：断连→重扫→重连、地址兜底、失败返回 False |
| 能力约束 | `tests/test_profile.py` 扩展 | ble/firmware_over_ble 字段加载；custom_frame 产品该字段为 false |
| GUI 选择器 | `tests/gui/test_connection_selector.py` | 切换 kind、make_transport() 按 kind 造对应类（注入 fake）、能力约束置灰；**按文件单独跑** |

**关键手法：** asyncio 循环线程 + 队列桥接是最易出错处，重点测**同步 API 在多线程下的正确性**（write 等待完成、read_byte 超时、close 无悬挂线程），而非测 bleak 本身。

## 7. 影响文件清单

**新增：**
- `src/lbs_firmware_studio/backend/ble_transport.py`
- `src/lbs_firmware_studio/backend/ble_scanner.py`
- `src/lbs_firmware_studio/gui/widgets/connection_selector.py`
- `tests/test_ble_transport.py`、`tests/test_ble_scanner.py`、`tests/gui/test_connection_selector.py`
- `tests/fakes.py` 扩展 `FakeBleClient`

**修改：**
- `pyproject.toml`（加 `bleak` 依赖）
- `src/lbs_firmware_studio/backend/profile.py`（DeviceProfile 加 ble 字段 + 加载）
- `products.yaml`（各产品加 ble 段）
- `src/lbs_firmware_studio/gui/main_window.py`（transport 由选择器构造）
- `src/lbs_firmware_studio/gui/pages/`（监控/脚本页接入连接选择器 + 能力约束置灰）
- `tests/test_profile.py`（ble 字段测试）

**零改动（关键）：** `transfer_protocol.py`、`deployer.py`、`protocol_frame.py`、`ymodem.py`、`serial_transport.py`。

## 8. 打包影响

`bleak` 为新增运行时依赖，PyInstaller 需收集其数据/隐藏导入。`.spec` 的 `hiddenimports` 可能需补 bleak 后端相关模块（Windows：`bleak.backends.winrt`），构建后实测 exe 蓝牙功能。
