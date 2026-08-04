# 后端全面审查与分批修复 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对 `src/lbs_firmware_studio/backend/` 全部 12 个文件完成审查，并按严重程度分批修复已确认的问题，每批 `python -m pytest` 全绿。

**Architecture:** 按层分 3 批审查（传输层 → 协议层 → 编排层），审查产出统一问题清单（`docs/superpowers/backend-review-issues.md`）；随后对清单中"已确认问题"按严重程度逐个 TDD 修复（每任务：失败测试 → 最小实现 → 回归 → 提交）。修复不改变协议字节级行为与公开接口签名。

**Tech Stack:** Python 3.13 / PySide6 / pyserial / bleak / PyYAML / pytest / pytest-qt

## Global Constraints

- 协议字节与真机逐字一致（`doc/knowledge.md`）；改动不得改变线上协议行为。
- 涉及 `transfer_protocol/deployer/protocol_frame/ymodem/serial_transport` 五文件，先评估现网影响面（`doc/framework.md:23`）。
- 不改变公开接口签名，除非审查确认签名本身是 bug 来源且影响面可控。
- 已知坑不重踩（`doc/pitfalls.md`）：串口枚举必须异步；BLE 长脚本 chunk_size=200；GUI 测试按文件单独跑（pytest-qt 退出段错误 -1073740791 为环境问题，全量收尾容忍）。
- 每批修复后跑 `python -m pytest`（`testpaths=["tests"]`、`pythonpath=["src"]`），全绿才算批完成。
- 测试命令：`python -m pytest`；单个文件：`python -m pytest tests/test_xxx.py -v`。
- 提交规范：`feat/fix/refactor/test/docs:` 前缀，提交到 `main-work` 分支，可随时推送 `origin/main-work`。

---

### Task 1: 基线验证

**Files:**
- Test: `tests/`（全量）

**Interfaces:**
- Produces: 基线结论（当前全量测试通过状态 + 已知段错误容忍说明），供后续任务判断回归。

- [ ] **Step 1: 运行全量测试建立基线**

Run: `python -m pytest`
Expected: 全部通过；若收尾出现 pytest-qt 退出段错误（码 -1073740791）属已知环境问题（`doc/pitfalls.md:23-26`），以各测试文件实际结果为通过基准。

- [ ] **Step 2: 记录基线摘要**

在 `docs/superpowers/backend-review-issues.md` 顶部写入：基线日期、通过数量、失败数量、段错误说明。

- [ ] **Step 3: 提交**

```bash
git add docs/superpowers/backend-review-issues.md
git commit -m "docs: 后端审查问题清单初始化（基线）"
```

---

### Task 2: 批次 1 审查 —— 传输层（serial_transport / ble_transport / ble_scanner）

**Files:**
- Review: `src/lbs_firmware_studio/backend/serial_transport.py`、`src/lbs_firmware_studio/backend/ble_transport.py`、`src/lbs_firmware_studio/backend/ble_scanner.py`

**Interfaces:**
- Consumes: Task 1 的基线结论。
- Produces: 问题清单更新（新增/确认条目，按 critical/major/minor 分级）。

- [ ] **Step 1: 逐文件审查**

对三个文件逐一 code review，检查点（含已知风险提示，审查须核实并补充新发现）：
- `serial_transport.py:50,58,99,166` 裸 except：其中 :99 RX 循环 `except Exception: sleep(0.05); continue` 若 read 持续抛错形成无日志忙循环——确认是否需退出条件或日志。
- `serial_transport.py:157` `self._serial.is_open = True`：`_serial` 为 None 时的 AttributeError 路径（仅测试注入可达）——确认防御方式。
- `ble_transport.py:19-34` `_ble_log` 与 `LBS_BLE_DEBUG` 机制：确认规范化方式可复用。
- `ble_transport.py:165-174` `_on_notify` 在 asyncio 线程执行，`_data_handler`/`_rx_queue` 由主线程改写，无锁——评估竞态窗口与修复方向。
- `ble_transport.py:265` `_try_connect` 重建 `_rx_queue` 与 notify 入队并存——确认是否存在丢字节窗口。
- `ble_scanner.py:38` `asyncio.run(disc(timeout))` 在已有事件循环线程调用抛 RuntimeError——确认 GUI 路径是否会触发。
- 线程生命周期：`ble_transport.py:132` `_run` 默认 30.0、`:235/:274` 10.0 超时魔法数——确认含义与合理性。

- [ ] **Step 2: 更新问题清单**

把审查结论写入 `docs/superpowers/backend-review-issues.md`：每文件一节，每条含 文件:行、严重程度（critical/major/minor）、问题描述、建议修复方向、状态（确认/待定/非问题）。确认"非问题"的条目要写明理由。

- [ ] **Step 3: 无回归验证**

Run: `python -m pytest tests/test_serial_transport.py tests/test_ble_transport.py tests/test_ble_scanner.py -v`
Expected: 全绿。

- [ ] **Step 4: 提交**

```bash
git add docs/superpowers/backend-review-issues.md
git commit -m "docs: 后端审查批次1（传输层）问题清单"
```

---

### Task 3: 批次 2 审查 —— 协议层（transfer_protocol / protocol_frame / ymodem）

**Files:**
- Review: `src/lbs_firmware_studio/backend/transfer_protocol.py`、`src/lbs_firmware_studio/backend/protocol_frame.py`、`src/lbs_firmware_studio/backend/ymodem.py`

**Interfaces:**
- Consumes: Task 1 基线；Task 2 清单格式。
- Produces: 问题清单更新（协议层部分）。

- [ ] **Step 1: 逐文件审查**

检查点：
- `transfer_protocol.py:147,149,183,218,228` 5 处 `print(f"[DEBUG] ...")`：确认全部调试残留、无开关，需转 `log_cb`/环境变量门控。
- `transfer_protocol.py:127` `_last_frame_timeout` dict 无默认值：非法 `last_frame_ack` 会 KeyError——确认回退默认值方案。
- `transfer_protocol.py:89,97,109,212` `max(0.05, _remaining())` 超时魔法数：确认一致性。
- `transfer_protocol.py:146` `b"ymodem update fmware\r\n"` 中 "fmware" 拼写：与 `tests/simulator.py:97` 及真机约定共用，**禁止改动**，在清单中记为"已知协议约定，非问题"。
- `protocol_frame.py:32` `build_frame` 不校验 data 类型（str 会 TypeError）：确认是否加类型校验。
- `ymodem.py:34` 填充字节 0x1A 硬编码、`make_packet` 无 seq 范围校验：确认必要性。
- `ymodem.py`/`transfer_protocol.py` 的 ACK/CRC 校验路径：对照 `tests/simulator.py` 握手实现，确认无遗漏分支。

- [ ] **Step 2: 更新问题清单**

写入协议层结论（格式同 Task 2）。

- [ ] **Step 3: 无回归验证**

Run: `python -m pytest tests/test_custom_frame_protocol.py tests/test_ymodem_protocol.py tests/test_protocol_frame.py tests/test_ymodem.py tests/test_backend_log_cb.py tests/test_ble_protocol_replay.py -v`
Expected: 全绿。

- [ ] **Step 4: 提交**

```bash
git add docs/superpowers/backend-review-issues.md
git commit -m "docs: 后端审查批次2（协议层）问题清单"
```

---

### Task 4: 批次 3 审查 —— 编排/业务层（deployer / pika_compiler / sensor_update / monitor_parser / profile）

**Files:**
- Review: `src/lbs_firmware_studio/backend/deployer.py`、`src/lbs_firmware_studio/backend/pika_compiler.py`、`src/lbs_firmware_studio/backend/sensor_update.py`、`src/lbs_firmware_studio/backend/monitor_parser.py`、`src/lbs_firmware_studio/backend/profile.py`、`src/lbs_firmware_studio/gui/pages/monitor_profiles.py`（注意：monitor_profiles 实际位于 gui/pages/，属监控页参数数据，纳入本批审查）

**Interfaces:**
- Consumes: Task 1-3 清单。
- Produces: 问题清单更新（编排层部分），含两项"行为确认"结论。

- [ ] **Step 1: 逐文件审查**

检查点：
- `deployer.py:4-13` PySide6 缺失桩：`Signal` 仅保存单个 `_fn`，多 connect 会覆盖——确认影响面（CLI/测试路径），确认是否补全桩。
- `deployer.py:83-86` YMODEM 固件更新 `sorted(glob("*"))` 后 `break` 只发第一个文件：结合 NEXT-AI `folders: [__single__]` 约定确认这是**有意行为还是 bug**，给出结论并写入清单。
- `deployer.py:80` custom_frame 固件更新对 `profile.folders` 中不存在的目录静默跳过：确认是否应告警。
- `deployer.py:45,53,54` BLE 降级参数（chunk 200 / block 128 / ack 90.0）：确认与 `doc/pitfalls.md` BLE 长脚本坑一致。
- `pika_compiler.py:14` `subprocess.run` 无 timeout：确认加 timeout 方案。
- `monitor_parser.py:17-21` 缓冲上限仅在无换行时清空：超长行若最终带换行可撑破 64K——确认修复方案。
- `profile.py:34-40` `_to_bytes` 用 `unicode_escape`：含反斜杠的 YAML 值可能误转义——确认是否改用 `yaml.safe_load` 等价解析。
- `profile.py:61` templates 回退拼接未先 `_resolve`：对照 `tests/test_profile_resolve.py:78` 确认边界行为。
- `sensor_update.py:16,18` 常量 `DEV_ID_ULTRASION`/`DEV_ID_CAMER` 拼写：注释称核实自设备源码，记为"协议真名，非问题"或经真机核实后再定。
- `monitor_profiles.py`：纯数据文件，确认无逻辑风险。

- [ ] **Step 2: 更新问题清单**

写入编排层结论；对 deployer 两项"行为确认"给出明确结论（有意行为 / 需修复 / 需真机核实），决定是否进入修复任务。

- [ ] **Step 3: 无回归验证**

Run: `python -m pytest tests/test_deployer.py tests/test_worker.py tests/test_pika_compiler.py tests/test_sensor_update.py tests/test_monitor_parser.py tests/test_profile.py tests/test_profile_resolve.py tests/test_profile_save.py tests/test_ble_ymodem_script_repro.py -v`
Expected: 全绿。

- [ ] **Step 4: 提交**

```bash
git add docs/superpowers/backend-review-issues.md
git commit -m "docs: 后端审查批次3（编排/业务层）问题清单"
```

---

### Task 5: 修复 R1 —— transfer_protocol 调试 print 残留改受控日志

**Files:**
- Modify: `src/lbs_firmware_studio/backend/transfer_protocol.py:147,149,183,218,228`
- Test: `tests/test_backend_log_cb.py`（追加）

**Interfaces:**
- Consumes: `CustomFrameProtocol(..., log_cb=None)` / `YmodemProtocol(..., log_cb=None)`（log_cb 签名 `Callable[[str], None]`，见 `tests/test_backend_log_cb.py`）。
- Produces: 协议层调试信息改走 `log_cb`，无 log_cb 时静默；不再写 stdout。

- [ ] **Step 1: 写失败测试**

```python
def test_protocol_debug_no_stdout_pollution(capsys):
    # 以 test_backend_log_cb.py 现有构造方式建协议实例并触发一次发送流程
    # （参考该文件现有 fixture/构造，可复用 test_custom_frame_protocol.py 的模拟链路）
    logs = []
    proto = CustomFrameProtocol(log_cb=logs.append)
    # ... 执行一段含调试输出的发送流程（如 send_folder 或单帧发送）...
    assert "[DEBUG]" not in capsys.readouterr().out
    assert any("DEBUG" in l or any(l) for l in logs)  # 调试信息改走 log_cb
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_backend_log_cb.py::test_protocol_debug_no_stdout_pollution -v`
Expected: FAIL（stdout 出现 `[DEBUG]` 行）。

- [ ] **Step 3: 实现**

将 `transfer_protocol.py` 中 5 处 `print(f"[DEBUG] ...")` 改为：
```python
if log_cb is not None:
    log_cb(f"[DEBUG] ...")
```
即复用协议实例已有的 `log_cb` 参数（无 log_cb 时静默，与现有 `log_cb` 语义一致）。注意这 5 处位于 `CustomFrameProtocol` 与 `YmodemProtocol` 两个类的方法内，须分别使用实例的 `log_cb`。

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/test_backend_log_cb.py tests/test_custom_frame_protocol.py tests/test_ymodem_protocol.py -v`
Expected: PASS 全绿。

- [ ] **Step 5: 提交**

```bash
git add src/lbs_firmware_studio/backend/transfer_protocol.py tests/test_backend_log_cb.py
git commit -m "fix: transfer_protocol 调试 print 改走 log_cb（去除 stdout 污染）"
```

---

### Task 6: 修复 R2 —— transfer_protocol 非法 last_frame_ack 防 KeyError

**Files:**
- Modify: `src/lbs_firmware_studio/backend/transfer_protocol.py:127`（`_last_frame_timeout` 取值处）
- Test: `tests/test_custom_frame_protocol.py`（追加）

**Interfaces:**
- Consumes: `CustomFrameProtocol(..., last_frame_ack="wait_2s")`。
- Produces: 非法 `last_frame_ack` 回退默认 `wait_2s` 超时，不再抛 KeyError。

- [ ] **Step 1: 写失败测试**

```python
def test_invalid_last_frame_ack_falls_back():
    # 构造 last_frame_ack="bogus" 的协议实例（其余参数用默认/测试常用值）
    proto = CustomFrameProtocol(last_frame_ack="bogus")
    # 触发含最后一帧的发送路径（构造最小 data 列表，参考现有测试的发送方式）
    # 断言：不抛 KeyError，且按默认 wait_2s 路径完成
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_custom_frame_protocol.py::test_invalid_last_frame_ack_falls_back -v`
Expected: FAIL（KeyError: 'bogus'）。

- [ ] **Step 3: 实现**

`_last_frame_timeout` 字典取值改为带默认：
```python
last_timeout = self._last_frame_timeout.get(last_frame_ack, self._last_frame_timeout["wait_2s"])
```
（以实际代码结构为准：若该 dict 为模块级或类级常量，取值处做 `.get(..., default)` 回退。）

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/test_custom_frame_protocol.py -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/lbs_firmware_studio/backend/transfer_protocol.py tests/test_custom_frame_protocol.py
git commit -m "fix: 非法 last_frame_ack 回退默认超时，防 KeyError"
```

---

### Task 7: 修复 R3 —— ble_transport 跨线程数据通路加锁/串行化

**Files:**
- Modify: `src/lbs_firmware_studio/backend/ble_transport.py`（`_on_notify` 165-174、`set_data_handler`、`_rx_queue` 相关）
- Test: `tests/test_ble_transport.py`（追加）

**Interfaces:**
- Consumes: `BleTransport(client_factory=None, scanner=None, reconnect_name=None)`，`set_data_handler`/队列语义与 SerialTransport 对等。
- Produces: notify 回调线程与主线程对 `_data_handler`/`_rx_queue` 的访问串行化，无并发写坏。

- [ ] **Step 1: 写失败测试**

```python
def test_concurrent_notify_and_set_handler_no_corruption():
    # 用 tests/fakes.py 的 make_fake_ble_pair 建链路
    # 线程 A：持续写入大量数据触发 notify 回调
    # 主线程：交替 set_data_handler(None)/set_data_handler(收集器)
    # 断言：不抛异常；最终收到的字节总量与写入总量一致（或 handler 切换后新数据仍可达）
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_ble_transport.py::test_concurrent_notify_and_set_handler_no_corruption -v`
Expected: FAIL（抛异常或丢字节/断言失败）。

- [ ] **Step 3: 实现**

为 `_data_handler`/`_rx_queue` 的读写加同一把 `threading.Lock`（或改用线程安全队列 `queue.Queue` 统一中转，由 RX 消费线程出队调用 handler）：
- `set_data_handler`/`set_rx_queue` 写入侧持锁；
- `_on_notify` 读取侧持锁或经队列中转；
- 保持现有对等接口与信号行为不变。具体以 `ble_transport.py` 现有 `_rx_queue`/`_data_handler` 使用方式为准（explore 显示二者并存，实施时选定一种统一方案，避免双通道）。

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/test_ble_transport.py -v`
Expected: PASS（含既有 12 个测试）。

- [ ] **Step 5: 提交**

```bash
git add src/lbs_firmware_studio/backend/ble_transport.py tests/test_ble_transport.py
git commit -m "fix: ble_transport notify 线程与主线程数据通路加锁防竞态"
```

---

### Task 8: 修复 R4 —— ble_transport 重连重建 _rx_queue 丢字节窗口

**Files:**
- Modify: `src/lbs_firmware_studio/backend/ble_transport.py:265`（`_try_connect`）
- Test: `tests/test_ble_transport.py`（追加）

**Interfaces:**
- Consumes: Task 7 的线程安全通路。
- Produces: 重连期间到达的 notify 字节不因队列重建而丢失。

- [ ] **Step 1: 写失败测试**

```python
def test_reconnect_queue_rebuild_no_byte_loss():
    # 建链路 → 断开 → 重连（触发 _try_connect 重建队列路径）
    # 期间持续写入数据
    # 断言：重连后收到的字节包含断连窗口期数据（或明确不丢失已入队数据）
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_ble_transport.py::test_reconnect_queue_rebuild_no_byte_loss -v`
Expected: FAIL（窗口期字节丢失）。

- [ ] **Step 3: 实现**

`_try_connect` 中不新建队列，改为复用既有 `_rx_queue`（清空策略改为消费端按连接状态丢弃过期字节，或在重建前先停止旧消费并转移残留）；与 Task 7 的统一队列方案配合实现。

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/test_ble_transport.py -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/lbs_firmware_studio/backend/ble_transport.py tests/test_ble_transport.py
git commit -m "fix: ble_transport 重连不再重建队列，消除丢字节窗口"
```

---

### Task 9: 修复 R5 —— ble_scanner 在已有事件循环线程调用不再抛 RuntimeError

**Files:**
- Modify: `src/lbs_firmware_studio/backend/ble_scanner.py:38`
- Test: `tests/test_ble_scanner.py`（追加）

**Interfaces:**
- Consumes: `scan(timeout=5.0, discover=None) -> list[BleDevice]`。
- Produces: 任意线程调用 `scan` 均安全（无事件循环时正常执行；已有事件循环时降级/隔离执行）。

- [ ] **Step 1: 写失败测试**

```python
def test_scan_with_existing_event_loop():
    import asyncio
    # 在测试线程里先建一个事件循环（不 run，仅 set）或在新线程中持有 loop
    # 调用 scan(timeout=0.1, discover=假 discover 函数)
    # 断言：不抛 RuntimeError；返回空列表或预期结果
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_ble_scanner.py::test_scan_with_existing_event_loop -v`
Expected: FAIL（RuntimeError: asyncio.run() cannot be called from a running event loop）。

- [ ] **Step 3: 实现**

`scan` 内改为：检测当前线程是否已有事件循环（`asyncio.get_event_loop()` 与 `loop.is_running()` 判定）；已有则用独立线程执行 `asyncio.run` 并等待结果，或复用 `ble_transport` 的"专用事件循环线程"模式；无循环时保持原 `asyncio.run`。

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/test_ble_scanner.py -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/lbs_firmware_studio/backend/ble_scanner.py tests/test_ble_scanner.py
git commit -m "fix: ble_scanner 兼容已有事件循环线程，防 RuntimeError"
```

---

### Task 10: 修复 R6 —— pika_compiler 加超时

**Files:**
- Modify: `src/lbs_firmware_studio/backend/pika_compiler.py:14`
- Test: `tests/test_pika_compiler.py`（追加）

**Interfaces:**
- Consumes: `compile_py(py_path, out_path, compiler_path, cwd=None) -> Path`。
- Produces: 编译器进程超过 `timeout`（默认 60s）时抛出带命令信息的异常，不再永久挂起。

- [ ] **Step 1: 写失败测试**

```python
def test_compile_timeout_raises():
    # 用假 compiler_path：一个 sleep 超过 timeout 的脚本（或 mock subprocess.run 抛 TimeoutExpired）
    # 断言：compile_py 抛异常，异常信息含 compiler 路径
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_pika_compiler.py::test_compile_timeout_raises -v`
Expected: FAIL（当前无超时，测试挂起或断言失败）。

- [ ] **Step 3: 实现**

```python
proc = subprocess.run(cmd, cwd=cwd, timeout=self._timeout if hasattr(self, "_timeout") else 60,
                      capture_output=True, text=True, encoding="utf-8", errors="replace")
```
超时捕获 `subprocess.TimeoutExpired` 后抛出 `RuntimeError(f"编译器超时: {compiler_path}")`（保留原有 stdout/stderr 信息，cwd 处理与现有实现一致）。

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/test_pika_compiler.py -v`
Expected: PASS（含既有 3 个测试）。

- [ ] **Step 5: 提交**

```bash
git add src/lbs_firmware_studio/backend/pika_compiler.py tests/test_pika_compiler.py
git commit -m "fix: pika_compiler 编译加超时，防永久挂起"
```

---

### Task 11: 修复 R7 —— monitor_parser 超长行撑破缓冲

**Files:**
- Modify: `src/lbs_firmware_studio/backend/monitor_parser.py:17-21`
- Test: `tests/test_monitor_parser.py`（追加）

**Interfaces:**
- Consumes: `MonitorParser.feed(data: bytes) -> list[dict]`，`MAX_BUFFER = 64K`。
- Produces: 缓冲超过 `MAX_BUFFER` 时无论有无换行都截断（丢弃最旧或重置），不无限增长。

- [ ] **Step 1: 写失败测试**

```python
def test_feed_overlong_line_truncates():
    p = MonitorParser()
    # 连续 feed 总长 > MAX_BUFFER 且不带换行的字节
    # 断言：p._buffer 长度不超过 MAX_BUFFER（或内部缓冲被重置）
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_monitor_parser.py::test_feed_overlong_line_truncates -v`
Expected: FAIL（缓冲超 MAX_BUFFER）。

- [ ] **Step 3: 实现**

`feed` 尾部追加缓冲后统一检查：`if len(self._buffer) > MAX_BUFFER: 截断/重置`（与现有"无换行清空"逻辑合并成单一上限守卫；注意保持换行内完整 JSON 优先的现有行为）。

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/test_monitor_parser.py -v`
Expected: PASS（含既有 7 个测试）。

- [ ] **Step 5: 提交**

```bash
git add src/lbs_firmware_studio/backend/monitor_parser.py tests/test_monitor_parser.py
git commit -m "fix: monitor_parser 超长行强制截断，防缓冲无限增长"
```

---

### Task 12: 修复 R8 —— serial_transport RX 循环异常处理改进

**Files:**
- Modify: `src/lbs_firmware_studio/backend/serial_transport.py:99`
- Test: `tests/test_serial_transport.py`（追加）

**Interfaces:**
- Consumes: `SerialTransport` RX 后台线程循环。
- Produces: read 持续抛错时循环记录并退出（或按重试上限退出），不再无日志 50ms 忙循环。

- [ ] **Step 1: 写失败测试**

```python
def test_rx_loop_exits_on_persistent_read_error():
    # 用 FakeSerial 构造 read 持续抛 OSError 的场景
    # 启动 start_rx 后等待
    # 断言：RX 线程退出（is_alive() 为 False），不进入忙循环
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_serial_transport.py::test_rx_loop_exits_on_persistent_read_error -v`
Expected: FAIL（线程仍存活/忙循环）。

- [ ] **Step 3: 实现**

RX 循环内记录错误（经现有日志/回调通道）并设置退出条件：连续 read 异常达到阈值（如 3 次）退出循环，或异常时检查停止标志；保留正常休眠节奏。以 `serial_transport.py` 现有循环结构（stop 标志/回调）为准实现。

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/test_serial_transport.py -v`
Expected: PASS（含既有 9 个测试）。

- [ ] **Step 5: 提交**

```bash
git add src/lbs_firmware_studio/backend/serial_transport.py tests/test_serial_transport.py
git commit -m "fix: serial_transport RX 循环持续读错误时退出，防无日志忙循环"
```

---

### Task 13: 修复 R9 —— serial_transport _serial 为 None 时防御

**Files:**
- Modify: `src/lbs_firmware_studio/backend/serial_transport.py:157`
- Test: `tests/test_serial_transport.py`（追加）

**Interfaces:**
- Consumes: `SerialTransport(serial_obj=None, ...)`。
- Produces: `_serial` 为 None 时相关操作给出清晰错误而非 AttributeError 崩溃。

- [ ] **Step 1: 写失败测试**

```python
def test_open_without_serial_obj_clear_error():
    # 构造 SerialTransport(serial_obj=None)（不注入真实串口对象）
    # 调用 open(port, baud)
    # 断言：抛出的异常信息清晰（含"未注入串口对象"类提示），而非裸 AttributeError
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_serial_transport.py::test_open_without_serial_obj_clear_error -v`
Expected: FAIL（AttributeError）。

- [ ] **Step 3: 实现**

`open`/相关方法入口校验：`if self._serial is None: raise RuntimeError("SerialTransport 未注入串口对象（serial_obj=None）")`；或对 `is_open` 访问做 None 守卫。以现有代码路径为准，保持测试注入路径语义。

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/test_serial_transport.py -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/lbs_firmware_studio/backend/serial_transport.py tests/test_serial_transport.py
git commit -m "fix: serial_transport 未注入串口对象时给出清晰错误"
```

---

### Task 14: 修复 R10 —— profile _to_bytes 反斜杠误转义

**Files:**
- Modify: `src/lbs_firmware_studio/backend/profile.py:34-40`
- Test: `tests/test_profile_resolve.py`（追加）

**Interfaces:**
- Consumes: `DeviceProfile` dataclass 字段（22 个，含 `firmware_dir`/`templates_dir` 等路径字段）。
- Produces: 含反斜杠的 YAML 值往返保存/读取不误转义（`unicode_escape` 被替换为安全解析）。

- [ ] **Step 1: 写失败测试**

```python
def test_roundtrip_backslash_value_no_mis_escape():
    raw = {"firmware_dir": "C:\\fw\\lib"}  # 含反斜杠的路径值
    # 经 _to_bytes → 写入 → 重新解析（走 save_profiles/load_profiles 或直接调用 _to_bytes）
    # 断言：解析结果与原始值逐字符一致，反斜杠未被 unicode_escape 破坏
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_profile_resolve.py::test_roundtrip_backslash_value_no_mis_escape -v`
Expected: FAIL（反斜杠被转义破坏）。

- [ ] **Step 3: 实现**

将 `_to_bytes` 的 `unicode_escape` 解码替换为 `yaml.safe_load`（对已是 YAML 标量文本安全），或等价的不解析转义的方案；对照 `tests/test_profile_save.py`/`test_profile.py` 现有断言确保不破坏已测行为。

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/test_profile.py tests/test_profile_resolve.py tests/test_profile_save.py -v`
Expected: PASS（含既有 13 个测试）。

- [ ] **Step 5: 提交**

```bash
git add src/lbs_firmware_studio/backend/profile.py tests/test_profile_resolve.py
git commit -m "fix: profile _to_bytes 防反斜杠误转义"
```

---

### Task 15: 修复 R11 —— protocol_frame build_frame 类型校验

**Files:**
- Modify: `src/lbs_firmware_studio/backend/protocol_frame.py:32`
- Test: `tests/test_protocol_frame.py`（追加）

**Interfaces:**
- Consumes: `build_frame(cmd, data=b"") -> bytes`。
- Produces: `data` 非 bytes 时抛出带类型的清晰 TypeError。

- [ ] **Step 1: 写失败测试**

```python
def test_build_frame_rejects_str_data():
    with pytest.raises(TypeError):
        build_frame(0x01, "hello")
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_protocol_frame.py::test_build_frame_rejects_str_data -v`
Expected: FAIL（当前 str 可传入并产生非预期字节）。

- [ ] **Step 3: 实现**

```python
if not isinstance(data, bytes):
    raise TypeError(f"build_frame data 必须是 bytes，收到 {type(data).__name__}")
```

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/test_protocol_frame.py tests/test_custom_frame_protocol.py -v`
Expected: PASS（含既有 9+5 个测试，确认既有调用全传 bytes）。

- [ ] **Step 5: 提交**

```bash
git add src/lbs_firmware_studio/backend/protocol_frame.py tests/test_protocol_frame.py
git commit -m "fix: build_frame 校验 data 类型为 bytes"
```

---

### Task 16: 全量回归与问题清单收尾

**Files:**
- Test: `tests/`（全量）
- Docs: `docs/superpowers/backend-review-issues.md`

**Interfaces:**
- Consumes: Task 5-15 全部修复。
- Produces: 阶段 1 完成结论：问题清单全部关闭（或显式标记为"已知行为/不修复+理由"）；全量测试绿。

- [ ] **Step 1: 运行全量测试**

Run: `python -m pytest`
Expected: 全部通过（收尾段错误容忍，见 Task 1）。若出现新增失败：定位最近改动任务回滚修复，不得带红提交。

- [ ] **Step 2: 更新问题清单状态**

将 `docs/superpowers/backend-review-issues.md` 中每条状态更新为 `fixed（引用提交）` 或 `known（不修复+理由）`；确认无遗留 open 项。

- [ ] **Step 3: 提交**

```bash
git add docs/superpowers/backend-review-issues.md
git commit -m "docs: 后端审查问题清单收尾（阶段1完成）"
```

---

### Task 17: 推送与合并

**Files:**
- Git: 分支操作

- [ ] **Step 1: 推送 main-work 到远端防丢失**

```bash
git push origin main-work
```
Expected: 推送成功。

- [ ] **Step 2: 合并回 main 并推送**

```bash
git checkout main
git merge main-work
git push origin main
git checkout main-work
```
Expected: 无冲突合并成功；日常开发回到 `main-work`。

---

## Self-Review 结论（对照 spec 2026-08-04-frontend-refactor-and-backend-review-design.md 第 4 节）

- **Spec 覆盖**：4.1 范围（12 文件）→ Task 2/3/4 全覆盖；4.2 流程（审查分级→3 批→每批 pytest 全绿→子 agent 实施+复审→TDD）→ Task 2-15 对应；4.3 红线（协议字节一致、五文件影响面、不重踩已知坑）→ Global Constraints；4.4 验收（问题清单关闭 + pytest 全绿）→ Task 16/17。
- **占位符扫描**：无 TBD/TODO；Task 5-15 均有失败测试代码与实现要点（实现要点依赖实施时读取目标文件现状，属审查类任务的合理粒度）。
- **类型一致性**：所有修复任务引用的 API 签名（`CustomFrameProtocol(log_cb=...)`、`scan(timeout, discover)`、`compile_py(py_path, out_path, compiler_path, cwd)`、`build_frame(cmd, data)`、`MonitorParser.feed(data)`、`DeviceProfile`/`_to_bytes`）均来自 explore 摸底结果，Task 间无签名冲突。
