# UI 深度重构设计规范（参考 multi-device-studio.html）

> 2026 依据 `multi-device-studio.html`（NovaLink Device Studio 深色科技风）重构桌面 GUI。
> 本文件是**唯一样式来源**：所有组件改动必须严格按下述令牌与细节实现，不得另立色值。
> 对应实现位置：`src/lbs_firmware_studio/gui/theme.py`（令牌 + QSS）、各 widget/page 组件。

## 1. 色彩体系（严格使用，全部走 theme 令牌）

| 令牌 | 值 | 语义（参考 HTML 类） |
|---|---|---|
| BG_PAGE | `#0b1018` | 页面底色（body bg） |
| BG_CARD | `#101722` | 卡片/面板底（rounded-xl bg-[#101722]） |
| BG_SIDEBAR | `#0e151f` | 左侧侧栏底（aside bg-[#0e151f]） |
| BG_BAR | `#101722` | 顶栏 + 底部状态栏底（header bg-[#101722]） |
| BG_EDITOR | `= BG_PAGE` | 页面底（兼容旧名；实现中页面底色 = BG_PAGE） |
| BG_CODE | `#0d131c` | 编辑器主体底（editor） |
| BG_LOGS | `#0a0f16` | 日志区深底（logs） |
| BG_CODE | `#0d131c` | 编辑器主体底（editor bg-[#0d131c]） |
| BG_RAISED | `#121b27` | 弹层/浮窗/菜单底（安全连接卡 bg-[#121b27]） |
| BG_INPUT | `#1e293b` | 输入框/按钮底（slate-800） |
| BG_HOVER | `#1f2b3d` | hover 提亮（可辨识一档） |
| BG_SELECTED | `rgba(34, 211, 238, 0.10)` | 选中导航项底（bg-cyan-400/10） |
| BG_SUBTLE | `#0d141e` | 统计块/浅底色（bg-[#0d141e]） |
| ACCENT | `#22d3ee` | 主强调（cyan-400） |
| ACCENT_HOVER | `#67e8f9` | 强调 hover（cyan-300） |
| ACCENT_FOCUS | `#67e8f9` | 键盘焦点环 |
| TEXT_ON_ACCENT | `#020617` | 强调色上文字（slate-950） |
| TEXT_PRIMARY | `#e2e8f0` | 正文/标题（slate-200） |
| TEXT_SECONDARY | `#94a3b8` | 次级/说明（slate-400） |
| TEXT_DISABLED | `#64748b` | 禁用/弱化（slate-500） |
| TEXT_COMMENT | `#7c8ea0` | 代码注释 |
| BORDER | `#1e293b` | 普通边框（slate-800） |
| BORDER_STRONG | `#334155` | 强调边框（slate-700） |
| SUCCESS | `#34d399` | 成功（emerald-400） |
| WARNING | `#fbbf24` | 警告（amber-400） |
| ERROR | `#f87171` | 错误（red-400） |
| ICON_IDLE | `#94a3b8` | 图标常态 |
| ICON_HOVER | `#e2e8f0` | 图标 hover |
| ICON_DISABLED | `#475569` | 图标禁用 |
| PRODUCT_GREEN | `= SUCCESS` | 产品名高亮（语义引用） |
| STATUSBAR | `#101722` | 状态栏底（深色，不再是蓝底） |
| STATUSBAR_ON | `#e2e8f0` | 状态栏前景常态 |
| STATUSBAR_ON_MUTED | `#64748b` | 状态栏前景弱化 |
| SUCCESS_BG | `rgba(52, 211, 153, 24)` | 成功浅底/chip |
| WARNING_BG | `rgba(251, 191, 36, 20)` | 警告浅底/chip |
| ERROR_BG | `rgba(248, 113, 113, 20)` | 错误浅底/chip |

- 状态点：`#34d399` 实心圆（在线/连接成功，参考 h-2 w-2 rounded-full bg-emerald-400）。
- 传感器端口色板（参考 P1–P8 彩色卡片，每端口一 accent 色）：
  `#22d3ee`(cyan) / `#a78bfa`(violet) / `#e879f9`(fuchsia) / `#38bdf8`(sky) /
  `#fbbf24`(amber) / `#fb7185`(rose) / `#34d399`(emerald) / `#a3e635`(lime)，
  取 `SENSOR_COLORS[port % 8]`；对应浅底 = 主色 + alpha 0.06~0.10。

## 2. 圆角 / 间距 / 字号

- 圆角：RADIUS_SM `6` / RADIUS_MD `8` / RADIUS_LG `12`（卡片 rounded-xl）/ RADIUS_PANEL `12` / RADIUS_FULL `16`（药丸）。
- 间距节奏（8px）：SPACE_XS 4 / SM 8 / MD 12 / LG 16 / XL 24 / XXL 32；卡片内边距约 `20px`（参考 p-5）。
- 字号：FONT_CAPTION `11` / FONT_BODY `13` / FONT_SUBTITLE `14` / FONT_TITLE `24`（text-2xl）/ FONT_LG `28`。
- 等宽数字：MONO_FONT 大字号 + 强调色（参考 `font-mono text-2xl text-cyan-300`）。
- 分组标题：10px + `tracking` 大写灰字（slate-500，参考 uppercase tracking-[0.16em]）。

## 3. 布局结构（三段式，参考 header + aside + main）

1. **顶栏 header**：高 `56px`，BG_BAR，底边 1px BORDER。
   左侧品牌区：logo 图标（qta 图标，ACCENT 色）+「LBS Firmware Studio」标题（white semibold，
   副标题 slate-500）；右侧：HostStatusBar 主机信息（"字段: 值"，值等宽）。
2. **左侧侧栏**：宽 `256px`，BG_SIDEBAR，右边 1px BORDER。
   分组标题（10px uppercase）→ 导航项（icon + 文字标签，行高约 44px，圆角 6px；
   选中 = BG_SELECTED 底 + ACCENT 文字 + 左 3px ACCENT 亮条；常态 slate-400 hover 提亮）→
   底部设置项（沉底，同导航项样式）。
3. **主内容区**：BG_PAGE；页面以卡片（BG_CARD + BORDER + 12px 圆角）承载；
   右侧监控栏固定宽 280px。
4. **底部状态栏**：`24px` BG_BAR 深色；左连接状态点 + 连接文字（slate），
   右部署阶段点（彩色）+ 阶段文案；deploy 日志单行等宽弱化色。

## 4. 组件细节

- **卡片**：标题 font-medium TEXT_PRIMARY + 副标题 FONT_CAPTION TEXT_SECONDARY；内容区留白 20px。
- **状态 chip**：半透明彩色底 + 彩色边框 + 彩色小字（参考 `rounded-full border-emerald-400/20 bg-emerald-400/10 text-emerald-300`）。
- **主按钮（primary）**：ACCENT 底 + TEXT_ON_ACCENT 文字 + 圆角 6px + bold；hover ACCENT_HOVER。
- **次按钮**：BG_INPUT 底 + BORDER 边 + TEXT_PRIMARY 文字；hover BG_HOVER + border ACCENT。
- **输入框 / 下拉 / radio**：BG_INPUT 底 + BORDER 边 + 6px 圆角；focus 边框 ACCENT_FOCUS；
  radio 选中指示器 SUCCESS（参考绿色小圆点）。
- **进度条**：高 6px、圆角、chunk ACCENT。
- **传感器卡**：标题「端口 N · 类型名」；每端口 accent 色（端口号 mono 彩色 + 标题 + 边框浅色）；
  空态「无设备」灰字；有数据时底部「更新 HH:MM:SS」小字。
- **编辑器**：BG_CODE 底 + BORDER 边框 + 12px 圆角；行号区 BG_EDITOR、行号 TEXT_DISABLED；
  当前行高亮 BG_HOVER；语法色：关键字 violet `#a78bfa`、字符串 emerald `#6ee7b7`、
  数字 amber `#fcd34d`、函数名 cyan `#67e8f9`、注释灰。
- **日志区**：BG_EDITOR 底 + mono 等宽；时间戳 TEXT_DISABLED；级别色走语义令牌。
- **弹层/浮窗**：BG_RAISED 底 + BORDER + 12px 圆角；标题 FONT_CAPTION 灰色。
- **对话框**：BG_PAGE 底；主操作按钮 primary。

## 5. 红线

- GUI 层不碰协议/串口/BLE（backend 零改动）；仅改 `gui/` 与 `tests/gui/`。
- 所有颜色必须走 `theme.*` 令牌，禁止组件内硬编码色值。
- 保持既有测试接口与行为不变（信号/访问器/文案）；颜色断言在 test_theme.py 同步更新。
- 布局改动不破坏 `nav_labels()/navigate()/header_text()` 等 MainWindow 测试访问器语义。
