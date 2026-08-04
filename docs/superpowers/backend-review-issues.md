# 后端审查问题清单

> 本文件由"后端全面审查与分批修复"计划维护。问题按严重度与批次跟踪。
> 条目状态：`确认`（已核实存在）/ `待定`（需进一步确认）/ `非问题`（已核实不构成问题，附理由）。
> 批次修复计划完成任务时把对应条目改为 `已修复`，全量 pytest 绿后改 `已验证`。

## 基线摘要（Task 1）

- **基线日期**：2026-08-04
- **状态**：✅ **基线已实测**（主 agent 代跑，2026-08-04）
- **通过数量**：261（`python -m pytest` 全量，30.44s）
- **失败数量**：0（未出现 pytest-qt 退出段错误）
- **段错误说明**：全量测试收尾时可能出现 pytest-qt 退出段错误（码 `-1073740791` / `0xC0000409`），属已知环境问题（`doc/pitfalls.md:23-26`），非本项目 bug，应以各测试文件实际结果为通过基准，不要尝试修复。
- **参考证据（非本次运行，勿作为基线）**：`.pytest_cache/v/cache/lastfailed`（旧缓存，2026-07-17 生成）记录 8 个上次失败的 GUI 测试，全部位于 `tests/gui/`，本次全量运行 261 个测试全部通过，说明旧失败已被修复或缓存过期：
  - `tests/gui/test_connection_selector_signals.py::test_target_changed_fires_on_ble_scan_populate`
  - `tests/gui/test_connection_selector_signals.py::test_make_transport_returns_ble_when_ble_selected`
  - `tests/gui/test_port_selector_async.py::test_show_event_triggers_async_scan`
  - `tests/gui/test_port_selector_async.py::test_refresh_does_async_re_scan`
  - `tests/gui/test_port_selector_async.py::test_empty_ports_returns_none`
  - `tests/gui/test_main_window.py::test_monitor_nav_enabled`
  - `tests/gui/test_main_window.py::test_navigate_to_monitor_page`
  - `tests/gui/test_main_window.py::test_leaving_monitor_stops_it`

## 问题清单

### 批次 1：传输层（serial_transport / ble_transport / ble_scanner）

审查日期：2026-08-04。无回归验证：本子任务执行环境无 bash/git、`irmia-devkit/test_runner` 被安全层拦截（与 Task 1 相同），Step 3 由主 agent 代跑（命令见简报）。

#### 1. serial_transport.py

| 编号 | 位置（文件:行号） | 严重度 | 描述 | 状态 |
|---|---|---|---|---|
| T2-S1 | serial_transport.py:99-101 | minor | RX 循环裸 `except Exception: sleep(0.05); continue`：若 read/in_waiting 持续抛错（串口拔出后未 stop_rx、句柄失效），形成**无日志、无退出条件**的忙循环（20 次/秒静默空转），排障无痕，线程永不退出。 | 确认 |
| T2-S2 | serial_transport.py:50,58,166 | minor（非问题） | 三处裸 except 均合理有界：:50 DTR/RTS 拉低失败无害（驱动/FakeSerial 差异）；:58 close() 失败不应上抛（句柄已被系统回收时无法补救）；:166 wait_for_reopen 打开重试有 `retries` 上限 + `delay` 间隔，非忙循环，最终返回 False 由上层报"设备未重新枚举"。**理由**：均有明确防御意图且失败有界，无需改动。 | 非问题 |
| T2-S3 | serial_transport.py:104-108 | minor | `_data_handler(bytes(chunk))` 调用在 try 块之外：handler 抛异常（如 MonitorParser 解析 bug）会直接杀死 daemon RX 线程且无任何迹象，协议层将静默等待超时。建议：handler 调用包 try/except 记录日志，或线程主体外层包 try/except 防止线程死亡。 | 确认 |
| T2-S4 | serial_transport.py:61-64 | minor | `write()` 仅检查 `_serial is None`，不检查 `is_open`：端口已 close/拔出后 write 抛底层异常（无友好提示）；wait_for_reopen 失败后 `_serial` 是已关闭旧句柄。建议：write 前检查 `self.is_open` 并抛 RuntimeError。 | 确认 |
| T2-S5 | serial_transport.py:29-35 | minor | `_port_present()` 调用 `comports()` 无异常保护；wait_for_reopen 的 while 循环（:133-137/:142-145）直接调用它，若 USB 枚举抛异常（Windows 驱动栈/权限）会冒出 wait_for_reopen，绕过失败返回语义。建议：内部 try/except 并记录日志。 | 确认 |
| T2-S6 | serial_transport.py:157 | minor（非问题） | `self._serial.is_open = True`：`_serial is None` 且 pyserial 未装且无 reopen_factory 时抛 AttributeError，被 :166 的 except 吞掉后重试 retries 次最终返回 False——不崩溃。**理由**：生产路径必有 pyserial（走 :155 分支），仅测试注入 `SerialTransport(None)` 可达且已有防御；可改为显式 `raise RuntimeError("pyserial not installed")` 提升可诊断性。 | 非问题 |

#### 2. ble_transport.py

| 编号 | 位置（文件:行号） | 严重度 | 描述 | 状态 |
|---|---|---|---|---|
| T2-B1 | ble_transport.py:165-174 | major | **BLE 断线检测缺失**：`_connected` 仅由 open/_try_connect/close 置位，设备侧断开（距离、关机）后 `is_open` 仍返回 True、`_rx_queue` 无数据、write 直到下次调用才抛错——上层误判链路健康。复用 BLE 链路的监控场景完全无感知。建议：`_RealBleakClient` 暴露 bleak 的 `set_disconnected_callback`，`_connect` 注册回调置 `_connected=False` 并日志；write 异常时同步置 False。 | 确认 |
| T2-B2 | ble_transport.py:271-278,288-294 | major | **`close()` 在 GUI 主线程同步等待最多 10s+2s**：`_run(self._disconnect(), timeout=10.0)` + `_stop_loop` 的 `join(2)`。connection_selector.disconnect() 在主线程调用，设备无响应时 UI 冻结最多 12s（B1 未修时设备已断但 `_connected=True` 会真实走到该路径）。建议：disconnect 放入后台线程执行或将其超时降至 2-3s；close 幂等可重入。 | 确认 |
| T2-B3 | ble_transport.py:165-174 | minor | `_on_notify` 在 asyncio 线程读 `_data_handler`/`_rx_queue`，主线程 `set_data_handler`（:180-187）与 `_try_connect`（:265）改写——无锁。GIL 保证单属性读写原子，但存在逻辑交错：handler 切换瞬间 notify 读到旧值入队/残留队列。实际影响小（BLE handler 模式仅 monitor 复用链路场景使用；queue 模式残留无人读）。建议：`threading.RLock` 串行化 handler 切换与队列清空。 | 确认 |
| T2-B4 | ble_transport.py:265 | minor | `_try_connect` 在 `_connect()`（含 `start_notify` 订阅）返回后重建 `self._rx_queue = queue.Queue()`：订阅已生效→队列替换的窗口内，notify 回调可能把字节入旧队列而丢失。对比串口版（重建前已 stop_rx，无并发）这是 BLE 独有窗口（微秒~毫秒级）；重连后设备立即回传（复位 boot 消息/YMODEM 'C'）时可能丢首字节，协议层以超时/重传兜底。建议：队列重建挪到 start_notify 之前。 | 确认 |
| T2-B5 | ble_transport.py:132,235,274 | minor | 线程生命周期魔法数：`_run` 默认 30.0（connect/write 超时）、disconnect 两处 10.0，含义分散无注释。核实含义：30s 给慢速 BLE 连接留裕量（GUI 在后台线程，不冻结 UI）；10s 给断开兜底。合理性：可接受，但 wait_for_reopen 重试时每次先耗 10s（reopen_retries 次叠加），应在常量注释说明权衡。建议：提取命名常量并注释。 | 确认 |
| T2-B6 | ble_transport.py:19-34 | minor（非问题） | `_ble_log`/`LBS_BLE_DEBUG` 机制：模块加载缓存开关+路径（避免热路径读环境变量）、纯旁路异常吞掉——**规范化方式可复用**（可抽为共享 debug_log 模块供 serial 等复用）。小建议：每次 `open(...,"a")` 重开文件句柄且无 rotation，调试开启且高频 notify 时有句柄抖动，可用单例句柄/logging 优化。 | 非问题 |
| T2-B7 | ble_transport.py:151 | minor（非问题） | `max(int(mtu_size,23)-3, 20)`：BLE 标准 ATT MTU 最小 23 → mtu-3 ≥ 20，max 恒等 mtu-3，逻辑正确。**理由**：与 BLE 规范及 bleak 协商值约定一致；仅当某后端报告异常 mtu<23 时 max 会强制 20 超写（理论场景）。可加注释说明。 | 非问题 |
| T2-B8 | ble_transport.py:222-226 | minor（非问题） | `response=False` 时 50ms 片间延迟在 loop 线程 `await sleep`（阻塞本 transport 全部排队任务）：128B YMODEM 块约 7 片 ≈ 350ms/块，仅影响自身链路吞吐。**理由**：与链路约定一致（BLE 透传防缓冲溢出，deployer 已改用 128B 块），非缺陷。 | 非问题 |
| T2-B9 | ble_transport.py:165-171,104 | minor | `_on_notify` 调 `self._data_handler(b)` 无异常保护：handler 抛异常 → asyncio 回调异常（loop 打印后继续，不崩），该批字节丢失且反复打印。与 T2-S3 同类。建议：handler 调用包 try/except 并记录日志。 | 确认 |

#### 3. ble_scanner.py

| 编号 | 位置（文件:行号） | 严重度 | 描述 | 状态 |
|---|---|---|---|---|
| T2-SC1 | ble_scanner.py:38 | minor（非问题） | `asyncio.run(disc(timeout))` 在已有事件循环线程调用会抛 RuntimeError。**核实结论**：scan() 的两个生产调用路径——GUI 扫描按钮（`_ScanWorker` 跑在 `_scan_thread` QThread）与 BLE 重连兜底（`wait_for_reopen` 里 `self._scanner(...)` 跑在 DeployWorker 的 QThread）——均是无 asyncio 事件循环的后台线程；GUI 主线程的 Qt exec 也不是 asyncio 事件循环，即便在主线程调 asyncio.run 也不会抛 RuntimeError（真实风险只是 5s 阻塞卡 UI，已被后台线程规避）。**理由**：现有路径不会触发；建议在 docstring 注明"必须在无运行中 asyncio loop 的线程调用"。 | 非问题 |
| T2-SC2 | ble_scanner.py:42-57 | minor（非问题） | dict 形态假设 `for dev, adv in devices.values()` 恒为二元组、name/rssi 取 adv 优先。**理由**：与 bleak 3.x `return_adv=True` 返回结构一致（bleak-backend-fix-report 已实测），值结构异常会被 :39 的 except 吞掉表现为空列表，不崩溃。建议：异常时记录日志便于排障。 | 非问题 |
| T2-SC3 | ble_scanner.py:39-40 | minor | 所有扫描异常一律静默返回 `[]`（适配器关闭、结构异常等），GUI 无法区分"没有设备"与"扫描失败"。建议：增加可选的失败原因上报（如返回 (list, err) 或回调），或至少记录一条日志。 | 待定 |

### 批次 2：协议层（transfer_protocol / protocol_frame / ymodem）

审查日期：2026-08-04。无回归验证：本子任务执行环境无 bash/git、`irmia-devkit/test_runner` 被安全层拦截（read_only=false，与 Task 2 相同），Step 3 由主 agent 代跑（命令见简报）。

#### 1. transfer_protocol.py

| 编号 | 位置（文件:行号） | 严重度 | 描述 | 状态 |
|---|---|---|---|---|
| T3-T1 | transfer_protocol.py:126-127 | minor | `_last_frame_timeout` 用 dict 直接索引 `[self.last_frame_ack]` 无默认值：`last_frame_ack` 来自产品 YAML 配置（profile.py:18,74 原样透传、无枚举校验），配置写错（如带空格 "wait_2s " / 非法值 "wait_5s"）时在升级中途抛 KeyError——此时设备已复位进入升级模式，升级中断且无友好提示，需手动恢复。建议：改为 `.get(self.last_frame_ack, 2.0)` 回退默认值，并在 `__init__` 校验枚举值。 | 确认 |
| T3-T2 | transfer_protocol.py:147,149,183,218,228 | minor | 5 处 `print(f"[DEBUG] ...")` 调试残留：无开关、无门控，YmodemProtocol 已有 `log_cb` 参数（:134）却未使用（CustomFrameProtocol 已用 log_cb，风格不一致）；数据块路径每包打印一次（大固件几百~几千行 stdout 刷屏）。建议：统一转 `log_cb` 调用或环境变量门控。 | 确认 |
| T3-T3 | transfer_protocol.py:172 | major | `seq = seq + 1 if seq < 255 else 1`：seq 回绕 255→1 **跳过 0**，与 YMODEM 标准 8 位计数器 255→0 回绕不一致。触发条件：1024B 块固件 >255KB、128B 块(BLE 链路)脚本 >32KB 时进入回绕。若设备端严格校验 seq 连续性（期望 255 后为 0），会持续 NAK 直至重试耗尽上传失败；simulator `_read_packet`（tests/simulator.py:162-180）剥掉 seq 不校验，该路径无测试覆盖。建议：改为 `seq = (seq + 1) & 0xFF`（255→0），并在模拟器增加 seq 校验测试。**待确认**：真机接收端是否校验 seq 连续性。 | 待定 |
| T3-T4 | transfer_protocol.py:185,207-227 | minor | 数据块阶段设备回 NAK（CRC 校验失败请求重传，YMODEM 标准行为）时 `_wait_control` 不识别 0x15：非 CAN/非期望/非可打印字符，落入 :226「其它非期望控制字节：继续等」分支，等满 `ack_timeout` 超时后才触发重传——语义等价但每个坏块多耗一个超时周期；且 simulator `_read_packet` 不校验 CRC，NAK 分支无任何测试覆盖。建议：`_wait_control` 对 NAK 显式短路（立即触发重传），simulator 增加 CRC 错包模拟。 | 确认 |
| T3-T5 | transfer_protocol.py:44 | minor | `FOLDER_CMD_MAP[folder_name]` 直接索引无防护：`folder_name` 来自产品 YAML 的 `folders` 列表（deployer.py:78-81 遍历），配置了 map 之外的文件夹名（如 "apps"）时 KeyError 中断升级，与 T3-T1 同类（外部配置输入未校验）。建议：`.get` + 友好报错，或加载配置时校验。 | 确认 |
| T3-T6 | transfer_protocol.py:89,97,109,212 | minor（非问题） | 4 处 `max(0.05, _remaining())` 超时魔法数一致性已核实：字面一致、语义正确（最小轮询间隔 50ms，防止 deadline 归零后 read_byte(timeout=0) 忙轮询空转）。**理由**：无行为缺陷，仅建议提取命名常量并注释以提升可维护性，非必须改动。 | 非问题 |
| T3-T7 | transfer_protocol.py:146 | minor（非问题） | `b"ymodem update fmware\r\n"` 中 "fmware" 拼写为**已知协议约定**：与 tests/simulator.py:97（`b"fmware" in line` 判定固件会话）及真机固件共用，改动会导致握手失败。**理由**：必须保持原样，**禁止改动**。 | 非问题 |

#### 2. protocol_frame.py

| 编号 | 位置（文件:行号） | 严重度 | 描述 | 状态 |
|---|---|---|---|---|
| T3-P1 | protocol_frame.py:32-36 | minor | `build_frame` 不校验 data 类型：传 `str` 时 `len(data)` 能通过 MAX_DATA_LEN 检查（str 有 len），随后 `head + data`（bytes + str）抛 TypeError；传 `bytearray`/`memoryview` 同理。生产调用方均传 bytes 不会触发，但接口契约无保护，误用即崩溃且报错信息指向拼接行而非入参。建议：入口加 `isinstance(data, bytes)` 校验并抛带参数说明的 TypeError。 | 确认 |
| T3-P2 | protocol_frame.py:39-51 | minor（非问题） | `parse_frame` 不校验 src/dst（SOURCE/DEST 字段）。**理由**：真机 ACK 帧 src/dst 与主机顺序相反（见 transfer_protocol.py:79-82 注释与 tests/test_custom_frame_protocol.py:72-78 实测），校验反而会拒绝合法真机 ACK，是协议约定而非缺陷。 | 非问题 |

#### 3. ymodem.py

| 编号 | 位置（文件:行号） | 严重度 | 描述 | 状态 |
|---|---|---|---|---|
| T3-Y1 | ymodem.py:34 | minor（非问题） | 填充字节 0x1A（SUB/Ctrl-Z）硬编码。**理由**：YMODEM/XMODEM 标准规定数据块不足块长时以 0x1A 填充，是协议必需而非魔法数；tests/test_ymodem.py:20 已断言填充正确。 | 非问题 |
| T3-Y2 | ymodem.py:29-36 | minor（非问题） | `make_packet` 无 seq 范围校验，`seq & 0xFF` / `(~seq) & 0xFF` 静默截断。**理由**：8 位取模即 YMODEM 协议定义（seq 为 mod-256 计数器），tests/test_ymodem.py:29-31 已验证 255 回绕补码正确；seq 的调用方回绕逻辑偏差单独跟踪于 T3-T3。建议：docstring 注明取模语义，避免未来调用方误解。 | 非问题 |

### 批次 3：编排/业务层（deployer / pika_compiler / sensor_update / monitor_parser / profile / monitor_profiles）

审查日期：2026-08-04。无回归验证：本子任务执行环境无 bash/git、`irmia-devkit/test_runner` 被安全层拦截（与 Task 2/3 相同），Step 3 由主 agent 代跑（命令见简报）。

#### 1. deployer.py

| 编号 | 位置（文件:行号） | 严重度 | 描述 | 状态 |
|---|---|---|---|---|
| T4-D1 | deployer.py:83-86 | minor | **行为确认①（YMODEM 固件只发第一个文件）= 有意行为**。`sorted(glob("*"))` + `break` 只发一个文件：NEXT-AI 是唯一 ymodem 产品，`folders: [__single__]`（products.yaml:47）即"单文件固件"约定，fwlib 目录实际只放单个 atk_f103.bin，tests/test_deployer.py:80-102 亦依赖"取第一个文件"语义。**但缺防御**：目录混入多余文件（README/旧版本 bin）时按字典序取首个可能发错文件；目录为空/仅子目录时零文件发送仍返回 done（与 T4-D2 同类）。建议：按扩展名（.bin）过滤 + 校验恰好一个文件，或注释显式声明单文件约定。 | 确认（有意行为，建议加固） |
| T4-D2 | deployer.py:78-81,87 | minor | **行为确认②（custom_frame 对不存在的目录静默跳过）= 应告警（需修复）**。`if sub.exists()` 跳过缺失目录且无任何提示：用户误以为全部文件夹已升级；极端情况（folders 全部缺失）仅执行 enter→reconnect→空 finish_session 仍上报 done。NEW-AI/SPARK-AI 当前 folders 与 fwlib 子目录均对齐（app/music/boot/config/version、app/version），风险来自固件目录与配置不同步（如发布新版本缺目录）。建议：对缺失目录 log 警告或 error 提示缺失列表；全部缺失时不应报 done。 | 确认（需修复） |
| T4-D3 | deployer.py:4-13 | minor | PySide6 缺失桩 `Signal.connect` 仅保存单个 `_fn`，多 connect 静默覆盖，且桩缺 disconnect/is_connected 等 API。**影响面已核实**：CLI（cli.py:41-43，三个不同 signal 各连一槽）、测试（test_deployer/test_worker 单连接）、GUI（真 PySide6，桩不生效）——当前无触发路径；但破坏 PySide6 Signal 多槽语义，未来 CLI/测试对同一 signal 二次 connect 会静默丢槽。建议：桩改列表存储 _fns（connect 追加、emit 遍历）并补 disconnect/is_connected。 | 确认（建议补全桩） |
| T4-D4 | deployer.py:45,53-54 | minor（非问题） | BLE 降级参数与 pitfalls 一致性核实：chunk 200（:45）与 doc/pitfalls.md「BLE 下发长脚本第一帧无 ACK 超时」修复一致（帧长 207B≤MTU244 不拆片）；block 128（:53）与 tests/test_deployer.py:111-118 断言及注释引用的 pika_deploy.py BT_YMODEM_BLOCK 一致；ack 90.0（:54）为 BLE YMODEM 慢链路 ACK 等待，无 pitfalls 直接佐证但设计合理。**理由**：参数均有测试/注释佐证、行为一致。建议：将 YMODEM 侧参数（128 块/90s ack）补记入 pitfalls（当前仅记录 custom_frame chunk 200）。 | 非问题 |
| T4-D5 | deployer.py:89-92,114-117 | minor | `error.emit` + `raise` 双通道上报的契约问题：update_firmware/deploy_script 失败时先 emit error 再抛异常，配合 gui/worker.py:51-59 `run_firmware` 的 except **无条件**补发 error（run_script 有 `opened` 标志防重复、run_firmware 没有），GUI 在升级失败时弹**两次**错误框；test_worker.py 未断言 error 条数故未暴露。建议：worker.run_firmware 参照 run_script 仅在 open 前失败才补发，或 deployer 明确"emit 与 raise 二选一"契约。 | 确认 |
| T4-D6 | deployer.py:82-87 | minor | YMODEM 固件路径对 firmware_dir 无文件/无匹配文件（仅子目录）时零发送仍 finish_session 并报 done——"空升级静默成功"，与 T4-D2 同类（用户无感知）。建议：发送前校验至少一个文件，否则报错。 | 确认 |

#### 2. pika_compiler.py

| 编号 | 位置（文件:行号） | 严重度 | 描述 | 状态 |
|---|---|---|---|---|
| T4-PC1 | pika_compiler.py:14 | minor | `subprocess.run(cmd, capture_output=True, ...)` 无 timeout：编译器（rust-msc.exe）挂起时 deploy_script 无限阻塞——GUI 侧 DeployWorker 永不发 finished、UI 恒显"编译中"；CLI 侧进程挂死。失败路径已有 returncode/输出校验（:16-19），唯独缺超时兜底。建议：加 `timeout=60` 并捕获 `subprocess.TimeoutExpired` 转含命令与超时值的友好 RuntimeError。 | 确认 |

#### 3. sensor_update.py

| 编号 | 位置（文件:行号） | 严重度 | 描述 | 状态 |
|---|---|---|---|---|
| T4-S1 | sensor_update.py:16,18 | minor（非问题） | 常量名 DEV_ID_ULTRASION / DEV_ID_CAMER 拼写非标准（ultrasonic/camera）。**理由**：ID 值 0xA3/0xA7 核实自设备源码（e:/LBS-NEW-AI/Drivers/DataFile/*，见模块 docstring）；monitor_profiles.py SENSOR_NAMES 的 JSON key 亦用 "ultrasion"/"camer" 且与设备端一致（监控映射依赖）；常量名拼写不影响协议字节。改动有被"好心纠正"破坏协议/映射一致性的风险。建议：注释注明"拼写沿袭设备端，勿纠正"。 | 非问题 |

#### 4. monitor_parser.py

| 编号 | 位置（文件:行号） | 严重度 | 描述 | 状态 |
|---|---|---|---|---|
| T4-M1 | monitor_parser.py:17-27 | minor | 缓冲上限 MAX_BUFFER=64K 仅「无换行」时清空：超长行**最终带换行**时（设备异常输出一行 >64K 且以 \r\n 结尾）可撑破上限——while 循环会完整 partition 出超长行，内存峰值=最长行长度、防护语义被绕过；tests/test_monitor_parser.py:39-42 仅覆盖"无换行超上限"路径。功能上超长行 json.loads 失败会静默丢弃（不崩），但缓冲膨胀防护失效。建议：while 循环内对 partition 出的行超 MAX_BUFFER 时直接丢弃并计数（或截断），补充"超长行带换行"测试。 | 确认 |

#### 5. profile.py

| 编号 | 位置（文件:行号） | 严重度 | 描述 | 状态 |
|---|---|---|---|---|
| T4-PR1 | profile.py:34-40 | minor | `_to_bytes` 用 `.decode("unicode_escape")` 二次转义：YAML 双引号字符串已被 yaml.safe_load 转义（`"\\r\\n"`→CRLF），unicode_escape 对已转义文本无操作，但会解释全部 Python 转义（\xHH/\uHHHH/\U/\N 等）——配置含反斜杠字面（YAML 单引号写法或 \\ 转义）时可能误转义；Python 3.12+ 对非法 \U 序列抛 UnicodeDecodeError 使 load_profiles 崩溃。当前 products.yaml 全部双引号且无反斜杠，**现网配置安全**。建议：改为受控替换（仅解释 \r \n \t \\ 等）或直接 `val.encode("utf-8")`（YAML 双引号已处理转义），并加单引号含反斜杠场景测试。 | 确认 |
| T4-PR2 | profile.py:56,61 | minor（非问题） | templates 回退 `_resolve(base, Path(firmware_dir).parent / "templates")` 使用**未 resolve** 的原始 YAML 字符串。**理由**：对照 tests/test_profile_resolve.py:78（test_templates_dir_falls_back_when_absent）已核实——常规配置（firmware_dir="./products/X/fwlib"）下 Path(...).parent 与"先 resolve 再取父级"结果完全等价（相对路径最终经 _resolve 规整、绝对路径原样），测试通过；唯一差异场景为 firmware_dir="." / ".."（Path(".").parent 与 resolve 后 .parent 不同），当前无实际配置触发且语义无定论。建议：回退前先 `_resolve(base, firmware_dir)` 再取父级以统一边界语义（非必须）。 | 非问题 |

#### 6. gui/pages/monitor_profiles.py

| 编号 | 位置（文件:行号） | 严重度 | 描述 | 状态 |
|---|---|---|---|---|
| T4-MP1 | monitor_profiles.py 全文 | minor（非问题） | 纯数据文件 + 3 个纯函数辅助。**理由**：get_by_path（点路径嵌套取值，任一层缺失返回 None）、sensor_display_name（get 兜底原 key）、get_host_state_path（按 label 匹配）均为确定性纯函数，无 IO/无状态/无异常路径，确认无逻辑风险。附注（维护性，非缺陷）：SENSOR_NAMES 与 sensor_update.py SENSOR_UPDATE_OPTIONS 重复维护设备显示名/ID（新增设备需同步两处，有漂移风险）；get_host_state_path 以 "运行状态" 文本 label 耦合 status_fields 数据，改动 label 名会静默失效。 | 非问题 |

<!-- 约定：后续批次（协议层 → 编排层）审查产出追加到本文件；批次修复任务完成时把对应行改为"已修复"，全量 pytest 绿后改"已验证"。 -->
