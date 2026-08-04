# 项目框架

> 迁移自旧知识图谱记忆（2026-07-16），已按当前仓库结构核对。

## 概述

LBS Firmware Studio：PySide6 桌面工具，代码在 `src/lbs_firmware_studio/`，分 **backend/（逻辑层）** 与 **gui/（界面层）**。

## 架构

- **backend/** — 三层：串口/BLE 传输（`serial_transport.py`、`ble_transport.py`、`ble_scanner.py`）→ 协议（`transfer_protocol.py`、`protocol_frame.py`、`ymodem.py`）→ 编排（`deployer.py`、`pika_compiler.py`、`monitor_worker.py`、`monitor_parser.py`、`monitor_profiles.py`）。
- **gui/** — `app.py`（入口）、`main_window.py`、`theme.py`（设计令牌）、`connection_selector.py`/`port_selector.py`（连接）、页面（`pages/`：firmware_page、monitor_page、script_editor_page、settings_page）、组件（`widgets/`：code_editor、sensor_card、log_view、status_bar 等）、对话框（`dialogs/`：sensor_update_dialog）。
- **worker 模式**：耗时 IO（串口/BLE 扫描、建连、下发）放后台线程/QThread，经信号回主线程；`MonitorWorker.start_on(transport)` 可复用外部持久链路（只挂/摘 data_handler）。
- **BLE 通道**：`BleTransport` 方法与 `SerialTransport` 对等（鸭子类型），bleak 3.0.2，异步事件循环封进专用线程，notify 回调推队列。
- **打包**：PyInstaller onedir + `scripts/entry.py` 入口垫片 + `scripts/build.py`；固件库 fwlib 不进分发包；产品固件目录可配（`paths.base_dir()`、`products.yaml`）。

## 关键约定

- Windows + Python 3.13，测试用 `python -m pytest`。
- **GUI 层不碰协议/串口/BLE 链路**，纯逻辑放 backend；设备操作经 worker → deployer。
- 深色主题禁硬编码色值，取 `theme.*` 令牌。
- 耗时 IO 必须放后台线程/QThread，勿阻塞 GUI 主线程。
- 协议层零改动铁律（transfer_protocol/deployer/protocol_frame/ymodem/serial_transport 五文件）——**已被 BLE 通道打破**，改协议文件前先确认是否有现网影响面。

## 分支与协作

- 日常开发在 `main-work` 分支，验证通过后合并回 `main` 并推送。
- 代码修改、代码审查由**子 agent（subagent）**完成。
