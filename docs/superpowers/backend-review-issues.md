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

<!-- 约定：后续批次（协议层 → 编排层）审查产出追加到本文件；批次修复任务完成时把对应行改为"已修复"，全量 pytest 绿后改"已验证"。 -->
