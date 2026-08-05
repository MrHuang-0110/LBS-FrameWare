# UI 重构设计文档：设计走查 + 新设计规格

> 日期：2026-08-04
> 类型：前端界面设计（仅文档，不修改源代码）
> 关联规格：`docs/superpowers/specs/2026-08-04-frontend-refactor-and-backend-review-design.md` 第 5 节
> 工作分支：`main-work`
> 审阅代码范围：`src/lbs_firmware_studio/gui/`（app.py / main_window.py / startup_window.py / theme.py / pages/* / widgets/* / dialogs/* / monitor_worker.py / worker.py）+ `tests/gui/*`

---

## 0. 文档地图

| 章节 | 内容 | 读者 |
|---|---|---|
| §1 | 设计走查问题清单（34 条，file:line 定位 + 建议） | 实施 agent |
| §2 | 新设计规格：设计方向与原则 | 实施 agent |
| §3 | 设计令牌表（颜色/字号/间距/圆角/图标/动效，含演进理由） | 实施 agent（theme.py） |
| §4 | 布局与组件规格（顶栏/ActivityBar/内容区/状态栏 + ProductSelector 等组件） | 实施 agent |
| §5 | 页面线框（ASCII） | 实施 agent + 验收 |
| §6 | 实施约束、红线与决策点 | 用户 + 主 agent |
| §7 | 测试影响评估（逐测试文件） | 实施 agent |
| 附录 A | 令牌迁移映射表（旧值 → 新值） | 实施 agent |

**本轮红线（与既有规格一致）**：GUI 不碰协议/串口/BLE；设备操作仍经 worker → deployer；深色主题不硬编码色值、全部走设计令牌；测试访问器签名（`header_text()` 等）尽量保持。

---

## 1. 设计走查问题清单

共 **34 条**，按五类组织。每条：`文件:行` 定位 → 问题 → 建议（标注严重度：🔴 高 / 🟡 中 / 🟢 低）。

### A. 视觉一致性（8 条）

| # | 定位 | 问题 | 建议 | 严重度 |
|---|---|---|---|---|
| A1 | `theme.py:70-116` | QSS 只覆盖了 Widget/Frame/Button/ComboBox/输入框/进度条/ToolTip，**缺 QScrollBar / QMenu / QMessageBox / QDialog / QListWidget 的深色样式** → 滚动条、右键菜单、槽位菜单、错误弹窗都是系统默认浅色，与深色主题强烈割裂 | 新增完整控件族样式：QScrollBar（细条 8px、滑块 BG_INPUT、hover 提亮）、QMenu/QMenu::item（BG_RAISED 底、选中 BG_SELECTED）、QMessageBox/QDialog（BG_EDITOR 底、BORDER 边、圆角）、QListWidget（用于 ProductSelector 弹层，见 §4.2） | 🔴 |
| A2 | `script_editor_page.py:164` | `_mark_dirty()` 用 `setStyleSheet("QPushButton { border: 1px solid ...; }")` 覆盖按钮样式 → 全局选择器把按钮的 hover/背景/圆角基样式全丢掉，只留一个边框，视觉退化 | 不用全局 QSS 覆盖；改为 `setProperty("dirty", True)` + 调用 `style().unpolish/polish` 刷新，或在 QSS 中定义 `QPushButton[dirty="true"] { border: 1px solid ACCENT; color: ACCENT; }` | 🔴 |
| A3 | `monitor_page.py:96`、`connection_selector.py:121`、`status_bar.py:39-40` | 状态提示用文本符号 `"●"` 当状态灯（连接状态点、链路口径提示），字体符号无法随令牌着色/缩放一致，属「emoji 当图标」反模式 | 全部换矢量图标：qta `fa5s.circle`（实心，SUCCESS）/`fa5s.circle-notch`（空心，disabled）/`fa5s.exclamation-triangle`（error），尺寸走新 ICON_* 令牌 | 🟡 |
| A4 | `code_editor.py:126` | 注释色取 `TEXT_DISABLED #6A6A6A`，在 `#1E1E1E` 上对比约 **2.9:1**，低于 4.5:1 可读性门槛，长注释几乎看不清 | 新增令牌 `TEXT_COMMENT #7A9A8A`（深色 IDE 通用注释绿灰）或提亮 `TEXT_DISABLED` 后单独定义注释色；行号底色 `BG_SIDEBAR` 与编辑器 `#1E1E1E` 区分弱，可加深至 `#212121` | 🟡 |
| A5 | `status_bar.py:40`(10px) / `connection_selector.py:292`(14px) / `main_window.py:52`(16px) / `activity_bar.py:39`(24px) | 图标尺寸 10/14/16/24 四处硬编码混用，无图标尺寸令牌，层级不统一 | 新增 `ICON_XS=10 / ICON_SM=14 / ICON_MD=16 / ICON_LG=20 / ICON_XL=24` 令牌，各组件按语义取用（状态点 XS、行内 SM、顶栏/按钮 MD、ActivityBar XL） | 🟡 |
| A6 | `script_editor_page.py:74` | floatbtn 圆角硬编码 `16px`，与 `RADIUS_SM/MD/LG`(6/8/10) 令牌体系脱节；`padding: 4px 12px` 同样硬编码 | 新增 `RADIUS_FULL=16` 令牌（药丸按钮语义），floatbtn 改用令牌；间距改用 `SPACE_SM` | 🟢 |
| A7 | `status_bar.py:38` | 蓝底 `#007ACC` 状态栏上，未连接图标用 `TEXT_DISABLED #4A4A4A`，对比 < 2:1 几乎不可见 | 未连接态图标/文字改用半透明白或 `#C8C8C8`（蓝底专用变体令牌，见 §3.1 的 `STATUSBAR_ON` 组）；连接态 `TEXT_ON_ACCENT` 保留 | 🟡 |
| A8 | `settings_page.py:34-42`（无 margins/spacing）、`monitor_page.py:54-55`(12px)、`host_status_bar.py:16-17`(12/6)、`script_editor_page.py:200-210`(8/16/24)、`status_bar.py:29`(`SPACE_XS+2`) | 间距硬编码散落各文件，8px 节奏未统一落地 | 统一走 `SPACE_*` 令牌：页面内容 margins 一律 `SPACE_LG`、组件间距 `SPACE_SM/MD`、浮层间距 `SPACE_SM`；删除 `SPACE_XS+2` 这类算式 | 🟢 |

### B. 可用性（10 条）

| # | 定位 | 问题 | 建议 | 严重度 |
|---|---|---|---|---|
| B1 | `startup_window.py:8-41` | 产品选择卡：**单击框选、双击进入**，隐喻不明确（无按钮、无说明点击即选中）；`QFrame` 非 focusable，**无 Tab/方向键/Enter 键盘可达**；卡片 `180×140` 固定尺寸，产品名长时溢出 | 组件化进 ProductSelector（§4.2）：单击即选择并关闭弹层（无需双击）、QListWidget 原生键盘导航、focus 环可见；删除 startup 流转 | 🔴 |
| B2 | `firmware_page.py:19` | 「开始固件更新」**无二次确认**，烧录属不可逆高危操作，误触即开始擦写 | 点击时弹确认框（`QMessageBox.question`）：显示目标产品 + 待发送文件夹摘要 + 「确认开始固件更新」；或改用「按住确认」式交互（先选后按）。建议确认框而非双态按钮，保持现有测试语义 | 🟡 |
| B3 | `firmware_page.py:18` | `待发送: -` 用 `-` 表示未初始化，产品未 set 时误导用户以为目录缺失 | 空态文案「待发送: （未选择产品）」；有 profile 后显示真实文件夹列表（现状已正确） | 🟢 |
| B4 | `firmware_page.py:73`、`script_editor_page.py:264` | `on_log` 用**中文关键字**（"失败"/"错误"）猜日志级别，文案一改就失效，且与 backend 日志来源解耦脆弱 | 后端 deployer 的 log 信号若带 level 则透传；否则前端按 `state`（error/transfering/done）推导级别，不解析日志文本 | 🟡 |
| B5 | `monitor_page.py:35,47` vs `main_window.py:54` | **双套串口选择并存**：顶栏 ConnectionSelector 一套、监控页顶部 PortSelector 一套；断连时监控页突然弹出第二套串口控件（`_sync_conn_ui` 可见性跳变），用户困惑 | 移除监控页本页 PortSelector（`_port`/`_port_lbl`），统一走顶栏连接；未连接时监控页顶部显示空态提示条「请先在顶栏连接设备」（§4.5）⚠️ 需用户决策（影响面见 §6.3） | 🔴 |
| B6 | `sensor_card.py:31-37` | 空端口卡片仅显示「端口 N」，**无「无设备」灰态提示**；卡片无最后刷新时间戳，**数据新鲜度不可见**（断流时用户无法区分「无更新」和「正常」） | 空态标题追加灰色「无设备」；卡片角标或标题尾加小字刷新时间（HH:MM:SS，来自帧节流渲染）；断流超阈值（如 2s）卡片整体降透明度 | 🟡 |
| B7 | `monitor_page.py:173-174` | 流式解析出错时 `_on_error` 直接 `QMessageBox.critical` → 一旦设备持续发坏帧会**弹窗风暴**，阻塞操作 | 错误降级为：状态栏红点 + LogView 追加 error 行；仅在「连续 N 次失败」或用户主动操作时弹框 | 🟡 |
| B8 | `script_editor_page.py:240-253` | `save()` 成功只写日志，无**就近视觉确认**；`QMessageBox` 只在失败时弹 | 保存成功：保存按钮短暂显示「已保存 ✓」（QTimer 800ms 复位）或日志行用 success 色（现状有）；建议前者，反馈更近 | 🟢 |
| B9 | `main_window.py:49-50` + `status_bar.py:33,60` | 顶栏产品名与底部状态栏产品名**重复显示**（`set_product`），信息冗余 | 底部状态栏去掉产品名，改显「连接目标 + 部署阶段」；顶栏 ProductSelector 承担产品身份（§4.1/§4.3）⚠️ 影响 test_status_bar（§7） | 🟢 |
| B10 | `theme.py:111-113` | QProgressBar QSS 有 `text-align:center` 但无文本颜色/字体设置，且代码从未 `setFormat` → **百分比数字从不显示**，进度只剩光秃的条 | QSS 补 `color: TEXT_PRIMARY; font-size: FONT_CAPTION`，页面在 `on_progress` 里 `setFormat(f"{pct}%")`；条高 6px 保留（VS Code 风格） | 🟡 |

### C. 冗余元素（5 条）

| # | 定位 | 问题 | 建议 | 严重度 |
|---|---|---|---|---|
| C1 | `monitor_page.py:36-39,159-163` | `_start_btn` 创建后 `setVisible(False)` 永远不显示，但 `_on_worker_state` 仍更新其文本/图标 → **死控件 + 死逻辑** | 删除 `_start_btn` 及其在 `_on_worker_state` 中的两处更新（监控自动启停由顶栏连接驱动，无需手动按钮） | 🔴 |
| C2 | `main_window.py:126` | `_make_page` 的 `PlaceholderPage` 分支是**死分支**（`_NAV` 全 enabled，无导航目标指向占位页） | 删除 `placeholder_page.py` + `main_window.py:126` 分支 + `main_window.py:16` import（规格 5.2 已列） | 🟢 |
| C3 | `theme.py:26` | `PRODUCT_GREEN` 与 `SUCCESS` 同值重复定义，语义别名未解释 | 保留别名但改为注释引用 `PRODUCT_GREEN = SUCCESS`（一行，写明用途=产品名高亮色）；或直接删掉、调用点改用 `SUCCESS` | 🟢 |
| C4 | `theme.py:51-55` vs `status_bar.py:7-11` | 阶段中文文案**两套**：`STAGE_TEXT`（"等待设备重连"/"进入升级模式"）与 `_STATE_TEXT`（"重连中"/"进入升级"），同一状态两处措辞不一致 | 以 `theme.STAGE_TEXT` 为唯一来源，`status_bar._STATE_TEXT` 删除并改用 `theme.STAGE_TEXT`（语义对齐：状态栏阶段文案=页面阶段文案） | 🟡 |
| C5 | `main_window.py:187,189` | 生产路径遗留 `print(f"[DEBUG] _run_deploy: ...")` | 删除；若需诊断日志走 `logging`（debug 级） | 🟢 |

### D. 布局缺陷（5 条）

| # | 定位 | 问题 | 建议 | 严重度 |
|---|---|---|---|---|
| D1 | `main_window.py:58` | 顶栏 `setFixedHeight(40)` 过矮：连接区一行要塞 串口/蓝牙单选 + 下拉 + 扫描 + 连接按钮 + 状态点，加 ProductSelector 后必然拥挤；高 DPI（125%/150%）下更甚 | 顶栏提到 **48px**（§4.1）；连接区与产品区用 1px BORDER 竖分隔线分块；控件垂直居中 | 🔴 |
| D2 | `settings_page.py:34-42` | 页面布局**无 margins/spacing**（`lay.addWidget` 直接贴边），与其它页 16px 边距不一致；「设置」标题是裸 QLabel | 统一 `contentsMargins(16,16,16,16)` + `spacing(12)`；标题用 `FONT_TITLE` + `TEXT_PRIMARY`，下设一行次级说明 | 🟡 |
| D3 | `sensor_card.py:15` | 卡片仅 `setMinimumHeight(120)`，网格内**各行卡片高度由内容决定**，行内不对齐、视觉参差 | 网格改等高：`SensorCard.setSizePolicy(Expanding)` + 内容顶部对齐（`align=Qt.AlignTop`），或 grid 行设置统一最小高；值区用 `tabular figures`（等宽数字）防抖动 | 🟡 |
| D4 | `script_editor_page.py:86-87` | 编辑页日志 `maxHeight 140` 固定矮条，固件页日志可伸缩（`firmware_page.py:55` stretch=1）→ **两页日志交互不一致** | 编辑页日志改为可伸缩（与固件页一致，stretch=1 或允许用户拖高），阶段/进度压缩为单行（§4.4） | 🟡 |
| D5 | `settings_page.py:40` | `save_btn` 默认 stretch 撑满整行宽，视觉差 | 保存按钮右对齐（前面 `addStretch(1)`）或限宽（如 120px 左对齐 + 状态文本同行右侧） | 🟢 |

### E. 组件缺陷（6 条）

| # | 定位 | 问题 | 建议 | 严重度 |
|---|---|---|---|---|
| E1 | `connection_selector.py:23` | RadioButton indicator 12px 偏小（可点区域小、选中环不醒目）；`_RADIO_QSS` 与 `theme.py:99-103` 的 QRadioButton 样式**双份定义**，改一处另一处不同步 | 统一 indicator 14→16px；QSS 收敛到 `theme.app_qss()` 单一来源，删除 `connection_selector.py:20-28` 的模块级重复定义 | 🟡 |
| E2 | `main_window.py:50` | 顶栏产品名用 `setStyleSheet` 行内拼接样式（虽用令牌值但散落组件内） | 产品名样式迁入 ProductSelector 内部（触发器样式集中管理）；MainWindow 不再行内设置 | 🟢 |
| E3 | `activity_bar.py:46,80-84` | QToolButton **无 focus 样式**，键盘 Tab 到图标按钮无任何视觉反馈（a11y 缺陷） | QSS 补 `QToolButton:focus { border: 1px solid ACCENT_FOCUS; border-radius: 4px; }`；`setFocusPolicy(StrongFocus)`；hover 图标提亮到 `ICON_HOVER` | 🔴 |
| E4 | `port_selector.py:75` | 「扫描中...」是**可选假选项**（`data=None`），用户可误选，选中后目标为 None 无反馈 | 占位项 `setEnabled(False)`（灰显不可选）或改用非下拉的 loading 态（按钮禁用 + 下拉禁用） | 🟡 |
| E5 | `host_status_bar.py:14-36` | NEW-AI 7 个状态字段单行排布，窄窗（900px）下**溢出挤压**无策略 | 值区改等宽字体（防数字抖动）；字段过多时允许内部横向滚动或两行换行；`HostStatusBar` 加最小宽度策略 | 🟢 |
| E6 | `log_view.py:13-22` | 日志**无最大行数限制**，长时间监控/多次下发后内存与渲染持续增长 | `append` 时若 `blockCount > 2000` 删除顶部块（`document().findBlockByNumber(0)` 裁剪），或按字符数裁剪 | 🟢 |

> 说明：A3/A5/A6/A8 与 E1/E2 等条目存在交叉，已按「观察点 → 令牌/组件层根治」归类，实施时以 §3（令牌）+ §4（组件规格）为准，无需逐条机械落实。

---

## 2. 新设计规格：方向与原则

### 2.1 设计方向

延续 **VS Code Dark+** 深色开发者工具风格（与项目现状一致，用户已认可），重构围绕四个词：

1. **层次**：背景分层从「几乎贴在一起」改为可辨识（编辑器 #1E1E1E → 侧栏/卡片 #252526 → 顶栏 #2D2D30 → 输入 #3C3C3C），并用 1px 分隔线明确区块边界。
2. **对比**：正文文字提亮到 #E0E0E0、次级 #A8A8A8；注释/禁用态达到可读下限；焦点环用亮蓝 #3FB6FF 全组件可见。
3. **语义**：状态（连接/部署阶段/错误）全部语义化——颜色 + 图标 + 文字三通道，不单靠颜色。
4. **一致**：一套令牌驱动全部组件；一套阶段文案；一套间距/圆角/图标刻度；弹出层（菜单/选择器/对话框）补齐深色样式，消灭「系统白底混入」。

### 2.2 关键取舍（相对现状）

| 决策 | 现状 | 新方案 | 理由 |
|---|---|---|---|
| 产品切换 | 独立启动窗（关窗→开窗） | 顶栏 ProductSelector 下拉（窗内切换） | 规格 5.2 已定；减少上下文断裂 |
| 顶栏高度 | 40px | 48px | 容纳选择器+连接区，抗高 DPI |
| 监控连接入口 | 顶栏 + 本页双套串口 | 仅顶栏（本页空态提示） | 消除双入口困惑（⚠️ 决策点 §6.3） |
| 监控启停 | 隐藏的开始/停止按钮（自动） | 彻底移除按钮，纯自动 + 状态显示 | 自动监控已生效，按钮是死控件 |
| 底部状态栏 | 蓝底 + 连接 + 产品名·阶段 | 蓝底 + 连接 + 阶段（去掉产品名） | 去重，信息更聚焦 |
| 编辑页日志 | 固定 140px 矮条 | 可伸缩（同固件页） | 两页交互一致 |

### 2.3 动效规范（PySide6 可落地）

| 项 | 规范 |
|---|---|
| 时长 | 微交互 120–200ms（hover/选中/弹层开合）；不做 > 400ms 的装饰动画 |
| 缓动 | 进入 ease-out（`QEasingCurve.OutCubic`），退出 ease-in；不动画 width/height/position（Qt 动画 transform 支持有限，改为淡入淡出 + 位移少量） |
| 用途 | 仅表达因果：弹层淡入、选中态切换、按钮 pressed 缩放 0.98（可用 `QPushButton` QSS pressed 模拟，不引入动画框架） |
| 降级 | 检测 Windows「动画显示效果」关闭或 `QApplication.styleHints()` 支持时，跳过动画直接切态；QSS 过渡依赖系统动画设置，默认关闭即自动降级（Qt QSS 无 transition，天然无动画——本规格不强制引入 QPropertyAnimation，除弹层外保持「瞬切 + 状态色」即可） |

> 务实说明：Qt Widgets 的 QSS 不支持 `transition`，纯 QSS 下 hover/选中即瞬时切换。规格不要求为每个 hover 引入动画对象（违背「不过度装饰」），仅 ProductSelector 弹层开合与 busy 态切换可用 `QGraphicsOpacityEffect + QPropertyAnimation`（150ms）做一层质感。

---

## 3. 设计令牌表

### 3.1 颜色令牌（theme.py 演进）

基调：VS Code Dark+ 保持不变，方向是「层次更分明、文字更亮、补全语义色与控件族」。全部令牌以 `theme.py` 模块常量的形式存在（QSS 用 f-string 注入，组件不得再出现裸色值）。

#### 背景分层

| 令牌 | 现值 | 新值 | 用途 | 改动理由 |
|---|---|---|---|---|
| `BG_EDITOR` | `#1E1E1E` | `#1E1E1E`（不变） | 编辑器/页面内容底色 | VS Code 标准，保持品牌辨识 |
| `BG_SIDEBAR` | `#252526` | `#252526`（不变） | 卡片/分组框/侧栏 | 同上 |
| `BG_BAR` | `#333333` | `#2D2D30` | 顶栏 + ActivityBar | VS Code 活动栏标准色；比 #333333 与输入框更易区分，区块边界清晰 |
| `BG_INPUT` | `#3C3C3C` | `#3C3C3C`（不变） | 输入框/按钮底 | 保留 |
| `BG_HOVER` | `#2A2D2E` | `#37373D` | hover 底 | 提亮一档，hover 可辨（现状与 BG_SIDEBAR 几乎无差） |
| `BG_SELECTED` | `#094771` | `#094771`（不变） | 列表选中底 | VS Code list.activeSelectionBackground，保留 |
| `BG_RAISED`（新增） | — | `#2D2D30` | 弹层（ProductSelector 面板/菜单） | 与顶栏同族、高于内容区一档 |
| `BG_SUBTLE`（新增） | — | `#262626` | 提示条/chip 底色 | 语义色浅底叠加位，见下方语义组 |
| `STATUSBAR` | `#007ACC` | `#007ACC`（不变） | 底部状态栏 | VS Code 标志蓝，保留（⚠️ 决策点 §6.6） |

#### 文字

| 令牌 | 现值 | 新值 | 用途 | 改动理由 |
|---|---|---|---|---|
| `TEXT_PRIMARY` | `#CCCCCC` | `#E0E0E0` | 正文/标题 | 提亮，正文对比升至 ≈12.9:1，观感更清爽 |
| `TEXT_SECONDARY` | `#9D9D9D` | `#A8A8A8` | 次级/说明/分组标题 | 提亮，对比 ≈5.6:1，保持层级 |
| `TEXT_DISABLED` | `#6A6A6A` | `#7A7A7A` | 禁用态 | 提亮至 ≈3.9:1，禁用仍可读 |
| `TEXT_COMMENT`（新增） | — | `#7A9A8A` | 代码注释 | 深色 IDE 注释绿灰，解决 A4 对比不足 |
| `TEXT_ON_ACCENT` | `#FFFFFF` | `#FFFFFF`（不变） | 强调色/状态栏上的文字 | 保留 |
| `STATUSBAR_ON`（新增组） | — | `#E8F1FA`（常态）/ `#B0D4F1`（弱化） | 蓝底状态栏专用前景 | 解决 A7：蓝底上禁用态改用亮蓝灰而非 #6A6A6A |

#### 强调 / 语义

| 令牌 | 现值 | 新值 | 用途 | 改动理由 |
|---|---|---|---|---|
| `ACCENT` | `#007ACC` | `#007ACC`（不变） | 主强调（按钮/选中条/链接） | 品牌蓝，保留 |
| `ACCENT_HOVER` | `#1177BB` | `#1A8AD4` | 强调 hover | 提亮，hover 反馈更明显 |
| `ACCENT_FOCUS`（新增） | — | `#3FB6FF` | 焦点环 | 全组件键盘焦点可见（a11y） |
| `SUCCESS` | `#4EC9B0` | `#4EC9B0`（不变） | 成功/已连接/产品名 | 保留 |
| `WARNING` | `#CCA700` | `#D7BA3F` | 进行中/警告 | 提亮，深底上更醒目 |
| `ERROR` | `#F14C4C` | `#F14C4C`（不变） | 错误/失败 | VS Code 红，保留 |
| `BORDER` | `#3E3E42` | `#45454A` | 通用分隔/描边 | 提亮，分隔可见（现状几乎隐形） |
| `BORDER_STRONG`（新增） | — | `#55555C` | 输入/卡片 hover 边框、分组框描边 | 悬停可辨 |
| `ICON_IDLE` | `#858585` | `#9BA3AF` | 图标常态 | 提亮，图标可辨识 |
| `ICON_HOVER`（新增） | — | `#CCCCCC` | 图标 hover | 悬停反馈 |
| `ICON_DISABLED` | `#4A4A4A` | `#5A5A5E` | 图标禁用 | 提亮至可见下限 |
| `PRODUCT_GREEN` | `#4EC9B0` | `= SUCCESS`（注释引用） | 产品名高亮 | 消除重复定义（C3） |

#### 语义浅底色（新增，提示条 / 状态 chip）

| 令牌 | 新值 | 用途 |
|---|---|---|
| `SUCCESS_BG` | `rgba(78, 201, 176, 28)` | 成功提示条底（"已连接/已保存"） |
| `WARNING_BG` | `rgba(215, 186, 63, 24)` | 进行中/警告提示条底 |
| `ERROR_BG` | `rgba(241, 76, 76, 24)` | 错误提示条底 |

（QSS 支持 rgba；若个别平台渲染异常可退回近似不透明色 `#1F3B36 / #3A351C / #3B2026`，二选一并在 theme.py 注释注明。）

### 3.2 字号令牌

| 令牌 | 现值 | 新值 | 用途 | 理由 |
|---|---|---|---|---|
| `FONT_CAPTION` | 11 | 11（不变） | 状态栏/角标/时间戳 | 保留 |
| `FONT_BODY` | 13 | 13（不变） | 全局正文 | 保留 |
| `FONT_SUBTITLE` | 15 | 14 | 分组框标题/次级标题 | 与正文层级更紧、组标题不再「喧宾夺主」 |
| `FONT_TITLE` | 18 | 18（不变） | 页面标题（设置页） | 保留 |
| `FONT_LG`（新增） | — | 22 | 弹层大标题（如需） | 备用，不强制 |

另建议在 theme.py 增加字重常量：`WEIGHT_REGULAR=400 / WEIGHT_MEDIUM=500 / WEIGHT_BOLD=600`（当前多处硬编码 `font-weight:600`）。

### 3.3 间距令牌

| 令牌 | 现值 | 新值 | 用途 |
|---|---|---|---|
| `SPACE_XS` | 4 | 4（不变） | 图标与文字间隙 |
| `SPACE_SM` | 8 | 8（不变） | 行内控件间距 |
| `SPACE_MD` | 12 | 12（不变） | 组件间距 |
| `SPACE_LG` | 16 | 16（不变） | 页面内容 margins / 卡片内边距 |
| `SPACE_XL` | 24 | 24（不变） | 区块间距 |
| `SPACE_XXL`（新增） | — | 32 | 大区块/分栏间距 |

### 3.4 圆角令牌

| 令牌 | 现值 | 新值 | 用途 | 理由 |
|---|---|---|---|---|
| `RADIUS_SM` | 6 | 4 | 按钮/输入框 | 桌面工具更锐利、紧凑 |
| `RADIUS_MD` | 8 | 6 | 分组框/小卡片 | 跟随 SM 缩放 |
| `RADIUS_LG` | 10 | 8 | 卡片（SensorCard/面板） | 跟随缩放 |
| `RADIUS_FULL`（新增） | — | 16 | 药丸按钮（floatbtn/chip） | 替代 script_editor 硬编码 16 |
| `RADIUS_PANEL`（新增） | — | 10 | 弹层/对话框 | 弹层与内容区分 |

### 3.5 图标令牌（新增）

| 令牌 | 值 | 用途 |
|---|---|---|
| `ICON_XS` | 10 | 状态栏状态点、行内状态灯 |
| `ICON_SM` | 14 | 列表项前导图标 |
| `ICON_MD` | 16 | 顶栏/按钮图标（ProductSelector 触发器、开始/下发按钮） |
| `ICON_LG` | 20 | 页内大按钮图标（可选） |
| `ICON_XL` | 24 | ActivityBar 主图标 |

图标家族统一 qta `fa5s.*`（现状已统一，保留）；禁止文本符号当图标（A3）。

### 3.6 统一阶段文案（C4 根治）

`theme.STAGE_TEXT` 为唯一来源，扩展对齐状态栏用词（右侧为最终采用文案）：

| state | 现 STAGE_TEXT | 现 status_bar | 统一文案 |
|---|---|---|---|
| idle | 就绪 | 空闲 | 就绪 |
| compiling | 编译中 | 编译中 | 编译中 |
| connecting | 连接中 | 连接中 | 连接中 |
| entering_upgrade | 进入升级模式 | 进入升级 | 进入升级模式 |
| reconnecting | 等待设备重连 | 重连中 | 等待设备重连 |
| transfering | 传输中 | 传输中 | 传输中 |
| done | 完成 | 完成 | 完成 |
| error | 出错 | 错误 | 出错 |

`status_bar._STATE_TEXT` 删除，`_refresh_product` 改用 `theme.STAGE_TEXT`。

---

## 4. 布局与组件规格

### 4.1 主窗布局结构

```
┌────────────────────────────────────────────────────────────────────┐
│ 顶栏 TopBar（48px，BG_BAR，底部 1px BORDER 分隔线）                 │
│  [⬢ ProductSelector ▾]  │  [○串口 ○蓝牙][下拉▾ 刷新] [连接] [●]     │
├──┬─────────────────────────────────────────────────────────────────┤
│  │ 内容区（QStackedWidget，BG_EDITOR）                              │
│  ▎│  设备页: QSplitter 左固件(2) │ 右监控(3)                        │
│  ▎│  编辑页: 工具行 + CodeEditor + 状态行 + 日志                    │
│  ▎│  设置页: 标题 + 表单 + 保存                                    │
│  │                                                                 │
├──┴─────────────────────────────────────────────────────────────────┤
│ 状态栏 StatusBar（24px，STATUSBAR 蓝）：[● 连接状态] …… [部署阶段]  │
└────────────────────────────────────────────────────────────────────┘
```

- **顶栏（48px，`BG_BAR`）**：左 = `ProductSelector`（含产品图标+名称+chevron）；`addStretch(1)`；右 = `ConnectionSelector` 整块。产品区与连接区之间 1px `BORDER` 竖分隔线（`QFrame.VLine`）。
- **ActivityBar（48px 宽，`BG_BAR`）**：与顶栏同色族；三个图标导航，选中态 = 左侧 2px `ACCENT` 亮条 + `BG_HOVER` 底 + 图标 `TEXT_ON_ACCENT`；hover = `ICON_HOVER`；锁定 = 非当前项 `ICON_DISABLED`；**新增 focus 环**（E3）。
- **内容区（`BG_EDITOR`）**：页面统一 margins `SPACE_LG(16)`、spacing `SPACE_MD(12)`。
- **底部状态栏（24px，`STATUSBAR`）**：左 = 连接状态（`○/●` 图标 + "未连接" 或 "COM3 · 115200"）；右 = 部署阶段（`产品已去除`，仅阶段文案 + 状态色点）。状态栏前景统一用 `STATUSBAR_ON` 组（A7）。

### 4.2 ProductSelector 组件规格（核心新增）

**职责**：顶栏显示当前产品 + 下拉切换；保留原启动窗卡片视觉（产品名 + 高亮选中态）；busy 时锁定。

**结构**（新文件 `src/lbs_firmware_studio/gui/widgets/product_selector.py`）：

```
ProductSelector(QWidget)
├── QPushButton#product-trigger  （触发器：16px 产品图标 + 产品名 + 12px chevron-down）
└── QFrame#popup（弹层，BG_RAISED + 1px BORDER + RADIUS_PANEL，宽 220px）
    └── QListWidget（无边框；每项 = 16px 产品图标 + 产品名 [+ 选中打勾 fa5s.check]）
```

**交互**：

| 场景 | 行为 |
|---|---|
| 点击触发器 | 展开弹层（淡入 150ms）；再次点击/Esc/点击外部关闭 |
| 单击产品项 | 立即选中 + 关闭弹层 + `product_changed.emit(name)`（无需双击） |
| 键盘 | QListWidget 原生支持 ↑/↓ 导航、Enter 确认、Esc 关闭；触发器可 Tab 聚焦且有 `ACCENT_FOCUS` 焦点环 |
| 当前项 | 列表中高亮：`BG_SELECTED` 底 + 左侧 3px `ACCENT` 条 + 右侧 `fa5s.check`（`SUCCESS` 色）；产品名当前项 `PRODUCT_GREEN`（延续卡片视觉），其它项 `TEXT_PRIMARY` |
| 锁定（busy/下发中） | 触发器 `setEnabled(False)`（灰显，QSS 禁用态）；弹层强制关闭 |
| 空列表 | 触发器显示「无可用产品」禁用态 |

**尺寸**：触发器最小宽 168px、高 30px（顶栏 48px 内垂直居中）；弹层宽 220px、行高 36px、最多 6 行可见后滚动（QSS 定制滚动条，A1）。

**建议接口**（供 MainWindow 与测试使用，命名对齐既有风格）：

```python
class ProductSelector(QWidget):
    product_changed = Signal(str)          # 切换产品（选中即发）
    def __init__(self, profiles: dict, current: str, parent=None): ...
    def current_product(self) -> str: ...          # 当前产品名
    def product_names(self) -> list[str]: ...      # 全部产品名
    def select_product(self, name: str) -> bool: ...  # 程序化切换（返回是否成功）
    def trigger_button(self) -> QPushButton: ...   # 测试访问器
    def is_popup_open(self) -> bool: ...           # 测试访问器
    def set_locked(self, locked: bool) -> None: ...  # busy 锁定
```

**MainWindow 集成（替换 switch_product_requested 流转）**：

```
ProductSelector.product_changed(name)
  → MainWindow._on_product_change(name)
      ├─ 守卫：self._busy → 拒绝（回滚选择到原产品）
      ├─ 停监控（_monitor.stop_monitor()）
      ├─ 断开旧页面信号（或整体重建页面栈——规格采用「重建」）
      ├─ 重建 _pages（_make_page 去死分支后重建 Firmware/Monitor/Editor 页）
      ├─ 重连信号：start_requested / deploy_requested / host_state_changed / run_toggle_requested / connection_changed / target_changed
      ├─ 加载新 profile：set_profile / set_port_getter / set_baud_getter
      ├─ 更新顶栏（selector 自身已更新）+ 状态栏（阶段重置为「就绪」）
      └─ 连接状态处理：见决策点 §6.4（baud 一致保持链路，否则断开提示）
```

`header_text()` 访问器保留：改为返回 `self._product_selector.current_product()`，签名不变。

### 4.3 连接选择器 ConnectionSelector（微调）

- 布局保持（单选 + 下拉/扫描 + 连接按钮 + 状态点），尺寸适配 48px 顶栏；`indicator` 升到 16px（E1）；`_RADIO_QSS` 收敛进 `theme.app_qss()`（E1）；状态点改矢量图标（A3）。
- 「扫描中...」占位项 `setEnabled(False)`（E4，同 PortSelector 处理）。
- 颜色全部走新令牌（无硬编码）。

### 4.4 各页面规格

#### 设备页（固件与监控分栏，QSplitter 左 2 : 右 3）

**左栏 · 固件更新（FirmwarePage）**

```
┌ 固件源 ──────────────────────────────┐
│ 目录: [……\products\NEW-AI\fwlib   ]   │
│ 待发送: app, music, boot, config, version
└──────────────────────────────────────┘
┌ 操作 ────────────────────────────────┐
│ [ ▼ 开始固件更新 ]        ● 就绪      │
│ ████████░░░░  80%                    │
└──────────────────────────────────────┘
┌ 日志 ────────────────────────────────┐
│ 12:00:01 编译中……                     │
└──────────────────────────────────────┘
```

- 「开始固件更新」：主色按钮（图标 fa5s.download，`ICON_MD`），宽度限 180px；点击弹确认框（B2）。
- 阶段：状态 chip = 色点（`state_color`）+ 阶段文案（`STAGE_TEXT`），色点矢量图标；`_stage` 文字随状态变色（`state_color`）。
- 进度条：`setFormat(f"{pct}%")` + QSS 文本色（B10）。
- 日志：LogView 可伸缩（现状 stretch=1 保留），加行数裁剪（E6）。

**右栏 · 数据监控（MonitorPage）**

```
[● 使用顶栏连接（SUCCESS_BG 提示条）]        [⟳ 传感器更新]
┌ 端口0·颜色 ──────────┐ ┌ 端口1·大电机 ─────┐
│ r: 1   g: 2   b: 3   │ │ 度: 255          │
│ lux: 1615            │ │                  │
│ 更新 12:00:01        │ │ 更新 12:00:03    │
└──────────────────────┘ └──────────────────┘
┌ HostStatusBar 卡片 ──────────────────────┐
│ 版本:317  IMU:…/…/…  Heap:…  电量:…  MAC:… │
└──────────────────────────────────────────┘
```

- **移除本页 PortSelector**（B5，⚠️ 决策点）：未连接时顶部显示 `WARNING_BG` 提示条「请先在顶栏连接设备」；已连接显示 `SUCCESS_BG` 提示条「● 使用顶栏连接」（图标 fa5s.link）。
- 传感器更新按钮：仅 `sensor_update` 产品且监控中启用（现状逻辑保留），图标 fa5s.sync，`ICON_MD`。
- 卡片网格：等高两列（D3）；空端口显示灰态「无设备」；卡片标题 + 字段 + 刷新时间（B6）；字段值用等宽数字（tabular）。
- 底部 HostStatusBar：保留字段结构，值区等宽字体、横向可滚动（E5）。
- 错误降级：不弹 QMessageBox，进状态栏红点 + 日志（B7）。

#### 代码编辑页（ScriptEditorPage）

```
[模板: blink.py ▾] [打开…] [保存]
┌───────────────────────────────────────────────────┐
│ 1  led.on()                                [▶][⏸] │
│ 2  import time                              [槽位3]│
│ 3                                        [⏫ 下发] │
└───────────────────────────────────────────────────┘
● 就绪  ████████░░ 80%
┌ 日志 ─────────────────────────────────────────────┐
│ 12:00:01 已保存 3.py                               │
└───────────────────────────────────────────────────┘
```

- 工具行（模板下拉 + 打开 + 保存）：`SPACE_SM` 间距；label「模板:」保留。
- **dirty 高亮修正**（A2）：保存按钮 `setProperty("dirty", true/false)` + repolish，QSS 定义 `QPushButton[dirty="true"] { border:1px solid ACCENT; color: ACCENT; }`；保存成功后短暂「已保存 ✓」（B8，QTimer 800ms 复位，可选）。
- 编辑器右上浮动操作组：保留浮动（父控件 = 编辑器，`parent is page._editor` 不变，**最小化测试破坏**，⚠️ 决策点 §6.5），但：间距用 `SPACE_SM`、圆角 `RADIUS_FULL`、按钮顺序调整为 [运行][暂停] | [槽位 N][下发]（运行/暂停相邻）；下发按钮补文字「下发」或保留图标 + 更明显 tooltip（a11y 建议文字）。
- 阶段 + 进度条合并单行（`QHBoxLayout`：色点 + 阶段文本 + 进度条 stretch=1），日志恢复可伸缩（D4）。

#### 设置页（SettingsPage）

```
设置
编译器路径: [c:\tools\gcc.exe          ] [浏览…]
┌ 固件目录（每产品） ─────────────────────────────┐
│ NEW-AI    [./products/NEW-AI/fwlib      ] [浏览…] │
│ SPARK-AI  [./products/SPARK-AI/fwlib    ] [浏览…] │
│ NEXT-AI   [./products/NEXT-AI/fwlib     ] [浏览…] │
└──────────────────────────────────────────────────┘
                                    [保存]  ● 已保存，重启后生效
```

- 统一 margins `SPACE_LG` / spacing `SPACE_MD`（D2）；标题「设置」用 `FONT_TITLE` + 次级说明一行（`TEXT_SECONDARY`、`FONT_BODY`）。
- 每产品行：产品名 label 固定宽（如 80px）左对齐 + 只读输入 + 浏览按钮，行间距 `SPACE_SM`。
- 保存按钮右对齐 + `addStretch(1)`（D5）；状态消息用 `SUCCESS` 色 + 图标（`SUCCESS_BG` 提示条）。
- 访问器（`compiler_path_text / product_rows / firmware_dir_text / set_* / save`）全部保留，测试零改动。

### 4.5 新增空态/提示条规范

| 场景 | 形态 |
|---|---|
| 监控页未连接 | 顶部 `WARNING_BG` 圆角提示条：⚠ 请先在顶栏连接设备 |
| 监控页已连接 | 顶部 `SUCCESS_BG` 提示条：● 使用顶栏连接（复用现 `_conn_hint` 升级为带底色条） |
| 设置保存成功 | `SUCCESS` 文字 + 图标：已保存，重启后生效 |
| 固件页未选产品 | 「待发送: （未选择产品）」 |

---

## 5. 页面线框（ASCII）

### 5.1 主窗骨架（默认进入，无启动页）

```
┌────────────────────────────────────────────────────────────────────────────┐
│ 48px ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │
│ [⬢ NEW-AI ▾]  │  [○串口 ○蓝牙][COM3·LBS ▾][刷新] [连接] [●]                │
├──┬─────────────────────────────────────────────────────────────────────────┤
│▎ │  ┌──────────────────────────────┐  ┌──────────────────────────────┐     │
│▎ │  │ 固件更新 (2/5)               │  │ 数据监控 (3/5)               │     │
│▎ │  │                              │  │ [● 使用顶栏连接]  [⟳ 传感器更新]│     │
│▎ │  │                              │  │ ┌ 端口0·颜色 ──┐ ┌ 端口1 ·─┐ │     │
│▎ │  │                              │  │ └─────────────┘ └─────────┘ │     │
│▎ │  │                              │  │ ┌ HostStatusBar ───────────┐ │     │
│▎ │  │                              │  │ └──────────────────────────┘ │     │
│▎ │  └──────────────────────────────┘  └──────────────────────────────┘     │
│  │                                                                         │
├──┴─────────────────────────────────────────────────────────────────────────┤
│ 24px ████  [○ 未连接]                        [就绪]                        │
└────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 ActivityBar（48px）

```
┌──┐
│▎│ ⬢ 固件与监控    ← 选中：左 2px ACCENT 条 + BG_HOVER 底 + 白图标
│▎│ ⬡ 代码编辑
│  │
│  │  (stretch)
│  │ ⚙ 设置          ← 沉底
└──┘
```

### 5.3 ProductSelector 弹层

```
 ┌─────────────────────────┐
 │ ▎ ⬢ NEW-AI        ✓    │  ← 选中：BG_SELECTED + 左 3px ACCENT 条 + 打勾
 │   ⬢ SPARK-AI           │
 │   ⬢ NEXT-AI            │
 └─────────────────────────┘
  220px × 3 行（>6 行滚动）
```

### 5.4 代码编辑页

```
┌──────────────────────────────────────────────────────────────┐
│ [模板: blink.py ▾]  [打开…]  [保存]                           │
├──────────────────────────────────────────────────────────────┤
│ 1  led.on()                                [▶][⏸] [槽位 3]    │
│ 2  import time                                      [⏫ 下发] │
│ 3  time.sleep(0.1)                                       │
│ …                                                          │
├──────────────────────────────────────────────────────────────┤
│ ● 传输中  ██████████░░░░  80%                               │
├──────────────────────────────────────────────────────────────┤
│ 12:00:01 已保存 3.py                                        │
└──────────────────────────────────────────────────────────────┘
```

### 5.5 设置页

```
┌──────────────────────────────────────────────────────────────┐
│ 设置                                                          │
│ 修改编译器与各产品固件目录，保存写回 products.yaml             │
│ 编译器路径: [c:\tools\gcc.exe          ]  [浏览…]             │
│ ┌ 固件目录（每产品） ──────────────────────────────────────┐  │
│ │ NEW-AI    [./products/NEW-AI/fwlib       ]  [浏览…]     │  │
│ │ SPARK-AI  [./products/SPARK-AI/fwlib     ]  [浏览…]     │  │
│ │ NEXT-AI   [./products/NEXT-AI/fwlib      ]  [浏览…]     │  │
│ └──────────────────────────────────────────────────────────┘  │
│                                    [保存]  ✓ 已保存，重启后生效│
└──────────────────────────────────────────────────────────────┘
```

---

## 6. 实施约束、红线与决策点

### 6.1 实施约束（沿用规格 5.6，补充）

- GUI 层不碰协议/串口/BLE；设备操作仍经 worker → deployer（`_run_deploy` 流程不动）。
- 深色主题不硬编码色值，全部走 `theme` 令牌；QSS 仅存在于 `theme.app_qss()` 与组件内通过令牌拼接处。
- 测试访问器签名（`header_text() / nav_labels() / is_nav_enabled() / navigate() / current_page_name() / is_busy() / status_bar_text() / click_switch_product()`）尽量保持；`click_switch_product` 语义变化见 §6.2。
- 删除文件：`startup_window.py`、`placeholder_page.py`；对应测试 `test_startup_window.py`、`test_placeholder_page.py` 同步删除。
- `AppController` 简化：删除 `show_startup()` 状态机，提供 `launch(default_product="NEW-AI")` 直入主窗；`main()` 调用 `on_product_selected("NEW-AI")` 的等价入口。

### 6.2 信号与访问器兼容表

| 现有成员 | 新方案 | 测试影响 |
|---|---|---|
| `MainWindow.switch_product_requested`（Signal） | 删除；由 `ProductSelector.product_changed` 承担，MainWindow 内部处理 | `test_main_window.py::test_switch_product_button_emits` 改写为「selector.select_product → 页面重建」 |
| `click_switch_product()` | 改为 `select_product(name)` 或保留 `click_switch_product` 转发到 selector 触发器 | 同上 |
| `header_text()` | 返回 `_product_selector.current_product()` | 签名不变，语义不变（仍含产品名） |
| `MainWindow._conn / _firmware / _monitor / _editor_page` | 属性名**保留**（重建页面栈时替换对象引用） | 大批测试免改（test_main_window_buttons 等） |
| `StartupWindow` 类 | 删除 | test_startup_window.py 删除；卡片选中视觉逻辑迁移进 ProductSelector 列表项 |

### 6.3 决策点 1：监控页是否移除本页 PortSelector

- **推荐**：移除（统一顶栏连接）。理由：双入口是 B5 主因，且顶栏连接已能驱动自动监控。
- ✅ **已决策（2026-08-05，用户）**：移除监控页本页 PortSelector，统一用顶栏连接。
- **代价**：`monitor_page._port / _port_lbl / _sync_conn_ui` 相关逻辑与 `test_monitor_page.py` 中不依赖端口选择器的用例不受影响，但需要确认无测试直接操作 `_port`。
- **备选**：保留本页端口选择作为「未连接时的回退入口」（现状行为）。若选此方案，需保留 `_sync_conn_ui` 但用提示条样式替代文本跳变。

### 6.4 决策点 2：切换产品时顶栏连接状态的处理

- **推荐**：切换产品后**检查新产品 baud 与当前链路是否一致**——一致则保持链路并自动重启监控；不一致则断开链路并提示「产品波特率变化，请重新连接」。
- ✅ **已决策（2026-08-05，用户）**：baud 一致保持链路并自动重启监控；不一致断开并提示。
- **备选**：一律断开并提示重连（简单但粗暴，频繁切换体验差）。

### 6.5 决策点 3：编辑页浮动按钮是否改为容器布局

- **推荐**：**保留浮动**（父控件 = 编辑器），仅规范间距/圆角/顺序。理由：`test_script_editor_page.py::test_run_pause_buttons_are_children_of_editor` 断言 `parent() is page._editor`，改动最小；浮动视觉是 VS Code 风格（编辑器内浮槽）。
- ✅ **已决策（2026-08-05，用户）**：保留浮动，仅规范间距/圆角/顺序。
- **备选**：改为编辑器外右上工具条（a11y/定位更稳），需同步改 parent 断言与 `_reposition_float_buttons` 删除。

### 6.6 决策点 4：底部状态栏蓝色保留与否

- **推荐**：保留 `#007ACC` 蓝（VS Code 标志，品牌一致）。
- ✅ **已决策（2026-08-05，用户）**：保留蓝色。
- **备选**：改深灰 `BG_BAR`（更克制），需同步调 `STATUSBAR_ON` 前景组为普通文字色。默认按推荐执行，除非用户明确要求去蓝。

---

## 7. 测试影响评估

约 140 个 qtbot 测试，按文件评估（★=需改动 / ◆=删除 / ○=基本不变 / ＋=新增）：

| 文件 | 评估 | 说明 |
|---|---|---|
| `test_theme.py` | ★ | `test_dark_colors_defined` 断言旧 hex（#1E1E1E/#333333/#007ACC/#CCCCCC/#3E3E42）→ 更新为新令牌值；`test_state_color_dark_mapping` 断言 `#CCA700/#4EC9B0/#F14C4C` → WARNING 改 `#D7BA3F` 需同步；新增断言：新令牌存在（ACCENT_FOCUS/BG_RAISED/TEXT_COMMENT/ICON_*） |
| `test_app_smoke.py` | ◆ 重写 | 依赖 `show_startup/on_product_selected/on_switch_product/current_window_kind` 流转 → AppController 简化后重写：`launch()` 直入主窗、产品切换走 ProductSelector、无 startup 态 |
| `test_startup_window.py` | ◆ 删除 | StartupWindow 删除；卡片选择/选中视觉测试迁移为 `test_product_selector.py` |
| `test_placeholder_page.py` | ◆ 删除 | PlaceholderPage 删除 |
| `test_main_window.py` | ★ | `test_switch_product_button_emits` 语义变化（§6.2）；其余（header_text/nav/状态栏/busy/监控启停）签名不变，属性名保留则基本免改；新增：`test_product_switch_rebuilds_pages`、`test_switch_blocked_when_busy` |
| `test_main_window_ble_gate.py` | ○ | 依赖 `_conn.set_kind` / `_ble_firmware_blocked` / `_start_firmware`，接口不动 |
| `test_main_window_buttons.py` | ○ | 依赖 `_firmware._start` / `_editor_page.*` / `_conn` / `_monitor.host_state_changed`，属性名保留即免改 |
| `test_activity_bar.py` | ○ | 接口（keys/is_enabled/current_key/set_locked/icon_color）不动；focus 样式不影响断言 |
| `test_connection_selector.py` / `_signals.py` | ○ | `selected_kind/selected_target/set_kind/scan_ble/make_transport` 接口不动；indicator 尺寸改动不影响 |
| `test_port_selector.py` / `_async.py` | ○ | 接口不动；「扫描中...」置禁用不影响现有断言（建议补一条：占位项不可选） |
| `test_monitor_page.py` | ○（若 §6.3 移除本页端口）★（若保留） | `card_count/card_at/has_sensor_update_button/latest_frame/field_text` 全保留；若移除 `_port` 且无测试直接引用则免改；`_sync_conn_ui` 若改提示条需核对 `set_transport_getter` 行为 |
| `test_firmware_page.py` | ★ 少量 | `start_button/summary_text/firmware_dir_text/progress_value/stage_text/log_text` 保留；若加二次确认框，`start_requested` 触发路径需先走确认（测试需 monkeypatch 确认框或提供 `confirm_start()` 直通）；进度 `setFormat` 不影响 `progress_value` |
| `test_script_editor_page.py` | ○（§6.5 保留浮动） | 全部断言依赖接口 + `parent is _editor`，保留浮动即免改；dirty 高亮改 `setProperty` 后 `_save_btn` 引用不变 |
| `test_settings_page.py` | ○ | 访问器全保留，仅布局调整 |
| `test_sensor_card.py` | ○ | `update/title_text/rows` 保留；新增刷新时间戳字段只影响视觉不破坏断言（建议补：空态含「无设备」提示的断言） |
| `test_host_status_bar.py` | ○ | `field_text` 保留；等宽字体/滚动不影响 |
| `test_status_bar.py` | ★ | `test_set_product`（断言 `_product_lbl` 含产品名）与 `test_state_text_and_color`（state_text 含产品名）→ 移除产品名后需改：`set_product` 删除或改存内部不影响显示；`state_text` 断言改为只含阶段文案 |
| `test_log_view.py` | ○ | `append/plain_text` 接口不动；行数裁剪不影响现有断言 |
| `test_code_editor.py` | ○ | 编辑/高亮接口不动；注释色变更不破坏功能断言 |
| `test_sensor_update_dialog.py` | ○ | 对话框接口不动 |
| 新增文件 | ＋ | `test_product_selector.py`：选择/切换/锁定/键盘导航/弹层开关；`test_main_window.py` 增补页面重建用例 |

**建议实施顺序**（TDD）：theme 令牌 → 更新 test_theme → ProductSelector（+测试）→ MainWindow 集成（改 app_smoke/main_window 测试）→ 删除 startup/placeholder（删测试）→ 页面样式翻新（同步各页测试微调）→ 全量 `python -m pytest` 收尾（pytest-qt 退出段错误按已知坑容忍）。

---

## 附录 A：令牌迁移映射表

| 旧令牌 | 旧值 | 新令牌 | 新值 |
|---|---|---|---|
| BG_EDITOR | #1E1E1E | BG_EDITOR | #1E1E1E（不变） |
| BG_SIDEBAR | #252526 | BG_SIDEBAR | #252526（不变） |
| BG_BAR | #333333 | BG_BAR | #2D2D30 |
| BG_INPUT | #3C3C3C | BG_INPUT | #3C3C3C（不变） |
| BG_HOVER | #2A2D2E | BG_HOVER | #37373D |
| BG_SELECTED | #094771 | BG_SELECTED | #094771（不变） |
| — | — | BG_RAISED（新） | #2D2D30 |
| — | — | BG_SUBTLE（新） | #262626 |
| STATUSBAR | #007ACC | STATUSBAR | #007ACC（不变） |
| TEXT_PRIMARY | #CCCCCC | TEXT_PRIMARY | #E0E0E0 |
| TEXT_SECONDARY | #9D9D9D | TEXT_SECONDARY | #A8A8A8 |
| TEXT_DISABLED | #6A6A6A | TEXT_DISABLED | #7A7A7A |
| — | — | TEXT_COMMENT（新） | #7A9A8A |
| TEXT_ON_ACCENT | #FFFFFF | TEXT_ON_ACCENT | #FFFFFF（不变） |
| ACCENT | #007ACC | ACCENT | #007ACC（不变） |
| ACCENT_HOVER | #1177BB | ACCENT_HOVER | #1A8AD4 |
| — | — | ACCENT_FOCUS（新） | #3FB6FF |
| SUCCESS | #4EC9B0 | SUCCESS | #4EC9B0（不变） |
| WARNING | #CCA700 | WARNING | #D7BA3F |
| ERROR | #F14C4C | ERROR | #F14C4C（不变） |
| BORDER | #3E3E42 | BORDER | #45454A |
| — | — | BORDER_STRONG（新） | #55555C |
| ICON_IDLE | #858585 | ICON_IDLE | #9BA3AF |
| ICON_DISABLED | #4A4A4A | ICON_DISABLED | #5A5A5E |
| — | — | ICON_HOVER（新） | #CCCCCC |
| PRODUCT_GREEN | #4EC9B0 | PRODUCT_GREEN | = SUCCESS（引用） |
| FONT_SUBTITLE | 15 | FONT_SUBTITLE | 14 |
| RADIUS_SM/MD/LG | 6/8/10 | RADIUS_SM/MD/LG | 4/6/8 |
| — | — | RADIUS_FULL（新） | 16 |
| — | — | RADIUS_PANEL（新） | 10 |
| — | — | SPACE_XXL（新） | 32 |
| — | — | ICON_XS/SM/MD/LG/XL（新） | 10/14/16/20/24 |
| — | — | SUCCESS_BG/WARNING_BG/ERROR_BG（新） | rgba(...) 见 §3.1 |
| status_bar._STATE_TEXT | 两套文案 | theme.STAGE_TEXT（唯一） | 见 §3.6 |

---

## 附注：设计依据

- 设计智能检索（`search.py --design-system "embedded firmware tool desktop developer dark"`）：风格匹配 Dark Mode（OLED/开发者工具），正文对比建议 ≥7:1、焦点可见、禁用态可辨、图标矢量统一——与本节令牌取值一致；排版延续 Inter（现状 UI_FONT 已含 Inter）。
- 走查结论与令牌改动均已对照 `tests/gui/` 现存断言，确保影响面可枚举（§7）。
