# 坑（Pitfalls）

> 迁移自旧知识图谱记忆（2026-07-16）。新增坑请按"现象 → 根因 → 修复 → 验证位置"格式追加/就地更新。

## Qt QColor() 无法解析 rgba() 字符串，半透明色须用 #AARRGGBB

- **现象**：主题令牌 `BG_SELECTED = "rgba(34, 211, 238, 0.10)"` 在 QSS 中工作，但 `QColor(theme.BG_SELECTED)`（如 product_selector 的 `painter.fillRect`）`isValid()=False`，选中底渲染失效。
- **根因**：Qt stylesheet 支持 `rgba()`（且 alpha 只接受 0-255 整数或百分比，浮点 `0.10` 会被解析为 0 全透明）；但 `QColor` 构造函数的字符串格式**不支持 `rgba()`**，只认 `#RGB/#RRGGBB/#AARRGGBB/颜色名/rgb()`。同一令牌若既进 QSS 又被 `QColor()` 解析，用 rgba() 必然有一侧失效。
- **修复**：同时被 QSS 与 `QColor()` 使用的半透明令牌一律用 **`#AARRGGBB`**（alpha 在前，如 `#1A22d3ee` = alpha 26≈10% + #22d3ee）；仅 QSS 使用的（如 SUCCESS_BG/WARNING_BG）可保留 `rgba(r,g,b,整数)`。
- **验证位置**：`src/lbs_firmware_studio/gui/theme.py`（BG_SELECTED）；`product_selector.py` 的 `QColor(theme.BG_SELECTED)`；`QColor('#1A22d3ee').isValid()==True, alpha==26`。

## YMODEM 数据块序号 255 后回绕到 0 导致固件被截断

- **现象**：NEXT-AI（YMODEM 协议）固件更新完成后产品不能运行；.bin 单独用 KEIL 烧录正常。固件 283,328B（277 块 × 1024B）超过 255 块。
- **根因**：主机 `transfer_protocol.py` 数据块 seq 用 `(seq + 1) & 0xFF`（255→0）；设备端 `ymodem.c:429-433` 是 `blk_expect++ 后 if==0 回 1`（255→1），seq=0 保留给文件头/结束块。第 256 块发 seq=0 时设备按结束块 ACK 并截断（`ymodem.c:395-400`），固件只写入前 255 块 → 残缺 → 产品起不来。参考工具 `pika_deploy.py:965-968` 注释明确"勿用 &0xFF（255→0）"。
- **修复**：`transfer_protocol.py` 数据块 seq 改为 `seq += 1; if seq > 255: seq = 1`（1..255 循环，跳过 0）。
- **验证位置**：`src/lbs_firmware_studio/backend/transfer_protocol.py`（YmodemProtocol.send_file）；测试 `tests/test_ymodem_protocol.py::test_seq_wraps_255_to_1_skip_0` + `tests/simulator.py`（模拟器同步对齐真机 1..255 回绕、seq=0 当结束块）。
- **同类提醒**：YMODEM 块号 0 永远只用于文件头/结束块，任何发送端实现都不应让数据块落到 0。

## BLE 下发长脚本第一帧无 ACK 超时

- **现象**：SPARK-AI/NEW-AI（custom_frame 协议）蓝牙下发脚本，短脚本（单帧）成功，长脚本（多帧）第一个数据帧就无 ACK 超时。
- **根因**：设备端接收处理能力有限，单帧过长（248B 数据 → 帧长 255B，超 MTU=244 被拆 2 片）时收不全/不处理，不回 ACK。不是 Flash 擦写超时（放大 ack_timeout 到 15s 无效），也不是分片速率（write_response=True 已有 BLE 层背压）。
- **修复**：`deployer._make_protocol` 对 custom_frame + BLE 把 chunk_size 从 248 降到 **200**（帧长 207B ≤ MTU 244，单帧不拆片）。串口仍用 profile.chunk_size(248)。
- **验证位置**：`src/lbs_firmware_studio/backend/deployer.py` 的 `_make_protocol`，is_ble 时 chunk_size=200。

## PyInstaller 冻结 GUI 崩溃只弹通用提示

- **现象**：`console=False`（runw.exe）打包的 GUI 双击崩溃只弹 `Failed to execute script '<name>' due to unhandled exception`，真实 traceback 被吞。
- **抓真实堆栈**：在终端直接运行 exe（`./程序.exe`），stderr 的 Python traceback 仍会打印——定位冻结崩溃根因最快的手段，无需改 spec 开 console。
- **相关坑**：`.spec` 以 `gui/app.py`（相对导入）为顶层脚本时，冻结后作为 `__main__` 无父包报 `attempted relative import with no known parent package`。修复见 `knowledge.md` 打包垫片。

## 串口枚举阻塞主线程导致白屏/被杀进程

- **现象**：`comports()` 在主线程执行可阻塞 40s，Windows 判定无响应杀进程 → GUI 白屏。
- **修复**：串口枚举异步化——`showEvent` 触发后台 QThread 执行 `comports()`，主窗先显示"扫描中..."，枚举完填充。

## pytest-qt 退出段错误（非本项目 bug）

- **现象**：全量测试收尾时 PySide6/pytest-qt 在 Windows 解释器退出报段错误（码 -1073740791），**未改动代码上可复现**。
- **处理**：非本项目 bug，GUI 测试按文件单独跑以容忍该退出问题。

## Qt.Popup 测试 waitExposed 段错误
- **现象**：pytest 中对 Qt.Popup 窗口调 `qtbot.waitExposed(popup)` 直接段错误（-1073740791）崩溃。
- **修复**：改用 `popup.show(); qtbot.wait(20)` 激活布局后再断言（见 test_connection_popup.py::test_product_selector_keeps_visible_height_in_popup）。

## QWidget 容器在竖向布局中高度塌陷为 0
- **现象**：ProductSelector 放进 ConnectionPopup（QVBoxLayout）后容器高度被压成 0，触发器（30px）溢出与下方连接区重叠，视觉上产品选择"消失"。
- **根因**：无内部 layout 的 QWidget 容器 sizeHint 无效 → 竖向布局给 0 高；与阶段 2"宽度被压成 0"同源（当时只修了宽度 `setMinimumWidth(168)`）。
- **修复**：`setFixedHeight(_TRIGGER_H)` 对称修高度（product_selector.py:132-140）。教训：QWidget 容器放进不同布局方向时宽/高都要显式约束。