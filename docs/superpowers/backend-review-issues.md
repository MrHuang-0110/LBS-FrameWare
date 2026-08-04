# 后端审查问题清单

> 本文件由"后端全面审查与分批修复"计划维护。问题按严重度与批次跟踪，状态：`待处理` / `已修复` / `已验证`。

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

| 编号 | 位置（文件:行号） | 严重度 | 描述 | 状态 |
|---|---|---|---|---|
| — | （待后续审查任务填充） | | | |

<!-- 约定：审查任务按层（传输层 → 协议层 → 编排层）产出问题并追加到上表；修复批次完成任务时把对应行改为"已修复"，全量 pytest 绿后改"已验证"。 -->
