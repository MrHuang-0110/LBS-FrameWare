# 设计文档：前端重构 + 后端全面审查（两阶段）

> 日期：2026-08-04
> 状态：已批准（用户确认）
> 工作分支：`main-work`

## 1. 背景与目标

LBS Firmware Studio（PySide6 桌面工具）当前整体功能可用但仍存在较多 BUG，前端存在结构遗留（独立的产品选择启动页、无用的占位页等）。目标：

1. **后端全面代码审查**：`backend/` 全部文件逐一审查，边审边修，修复后测试全绿。
2. **前端重构**：去掉独立产品选择页面，改为顶栏下拉 + 保留卡片视觉的自定义选择器控件；视觉全面翻新（由 ui-ux-designer 子智能体产出设计，主 agent 实施）。

## 2. 需求基线（用户已确认）

| 维度 | 决策 |
|---|---|
| 产品切换形式 | 顶栏下拉 + 保留卡片视觉的选择器控件（ProductSelector） |
| 前端重构深度 | 视觉全面翻新 + 结构重构 |
| 后端审查范围 | 全部 backend/ 文件，分批修复 |
| 审查后处理 | 边审边修 |
| 执行顺序 | 先后端修复，再前端重构（方案 A：两阶段顺序流水线） |
| ui-ux-designer 分工 | 设计产出为主，主 agent 实施 |

## 3. 总体架构（不变式）

保持现有分层不变：`backend/`（传输 → 协议 → 编排）与 `gui/`（页面/组件）严格分离，GUI 不直接碰协议/串口/BLE 链路。两阶段串行：阶段 1 完成后 pytest 全绿再进入阶段 2。

## 4. 阶段 1：后端全面审查与分批修复

### 4.1 审查范围

`backend/` 全部文件：

- 传输层：`serial_transport.py`、`ble_transport.py`、`ble_scanner.py`
- 协议层：`transfer_protocol.py`、`protocol_frame.py`、`ymodem.py`
- 编排层：`deployer.py`、`pika_compiler.py`、`sensor_update.py`、`monitor_parser.py`、`monitor_profiles.py`、`profile.py`

### 4.2 流程

1. 子 agent 对每个文件做 code review，产出问题清单（每条：文件:行、严重程度、影响面、修复建议）。
2. 按严重程度分级：**critical**（崩溃/数据损坏/协议错误）→ **major**（功能异常/竞态）→ **minor**（健壮性/风格）。
3. 按层分 3 批修复：批次 1 传输层 → 批次 2 协议层 → 批次 3 编排层。
4. 每批修复后立即 `python -m pytest`，全绿才进入下一批。
5. 每批修复由子 agent 实施 + 子 agent 复审；修复加回归测试（TDD）。

### 4.3 约束与红线

- 协议字节与真机逐字一致（见 `doc/knowledge.md`），改动不得改变线上协议行为。
- 涉及 `transfer_protocol/deployer/protocol_frame/ymodem/serial_transport` 五文件时先评估影响面（协议层零改动铁律已被 BLE 通道打破）。
- 不改变公开接口签名，除非审查确认签名本身是 bug 来源且影响面可控。
- 已知坑（`doc/pitfalls.md`）不得重踩：串口枚举必须异步、BLE 长脚本 chunk_size 200、冻结崩溃用终端跑 exe 取堆栈。

### 4.4 验收标准

全部问题关闭或显式记录为已知项 + pytest 全绿。

## 5. 阶段 2：前端重构

### 5.1 ui-ux-designer 产出（子智能体，只产文档不改代码）

1. **设计走查**：对现有界面输出问题清单（视觉一致性、可用性、冗余元素、布局缺陷）。
2. **新设计规格**：
   - 设计令牌：颜色 / 间距 / 字号 / 圆角 / 图标（更新 `theme.py`）。
   - 布局结构：顶栏（产品选择器 + 连接区 + 状态）、Activity Bar、页面内容区、底部状态栏的新布局。
   - 组件规格：**ProductSelector**（顶栏下拉 + 卡片视觉）、固件与监控分栏页、代码编辑页、设置页。
3. **产出物**：设计文档（走查结论 + 令牌表 + 组件规格 + 页面线框）。

### 5.2 结构重构（主 agent 实施）

- **删除产品选择页面**：移除 `startup_window.py` 的启动流转——`AppController.show_startup()` 不再出现；启动直接进入主窗口，默认产品为 NEW-AI（与现 `app.py` 行为一致）。
- **新增 `ProductSelector` 组件**：顶栏下拉，弹出面板保留现有卡片视觉（产品名 + 高亮选中态），复用现有 `_Card` 视觉逻辑。
- **MainWindow 持全部产品**：接收全部 profiles，切换产品时重建页面栈与信号连线（清空当前页面状态、停监控），不再整窗切换。
- **清理遗留**：删除 `placeholder_page.py`（无导航目标使用）、`main_window._make_page` 死分支。
- **AppController 简化**：只剩启动入口 + 配置加载，去掉 startup↔main 切换状态机。

### 5.3 数据流（切换产品）

`ProductSelector` 选中新产品 → 主窗口守卫（busy 时禁用选择器）→ 断开旧页面信号 / 停监控 → 重建页面栈 → 加载新 profile → 更新顶栏产品名与状态栏。

### 5.4 错误处理

- 切换时正在下发/监控：选择器禁用（沿用 `_busy` 锁）。
- 产品配置缺失/损坏：启动时给出友好错误而非崩溃。

### 5.5 测试

- 更新现有 GUI 测试（启动流转、切换产品路径）。
- 新增 ProductSelector 选择/切换测试；复用现有 `fakes.py`/`simulator.py`。
- GUI 测试按文件单独跑（pytest-qt 退出段错误已知坑）；最终全量 `python -m pytest` 验证（收尾容忍段错误）。

### 5.6 红线

- GUI 层不碰协议/串口/BLE；设备操作仍经 worker → deployer。
- 深色主题不硬编码色值，全部走设计令牌。
- 测试访问器签名（`header_text()` 等）尽量保持，减少测试破坏面。

## 6. 验收与合并

- 每阶段独立验收（阶段 1：pytest 全绿 + 问题清单关闭；阶段 2：重构完成 + 新旧测试全绿）。
- 按项目规则：日常开发在 `main-work`，验证通过后合并回 `main` 并推送；改动提交到 `main-work` 后可随时推送远端防丢失。
