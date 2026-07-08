# LBS Firmware Studio · 阶段 1 设计文档

- 日期：2026-07-08
- 状态：待复审
- 范围：仅阶段 1（统一后端 + 极简 GUI），后续阶段（代码编辑器、数据监控）各自再走一轮设计

---

## 1. 概述

### 1.1 目标

构建一个 Windows 桌面程序 **LBS Firmware Studio**，能对三款 PikaPython MCU 产品（NEW-AI / SPARK-AI / NEXT-AI）完成「固件更新」和「Python 脚本下发」，替代现有两个分散的命令行工具，并在真机上端到端验证通过。

### 1.2 背景：已有资产

现有两套独立工具，均为 Python 3.13 + pyserial，无真实 GUI：

| 工具 | 位置 | 支持产品 | 协议 | 可复用核心 |
|---|---|---|---|---|
| pikapython-download-tool | `E:\LBS-Project\pikapython-download-tool` | NEW-AI、SPARK-AI（内部代号 Will_AI） | 自定义帧 `0x5A 0x97 0x98 [len][cmd][data][checksum] 0xA5`，8 位累加和 | `SerialDownloader` 类（toolGUI.py:32-707，干净自包含） |
| NEXT-AI tools | `E:\LBS-Project\NEXT-AI_PROJECT\APP2\tools` | NEXT-AI | YMODEM（SOH/STX + CRC16-XMODEM） | `pika_deploy.ymodem_send`（比 lbs_fw_update 版更健壮）+ `crc16_xmodem` |

三款产品都是 PikaPython 设备，共用编译器 `rust-msc-latest-win10.exe`（`.py` -> `.py.o` 字节码）。差别只在传输协议与进入升级方式。

### 1.3 构建策略

采用分阶段 MVP（方案 A）：

- **阶段 1（本文档）**：统一后端 + 极简但高级感的 GUI，三款产品的固件更新与脚本下发，真机验证。
- **阶段 2**：代码编辑器（QScintilla + 文件树 + 一键编译下发）。
- **阶段 3**：数据监控（JSON 解析 + 端口拓扑仪表盘 + 实时曲线），并接入蓝牙链路。

阶段 1 即把 GUI 骨架与视觉语言定下来，后续阶段继承。

---

## 2. 阶段 1 范围

### 2.1 纳入

- 统一后端三层架构（串口层 / 协议层 / 编排层）。
- 三款产品的 `DeviceProfile` 配置，去硬编码路径。
- 自定义帧协议（NEW-AI/SPARK-AI）+ YMODEM 协议（NEXT-AI）两套传输，统一接口；合并现有两套 YMODEM 实现为一份。
- `.py` -> `rust-msc` 编译 -> `.py.o` 下发。
- App Store 风格 GUI：启动产品选择界面 + 主窗口（左功能栏 + 右操作区 + 左上角产品状态）。
- 顺带修复已知坑（见第 8 节）。

### 2.2 不纳入（留给后续阶段）

- 代码编辑器（阶段 2）。
- 数据监控 / JSON 仪表盘（阶段 3）。
- 蓝牙链路（阶段 3，因 NEXT-AI 蓝牙的 JSON 干扰天然与监控耦合）。

### 2.3 成功标准

1. 三款产品各自能用新工具完成一次固件更新 + 一次脚本下发。
2. GUI 视觉高级、操作流畅（App Store 风格）。
3. 后端可脱离 GUI 独立运行（为阶段 2/3 与自动化测试打基础）。
4. 纯协议逻辑与编排层有自动化测试覆盖；真机用例有手动验证清单。

---

## 3. 架构

### 3.1 三层架构

```
┌──────────────────────────────────────────────────┐
│  GUI 层 (PySide6)                                 │ 阶段1: 产品选择 + 功能栏 + 操作区
│  ↓ 调用                                           │ 阶段2: +编辑器  阶段3: +监控仪表盘
├──────────────────────────────────────────────────┤
│  编排层  DeviceDeployer                           │ 产品无关
│   compile() -> connect() -> enter_upgrade()         │ 按 DeviceProfile 驱动
│   -> transfer() -> finish()                         │ 向 GUI 发进度/日志/状态事件
├──────────────────────────────────────────────────┤
│  协议层  TransferProtocol (ABC)                   │ 协议无关
│   · CustomFrameProtocol  (NEW-AI / SPARK-AI)     │ 统一接口:
│   · YmodemProtocol       (NEXT-AI)               │  enter_upgrade / send_file / finish
├──────────────────────────────────────────────────┤
│  串口层  SerialTransport                          │ 平台无关(pyserial)
│   open/close/reconnect/write/read                │ + 后台接收线程 + 数据回调
│   USB 复位重连策略                                │ (为阶段3监控的JSON流预留)
└──────────────────────────────────────────────────┘
```

### 3.2 三个关键设计决断

1. **串口层现在就加「后台接收线程 + 数据回调」**。现有两版都是同步阻塞，阶段 3 监控要实时收 JSON 流，现在预留避免返工。RX 线程把字节路由给"当前 handler"：阶段 1 路由给协议层的 `read_until` 等待循环；阶段 3 切到"监控模式"时路由给 JSON 解析器。
2. **协议层只统一接口契约，不统一协议细节**。YMODEM（文件流式）和自定义帧（带功能码的请求-应答）语义不同，强行合并会出错。
3. **`DeviceProfile` 数据类驱动一切**。把"末帧是否等 ACK / 等多久""波特率""进入升级命令""下发文件夹"等差异做成配置项，统一现有 Python 版（末帧等 30s）与 C 版（不等）的分歧。

### 3.3 三款产品映射

| 产品 | 协议 | 链路（阶段 1） | 进入升级方式 | 下发内容 |
|---|---|---|---|---|
| NEW-AI | 自定义帧 | USB | 发 `0x6F` 帧 + `"RESET_FWLIB"`（不等 ACK，复位重连） | 5 文件夹 `app,music,boot,config,version` |
| SPARK-AI | 自定义帧 | USB | 同上 | 2 文件夹 `app,version` |
| NEXT-AI | YMODEM | USB | 发文本 `"ymodem update fmware\r\n"`（拼写须与设备端 C 代码一致，勿改） | 单个 `.bin` / `.py.o`（多文件时 YMODEM 批次） |

---

## 4. 后端模块

### 4.1 模块总览

| 模块 | 职责 | 依赖 | 复用来源 |
|---|---|---|---|
| `serial_transport` | pyserial 封装 + 后台接收线程 + 复位重连 | pyserial | 两版的 `open_serial` / `reopen_after_reboot` |
| `protocol_frame` | 自定义帧纯函数：构造/解析/校验 | 无（纯 bytes） | `SerialDownloader.build_frame/parse_frame/checksum` |
| `ymodem` | YMODEM 纯函数 + 收发逻辑：CRC16/组包/握手 | `serial_transport` | `pika_deploy.ymodem_send` + `crc16_xmodem`（合并两套） |
| `transfer_protocol` | `TransferProtocol` ABC + 两个实现 | 上面三个 | `SerialDownloader`（自定义帧）、`ymodem` |
| `pika_compiler` | 调 `rust-msc` 把 `.py` 编译成 `.py.o` | subprocess | `compile_file` |
| `deployer` + `profile` | 编排 + 产品配置 + 事件分发 | 全部 | 重写（现有编排层耦合死 GUI 代码） |

### 4.2 关键接口

**串口层**
```python
class SerialTransport:
    def open(self, port: str, baud: int) -> None
    def close(self) -> None
    def write(self, data: bytes) -> int
    def read_until(self, predicate, timeout: float) -> bytes        # 协议层同步等响应
    def set_data_handler(self, handler: Callable[[bytes], None])    # 阶段3: JSON 流走这里
    def wait_for_reopen(self, retries: int, delay: float) -> bool   # USB 复位后重连
    # 内部: 后台 RX 线程把字节喂给「当前 handler」(协议等待 or 数据回调)
```

**协议层**
```python
class TransferProtocol(ABC):
    @abstractmethod
    def enter_upgrade_mode(self, transport: SerialTransport) -> None: ...
    @abstractmethod
    def send_file(self, transport, path: Path, on_progress: Callable[[int,int],None]) -> None: ...
    @abstractmethod
    def finish_session(self, transport) -> None: ...

class CustomFrameProtocol(TransferProtocol):    # NEW-AI / SPARK-AI
    # 额外: send_folder() -- 自定义帧是文件夹级语义
    # 末帧 ACK 行为由 profile.last_frame_ack 驱动 (wait_2s / wait_30s / skip)

class YmodemProtocol(TransferProtocol):         # NEXT-AI
    # USB 1024B 块; 内部用合并后的 ymodem 收发逻辑
```

**纯函数模块（最该先抽、最好测）**
```python
# protocol_frame.py -- 零 IO
def build_frame(cmd: int, data: bytes) -> bytes
def parse_frame(raw: bytes) -> tuple[int, bytes]      # (cmd, data)
def calculate_checksum(frame_without_tail: bytes) -> int

# ymodem.py 的纯函数部分
def crc16_xmodem(data: bytes) -> int
def make_packet(seq: int, payload: bytes, block_size: int) -> bytes
```

**编排层 + 配置**
```python
@dataclass
class DeviceProfile:
    name: str                      # "NEW-AI" / "SPARK-AI" / "NEXT-AI"
    protocol: TransferProtocol
    baud: int = 115200
    enter_cmd: bytes               # RESET_FWLIB帧 / "ymodem update fmware\r\n"
    folders: list[str]             # NEW-AI:5 / SPARK-AI:2 / NEXT-AI:[单文件]
    chunk_size: int                # USB 248(自定义帧) / 1024(YMODEM)
    ack_timeout: float
    last_frame_ack: str            # "wait_2s" | "wait_30s" | "skip"
    filename_encoding: str         # "gbk" | "utf-8"
    compiler_path: Path
    script_dirs: dict              # 源.py目录 -> 输出.py.o目录 映射

class DeviceDeployer(QObject):     # PySide6, 用信号跨线程
    progress = Signal(int, int)     # (done, total)
    log = Signal(str)
    state_changed = Signal(str)     # idle/compiling/connecting/transfering/finishing/done/error
    error = Signal(str)

    def compile_scripts(self, profile, py_paths) -> list[Path]    # -> .py.o 列表
    def update_firmware(self, profile, port) -> None              # 固件更新全流程
    def deploy_scripts(self, profile, port) -> None               # 脚本下发全流程
```

### 4.3 线程模型

- **GUI 主线程**：Qt 事件循环，只做 UI。
- **部署工作线程**：`DeviceDeployer` 在 `QThread` 里跑 `compile -> connect -> enter -> transfer -> finish`（串口阻塞 I/O），通过 Qt 信号把进度/日志/状态回主线程。
- **串口 RX 线程**：`SerialTransport` 内部常驻读线程，字节路由给"当前 handler"。这是阶段 1 为阶段 3 预留的关键开关。

### 4.4 配置文件

用 `products.yaml` 取代散落的 `pikacompiler.conf` + `deploy_port.txt` + 各 `CONFIG.txt` 的硬编码路径：

```yaml
products:
  NEW-AI:
    protocol: custom_frame
    baud: 115200
    folders: [app, music, boot, config, version]
    firmware_dir: ./products/NEW-AI/fwlib
    script_dirs: { ./products/NEW-AI/write: ./products/NEW-AI/app }
    last_frame_ack: wait_2s
    filename_encoding: gbk
  SPARK-AI:
    protocol: custom_frame
    folders: [app, version]
    ...
  NEXT-AI:
    protocol: ymodem
    enter_cmd: "ymodem update fmware\r\n"
    last_frame_ack: skip
    ...
compiler_path: ./tools/rust-msc-latest-win10.exe
```

---

## 5. 数据流

### 5.1 两种操作的差别

| 操作 | 输入 | NEW-AI/SPARK-AI 下发内容 | NEXT-AI 下发内容 |
|---|---|---|---|
| 固件更新 | 产品配置里的固件目录 | 全量文件夹：NEW-AI 5 个 / SPARK-AI 2 个 | 单个 `.bin` |
| 脚本下发 | 用户选的 `.py` 文件夹 | 仅 `app` 文件夹（编译出的 `.py.o`） | `.py.o`（YMODEM 批次） |

脚本下发只刷新用户脚本，不碰 boot/config/music，比固件更新轻。脚本下发以**一个 `.py` 文件夹**为单位：选文件夹 -> 编译其中所有 `.py` -> 下发。

### 5.2 固件更新流程

**自定义帧（NEW-AI / SPARK-AI）**
```
1. open(port, 115200)
2. enter_upgrade: 发 0x6F 帧 + "RESET_FWLIB"  -> 不等 ACK（设备会断开复位）
3. close -> 轮询 reopen（最多 5 次）-> 等 5s 设备初始化
4. for folder in profile.folders:          # NEW-AI:5 / SPARK-AI:2
     for file in folder:
       a. 发文件名帧(cmd=文件夹码, data=文件名) -> 等 ACK 0xFD (超时2s, 重试3次)
       b. 分块(248B): 中间帧 0xAA 等ACK / 末帧 0xBB
          末帧按 profile.last_frame_ack: "wait_2s" -> 等2s无应答则跳过（符合需求文档）
5. finish: 设备自行重启 -> close
```

自定义帧功能码：`0xEC`=music, `0xDA`=app, `0xDB`=boot, `0xDC`=config, `0xDD`=version, `0xAA`=数据帧(有后续), `0xBB`=数据帧(末帧), `0xFD`=ACK 成功, `0xFC`=ACK 失败, `0x6F`=固件更新/复位。

**YMODEM（NEXT-AI）**
```
1. open(port, 115200), 关闭 DTR/RTS（避免 MCU 误复位）
2. enter_upgrade: 写 "ymodem update fmware\r\n" -> 等 500ms（设备写 Flash+复位）
3. USB CDC 端口会消失 -> 轮询 reopen（最多 40×3s）
4. transfer(ymodem):
   a. 等 'C'（超时 120s）
   b. 发 block0 头（文件名+大小）-> 等 ACK + 'C'
   c. 发数据块 STX/1024B，不足补 0x1A
   d. EOT -> NAK -> EOT -> ACK -> 'C' -> 空 block0 -> ACK
   e. usb_quick_exit: 读到 "YMODEM OK" 即结束；EOT 阶段 TimeoutError 视为正常完成
5. finish -> close
```

### 5.3 脚本下发流程（三款共用骨架，差异在传输）

```
1. compile: 对所选文件夹内每个 .py，调 pika_compiler.compile(py, out.py.o) -> 得 .py.o 列表
2. open(port, baud)
3. enter_upgrade + 重连   # 同 5.2 的步骤 2-3，按产品协议
4. transfer:
   · NEW-AI/SPARK-AI: 把 .py.o 作为 app 文件夹(cmd=0xDA) 用自定义帧 send_folder 下发
   · NEXT-AI:         用 YMODEM 批次下发 .py.o（单文件即单次会话；多文件连续批次，设备端是否支持见第 11 节待确认项）
5. finish -> close
```

### 5.4 共性抽取：enter_upgrade + 重连

两种协议的「进入升级 + 复位重连」模式相同，只是触发命令和重连参数不同。由 `DeviceProfile.enter_cmd` + `wait_for_reopen(retries, delay)` 驱动，编排层统一调用，协议层只管 `enter_upgrade_mode()` 的具体字节。

### 5.5 进度与日志事件流

```
工作线程(QThread)  ──progress(done,total)──┐
                ──log(str)──────────────── ├──▶  GUI 主线程: 更新进度条/日志/状态灯
                ──state_changed(str)──────┘
                ──error(str)──────────────┘     (出错时工作线程结束, GUI 弹提示)
```

---

## 6. GUI 设计（App Store 风格）

### 6.1 应用流程

```
启动 -> [产品选择界面] -> 选定产品 -> [主窗口: 左功能栏 + 右操作区]
                              ↑                        │
                              └── 左上角"切换产品"可回到此 ┘
```

### 6.2 启动产品选择界面

三个大卡片（NEW-AI / SPARK-AI / NEXT-AI），每卡含产品专属图标、产品名、端口数、协议。浅色背景、圆角阴影、悬停轻浮起、点击进入主窗口。

### 6.3 主窗口

- **左上角**：产品图标 + 产品名 + 连接状态小圆点 + 串口信息（COM 号、波特率）；右侧"切换产品"按钮与"设置"入口。
- **左功能栏**：图标 + 文字导航，激活项浅蓝底蓝字。
  - 固件更新（可用）
  - 脚本下发（可用）
  - 代码编辑（阶段 2，置灰"即将推出"）
  - 数据监控（阶段 3，置灰"即将推出"）
  - 设置（可用：编译器路径、串口默认、产品配置）
- **右操作区**：按选中功能显示具体操作。
  - 固件更新：固件源（profile 配置目录，只读+可改）、进度、日志、开始/停止。
  - 脚本下发：`.py` 文件夹选择 + 待编译文件列表、进度、日志、开始/停止。

### 6.4 视觉方向

- **浅色主题**：背景 `#F5F5F7`，卡片/面板 `#FFFFFF`。
- **强调色**：Apple 蓝 `#0071E3`（主按钮、激活态、进度条）；状态色绿/琥珀/红/灰。
- **卡片**：圆角 ~12px、极轻阴影、悬停轻微浮起。
- **字体**：UI 用 Segoe UI Variable / Inter；文件名/端口/日志用等宽（JetBrains Mono / Cascadia Code）。
- **图标**：每个产品有专属图标；每个功能栏导航项有统一线条风格图标（固件更新=下载箭头、脚本下发=上传/发送、代码编辑=代码括号、数据监控=折线图、设置=齿轮）。具体图标集（SVG 或 QtAwesome）在实现阶段定。
- **留白与层级**：大间距、清晰分组、不堆砌；进度带阶段文字。

### 6.5 阶段 1 组件清单

- 启动界面：产品卡片 ×3（含产品图标）。
- 主窗口：左上产品状态条、左功能栏（含图标）、右操作区（固件源/脚本文件夹选择、文件列表、进度、日志、主按钮）、设置页。

### 6.6 交互细节

- **产品切换**：切换产品时，串口/固件源/脚本文件夹按该产品 `DeviceProfile` 自动填默认值。
- **开始前置校验**：串口未选/文件夹为空/编译器缺失 -> 主按钮禁用并提示原因。
- **过程态**：操作中状态灯变琥珀 + 旋转，控件锁定，停止按钮可用；停止需二次确认。
- **完成/失败**：绿色成功提示 / 红色错误弹窗（带日志定位）。

> 视觉执行（精确配色、设计令牌、样式化组件）在实现阶段用 `ui-ux-pro-max` + `design-system` + `ui-styling` 落地，本文档只定方向。

---

## 7. 错误处理与重传

| 场景 | 策略 |
|---|---|
| 帧 ACK 超时 | 重传该帧，最多 3 次（可配），仍失败则中止并报错 |
| YMODEM NAK | 重发当前块，最多 3 次 |
| USB 复位端口消失 | `wait_for_reopen` 轮询重开（次数/延时由 profile 给），超时则报"设备未返回" |
| 编译失败 | `rust-msc` 退出码≠0 -> 捕获 stderr -> 日志+错误弹窗，中止 |
| 用户停止 | 二次确认 -> YMODEM 发 CAN 取消 / 自定义帧直接关串口 -> 清理状态 |
| 串口权限/不存在 | 打开时区分错误类型，给中文提示 |
| 校验失败/异常帧 | 丢弃坏帧，等下一有效帧（不污染重传计数） |

所有错误经 `DeviceDeployer.error` 信号回主线程，GUI 弹带原因+日志定位的提示。

---

## 8. 阶段 1 顺带修复的已知坑

| 坑（来自现有代码） | 修复 |
|---|---|
| Python 末帧 ACK 等 30s（与需求文档矛盾） | 改 `wait_2s`（profile 可配） |
| 无重传机制 | 加 max_retries=3 |
| 两套 YMODEM 重复 | 合并为一份（以 `pika_deploy.ymodem_send` 为基） |
| 文件名 gbk 硬编码 | 编码可配（utf-8/gbk），按产品默认 |
| 硬编码路径 `E:\NewAiProject\...` | `DeviceProfile` + `products.yaml` |
| `compile_log.txt` 7.6MB 无轮转 | 日志限大小/轮转 |
| `toolGUI.py` 死 GUI 代码 | 不复用，全新后端 |
| `deploy_bt_port.txt` 引用但缺失 | 配置统一进 yaml（阶段 3 蓝牙时） |

> "fmware" 拼写错误**保留**——须与设备端 C 代码一致，改了反而连不上。

---

## 9. 测试策略

按 TDD 流程，能自动化的全自动化；硬件交互部分用手动矩阵 + 设备模拟器补足。

### 9.1 单元测试（pytest，纯逻辑，无硬件）

- `protocol_frame`：build/parse/checksum 往返、最大长度、坏校验、坏帧头帧尾。
- `ymodem`：`crc16_xmodem` 用已知向量验证、`make_packet` 填充与序号 255->1 回绕、block0 头。
- `pika_compiler`：mock subprocess 验证参数与错误处理。
- `DeviceProfile`：从 yaml 加载、产品切换。

### 9.2 集成测试（mock 传输层，无硬件）

- `SerialTransport`：用虚拟串口/pyserial mock 测 RX 线程路由、`read_until`、重连。
- `TransferProtocol`：mock transport 测 enter_upgrade/send_file/finish 时序、NAK 重传、末帧 wait_2s。

### 9.3 设备模拟器（新建，关键资产）

一个 Python 脚本模拟设备端：按自定义帧/YMODEM 协议应答 ACK、收帧、校验。让集成测试无需真机即可跑通完整流程。阶段 3 还能模拟 JSON 上报。

### 9.4 真机手动矩阵（HITL，无法 CI）

3 产品 × (固件更新 + 脚本下发) = 6 个用例，逐个在真机验证，出测试清单。

---

## 10. 后续阶段（占位，不在本 spec 范围）

- **阶段 2**：代码编辑器。在"脚本下发"右侧内嵌 QScintilla 编辑器 + 文件树，支持语法高亮、一键编译下发、（可选）设备 API 自动补全。
- **阶段 3**：数据监控。设备主动上报 JSON（NEW-AI 8 端口 / SPARK-AI 4 端口 / NEXT-AI 2 端口，每端口可挂电机/超声波/颜色/触碰/摄像头等，外加电量/内存/运行状态）。做端口拓扑仪表盘 + 实时数值曲线（pyqtgraph）。串口层切换到"监控模式"路由 JSON 流。同时接入蓝牙链路（含 NEXT-AI 蓝牙 JSON 干扰过滤）。

---

## 11. 待定项与风险

- **蓝牙**：阶段 1 只做 USB，蓝牙延后到阶段 3。若实际需要阶段 1 即含蓝牙，需另开范围。
- **NEXT-AI 多文件脚本下发**：文件夹含多个 `.py` 时，编译出多个 `.py.o` 用 YMODEM 批次发送；批次语义需在实现时与设备端确认（设备是否支持连续多文件接收）。
- **设备模拟器**：作为新资产投入，但回报高（无硬件回归测试 + 阶段 3 复用）。
- **真机验证依赖**：阶段 1 验收必须有三款真机与对应固件/脚本可用。
