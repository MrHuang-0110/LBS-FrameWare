# LBS Firmware Studio · Phase 1a 后端真机验证清单 (HITL)

> 目的：在真实 NEW-AI / SPARK-AI / NEXT-AI 设备上验证后端的固件更新与脚本下发端到端可用，并确认末尾评审列出的 4 个真机风险点。
> 后端已通过 33 个自动化测试（用设备模拟器），本清单覆盖模拟器无法验证的真机行为。
> 日期：______  测试人：______  后端提交：`3003140`

## 真机验证进展（更新）

- ✅ **固件更新 3/3 通过**（NEW-AI / SPARK-AI / NEXT-AI），2026-07-09
- 过程中修复的真机 bug：
  1. `winerror 22 (ERROR_BAD_COMMAND)`：重连后设备 USB CDC 未就绪就写入 → 加 `post_reopen_delay`（提交 `1417667`）
  2. `no ACK after 3 retries`：真机 ACK 是 8 字节带 1 data 字节，`_wait_ack` 只认 7 字节 → 改为按帧长动态解析（提交 `dc67cc8`）
  3. CLI 打开串口在 try 外，坏端口抛 traceback → 移入 try（提交 `ace6854`）
- ⏳ **脚本下发 待验证**（用例 2 / 4 / 6）
- ⏳ 风险点 R1–R4 待在脚本下发/大固件时确认

---

## 0. 准备

### 0.1 环境
- [ ] Windows，已装 Python 3.13
- [ ] 在 `e:\LBS-FramWare` 执行过 `python -m pip install -e .`（含 pyserial、PyYAML）
- [ ] 确认编译器就位：`e:\LBS-FramWare\tools\rust-msc-latest-win10.exe` 存在
- [ ] 冒烟自检（无需真机）：
  ```
  cd e:\LBS-FramWare
  python -m lbs_firmware_studio.cli --list
  ```
  预期输出三行：`NEW-AI: custom_frame ...` / `SPARK-AI: custom_frame ...` / `NEXT-AI: ymodem ...`

### 0.2 放置固件与脚本素材（路径自填）

`products.yaml` 期望的目录结构如下。把你的真实素材放进去，或改 yaml 的 `firmware_dir`/`script_dirs` 指向你的路径。

| 产品 | 固件目录 (firmware_dir) | 需含子文件夹 | 脚本源目录 (script_dirs 的 key) |
|------|------|------|------|
| NEW-AI | `./products/NEW-AI/fwlib` | `app, music, boot, config, version` | `./products/NEW-AI/write`（放 `.py`） |
| SPARK-AI | `./products/SPARK-AI/fwlib` | `app, version` | `./products/SPARK-AI/write` |
| NEXT-AI | `./products/NEXT-AI/fwlib` | （单文件，直接放 `.bin`） | `./products/NEXT-AI/write` |

- [ ] NEW-AI 固件目录已就位：`______________________`
- [ ] NEW-AI 脚本 `.py` 已就位：`______________________`
- [ ] SPARK-AI 固件目录已就位：`______________________`
- [ ] SPARK-AI 脚本 `.py` 已就位：`______________________`
- [ ] NEXT-AI 固件 `.bin` 已就位：`______________________`
- [ ] NEXT-AI 脚本 `.py` 已就位：`______________________`

> 备注：脚本下发流程会先用 `rust-msc` 把 `.py` 编译成 `.py.o` 再发送。固件更新直接发 `firmware_dir` 里的文件。

### 0.3 记录设备串口号

先接一款设备，用设备管理器或以下命令确认 COM 号（每次插拔可能变）：
- NEW-AI 串口：`COM___`
- SPARK-AI 串口：`COM___`
- NEXT-AI 串口：`COM___`

> ⚠️ 一次只接一台设备，确保串口未被其他程序（串口助手、旧下载工具）占用，否则会报权限错误。

---

## 命令速查

```
# 固件更新
python -m lbs_firmware_studio.cli --product <名称> --port COM__ --firmware

# 脚本下发（DIR = 含 .py 的文件夹）
python -m lbs_firmware_studio.cli --product <名称> --port COM__ --scripts <DIR>
```

运行时终端会打印 `[状态]`（compiling / connecting / entering_upgrade / reconnecting / transfering / done）、进度 `已发/总数`，以及日志。最后打印 `完成` 且退出码 0 = 成功；`失败: ...` 且退出码 1 = 失败。

---

## 用例矩阵（3 产品 × 2 操作 = 6）

### 用例 1 — NEW-AI 固件更新
```
python -m lbs_firmware_studio.cli --product NEW-AI --port COM__ --firmware
```
- [ ] 状态依次经过 entering_upgrade → **reconnecting** → transfering → done
- [ ] 5 个文件夹 (app/music/boot/config/version) 的文件都发送成功
- [ ] 退出码 0，打印「完成」
- [ ] 设备复位后正常启动、功能正常
- 观察 / 异常：`______________________`

### 用例 2 — NEW-AI 脚本下发
```
python -m lbs_firmware_studio.cli --product NEW-AI --port COM__ --scripts .\products\NEW-AI\write
```
- [ ] 先编译 `.py` → `.py.o`（日志有 compile 行），再发送
- [ ] 状态经过 reconnecting → transfering → done
- [ ] 设备运行新脚本，行为符合预期
- 观察 / 异常：`______________________`

### 用例 3 — SPARK-AI 固件更新
```
python -m lbs_firmware_studio.cli --product SPARK-AI --port COM__ --firmware
```
- [ ] 2 个文件夹 (app/version) 发送成功
- [ ] 状态 reconnecting → transfering → done，退出码 0
- [ ] 设备复位后正常
- 观察 / 异常：`______________________`

### 用例 4 — SPARK-AI 脚本下发
```
python -m lbs_firmware_studio.cli --product SPARK-AI --port COM__ --scripts .\products\SPARK-AI\write
```
- [ ] 编译 + 发送成功，done，退出码 0
- [ ] 设备运行新脚本正常
- 观察 / 异常：`______________________`

### 用例 5 — NEXT-AI 固件更新（YMODEM）
```
python -m lbs_firmware_studio.cli --product NEXT-AI --port COM__ --firmware
```
- [ ] 发送 `ymodem update fmware` 命令后设备进入升级、USB 端口消失
- [ ] 状态出现 **reconnecting**，主机在 40×3s 内重新打开端口
- [ ] 收到 'C' 后开始 YMODEM 传输，进度递增到 100%
- [ ] 传输结束读到「YMODEM OK」，退出码 0
- [ ] 设备复位后运行新固件
- 观察 / 异常：`______________________`

### 用例 6 — NEXT-AI 脚本下发（YMODEM，单文件）
```
python -m lbs_firmware_studio.cli --product NEXT-AI --port COM__ --scripts <含单个.py的目录>
```
- [ ] 编译出 `.py.o`，发送 `ymodem` 命令进入 YMODEM
- [ ] YMODEM 传输完成，done，退出码 0
- [ ] 设备运行新脚本正常
- [ ] （若目录含 >1 个 .py）预期**快速报错**：`multi-file YMODEM script deploy not supported in Phase 1a`，而不是卡住 120s
- 观察 / 异常：`______________________`

---

## 专项风险验证（末尾评审列出的 4 项）

### R1 — YMODEM 'C' 重发（用例 5/6 期间观察）
重连后主机会丢弃旧串口缓冲，靠设备**周期性重发 'C'** 来握手。
- [ ] NEXT-AI 固件/脚本升级能正常收到 'C' 并开始传输（**不**卡到 120s 超时）
- [ ] 如果卡住约 120s 后报「等 'C' 超时」→ 说明设备只发一次 'C'，需在代码里改为「重连后主动触发」。记录：`______`

### R2 — custom_frame 复位帧是否被截断（用例 1/3 期间观察）
主机发完 `RESET_FWLIB` 帧后立即 close 串口再重连；真机上末尾字节可能未发完就被 close。
- [ ] NEW-AI/SPARK-AI 复位可靠（设备确实进入升级模式，重连后传输成功）
- [ ] 如偶发「设备没进入升级/重连后无响应」→ 可能需在 close 前加 flush。记录复现率：`______`

### R3 — DTR 开串口瞬间是否误复位设备
`SerialTransport.open()` 在构造串口后拉低 DTR/RTS，但构造那一刻 DTR 可能已被瞬间置位。
- [ ] 打开串口时设备**没有**意外复位/重启（尤其 NEXT-AI）
- [ ] 如观察到打开即复位 → 需改为「构造时不置位再配置」。记录：`______`

### R4 — NEXT-AI YMODEM 块序号 1..255 回绕
后端 seq 从 1 递增，到 255 后回到 1（跳过 0），与现有工具一致。
- [ ] 传输 **>255 KB**（>255 个 1024 字节块）的固件能完整成功（触发一次回绕）
  - 如固件较小无法触发，可用 NEXT-AI 的 `atk_f103.bin`（约 274KB，能触发）验证
- [ ] 设备接收完整、校验通过
- 观察：`______________________`

---

## 汇总

- 通过用例：___ / 6
- 阻塞问题（需改代码才能进 Phase 1b）：`______________________`
- 非阻塞问题（可延后）：`______________________`
- 4 个风险点结论：R1 `___` R2 `___` R3 `___` R4 `___`

> 全部 6 用例通过、4 风险点无阻塞 → 后端真机验证完成，可进入 Phase 1b（GUI）。
> 若有阻塞问题 → 回到 systematic-debugging 定位根因后修复，再复测。
