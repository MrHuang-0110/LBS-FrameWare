# 知识

> 迁移自旧知识图谱记忆（2026-07-16）。沉淀可复用的方案与调试方法。

## 打包入口垫片（解决冻结后相对导入崩溃）

`.spec` 曾直接以 `gui/app.py`（相对导入）为顶层脚本，冻结后作为 `__main__` 无父包报 `attempted relative import with no known parent package`。修复：新建 `scripts/entry.py` 顶层垫片，以绝对导入调用：

```python
from lbs_firmware_studio.gui.app import main
```

`.spec` 入口改指它；`tests/test_build_plan.py` 的 `test_entry_shim_uses_absolute_import_of_main` 守门。

## BLE 传输调试方法

排查设备不回 ACK 类问题时，在传输层打印原始字节与时间点：

- `ble_transport._on_notify`：打印收到的原始字节；
- `transfer_protocol` 的 `_send_and_wait` / `_wait_ack`：打印发送字节与超时，直接对比"设备对哪些帧回了 ACK、对哪些帧无回应"。

## 冻结崩溃调试

见 `pitfalls.md`"PyInstaller 冻结 GUI 崩溃只弹通用提示"——终端直接跑 exe 拿真实 traceback。

## 测试与验证

- 全量收尾存在 pytest-qt 退出段错误（非本项目 bug），GUI 测试按文件单独跑。
- 协议字节与真机逐字一致；BLE 类问题优先参考设备侧部署脚本（如 `E:\LBS-NEXT-AI\tools\pika_deploy.py`）核对协议行为。
