# 坑（Pitfalls）

> 迁移自旧知识图谱记忆（2026-07-16）。新增坑请按"现象 → 根因 → 修复 → 验证位置"格式追加/就地更新。

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