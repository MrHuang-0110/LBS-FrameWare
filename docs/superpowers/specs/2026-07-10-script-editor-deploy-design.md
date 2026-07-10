# 脚本编辑器 + 脚本下发 + 槽位选择 · 设计文档

> 状态：设计已与用户确认（架构/数据流/视觉三段均通过），待写实施计划。

## 目标

在 LBS Firmware Studio 的「代码编辑」页做一个完整的 **Python 脚本编辑器**，形成
「选模板 → 编辑 → 保存 → 选槽 → 下发」单页闭环：编辑器内部右上角浮两个圆形按钮
（选槽位、下发），顶部有「预加载模板」下拉。复用已就绪的后端
`DeviceDeployer.deploy_script()` 与 `DeployWorker` 线程模式。导航栏原「脚本下发」项
**隐藏**，功能全部并入「代码编辑」页。

## 全局约束（沿用项目既定）

- Python 3.13、Windows、解释器用 `python`；PySide6 6.11.1、qtawesome、pytest-qt。
- **GUI 层只做界面**：下发经 `DeployWorker` 调 `DeviceDeployer`，不碰协议/串口写。
- 深色主题：颜色/圆角一律取 `theme.*` 常量，禁止硬编码色值。VS Code Dark+ 风格。
- 后端信号签名固定：`progress(int,int)`、`log(str)`、`state_changed(str)`、`error(str)`。
- state→颜色/文字映射沿用固件页：idle/compiling/connecting/entering_upgrade/
  reconnecting/transfering/done/error。
- **QScintilla 不可用**（绑定 PyQt 而非 PySide6）：编辑器基于 `QPlainTextEdit` 自实现。
- 测试用 pytest-qt + 手动 emit / qtbot 真实事件，**不碰真串口**；GUI 测试按文件单独跑，
  容忍多 QThread 同进程 teardown 段错误（以断言结果为准）。
- 事件处理器中先 `super()` 再 `emit`（避免 use-after-delete）。

## 架构与组件

### 新增控件 `gui/widgets/code_editor.py`
- `CodeEditor(QPlainTextEdit)`：行号边栏（LineNumberArea）+ 当前行高亮 + Tab→空格缩进
  （4 空格）。等宽字体。
- `PythonHighlighter(QSyntaxHighlighter)`：关键字/字符串/注释/数字/装饰器高亮，颜色取
  `theme.*`（关键字→ACCENT，字符串→SUCCESS，注释→TEXT_DISABLED，数字/装饰器→WARNING）。
- 纯 UI，自包含可独立测试。

### 新页面 `gui/pages/script_editor_page.py` → `ScriptEditorPage(QWidget)`
- 顶部行：`QLabel("模板:")` + `QComboBox`（模板下拉，首项「(空白)」）+ `QPushButton("保存")`。
- 编辑区：`CodeEditor`，**内部右上角绝对定位**两个圆形按钮：
  - 「槽位 N」按钮：显示当前槽位号，点击弹 `QMenu` 列 `0..max_slot`。
  - 「下发」按钮：图标 `fa5s.upload`，主强调色。
  - 两按钮直径约 40px 正圆，深色底 + hover/pressed 反馈；随编辑区 resize 保持右上对齐。
- 底部：`QProgressBar` + `LogView`（复用）。
- 只做界面；下发经 worker 调后端。

### 后端小改 `backend/profile.py` + `products.yaml`
- `DeviceProfile` 加字段：`max_slot: int = 0`、`templates_dir: Path`。
- `templates_dir` 按约定推导 `<firmware_dir 的产品根>/templates`，即
  `./products/<产品名>/templates`（load_profiles 时生成，无需每产品手写）。
- yaml 给三产品配 `max_slot`：NEW-AI=19、SPARK-AI=9、NEXT-AI=0。

### 编排层（无需改）
- `deployer.deploy_script(profile, port, py_path, slot)` 已就绪，签名不变。

### worker `gui/worker.py`
- 加 `run_script` 槽（对称 `run_firmware`）：`open→start_rx→deploy_script(...)`，异常同样
  补发 error/state_changed，finally close + finished。
- `set_job` 扩展携带 `py_path`、`slot`（对固件路径为 None）。

### 主窗 `main_window.py`
- `_NAV`：移除（隐藏）scripts 项；editor 项 `enabled=True` 并接 `ScriptEditorPage`。
- 抽出固件/脚本公共的 thread/worker 接线（`_run_worker(kind)` 之类），减少重复。

## 数据流与交互

1. **进入**：`set_profile(profile)` → 扫 `templates_dir` 填模板下拉；槽位按钮初始化 slot 0，
   选单 `0..max_slot`；`max_slot==0`（NEXT-AI）时按钮禁用/单选。
2. **选模板**：读文件灌入编辑器，标记 clean；首项「(空白)」清空编辑器。
3. **编辑**：`modificationChanged` 标 dirty，保存按钮高亮（强调色边框）。
4. **选槽位**：弹 `QMenu` 选 `0..max_slot`，按钮文字更新「槽位 N」。槽位号决定保存文件名与下发目标。
5. **保存**（Ctrl+S / 保存按钮）：写 write 目录（`profile.script_dirs` 的 key）`/<slot>.py`（UTF-8），
   标 clean，日志「已保存 <slot>.py」。
6. **下发**（圆形下发按钮）：前置校验——①未选串口→提示；②内容为空→提示；
   ③**有未保存改动→提示"请先保存"并中止**（不自动保存）。通过后走 `DeployWorker.run_script`
   → `deploy_script(profile, port, <write>/<slot>.py, slot)`。信号回主线程更新进度/日志/状态栏。
   忙碌时锁定下发/保存/模板/槽位/串口/切换/ActivityBar（沿用 `_on_state` + `set_locked`）。

## 错误处理

- 编译失败 / 串口打开失败 / 传输失败 → `error` 信号 → 弹窗 + 状态 `error` + 日志红字，与固件页一致。
- 保存失败（IO 错误）→ 弹窗提示，不改 clean/dirty 态。

## 视觉

- VS Code Dark+，颜色取 `theme.*`，全局圆角 2px（圆形按钮特例）。
- 圆形按钮浮在编辑器内部右上角，叠在文本上、右上对齐。
- 布局：上（模板+保存）/ 中（编辑器 stretch=1）/ 下（进度+日志）。

## 测试策略

- `tests/gui/test_code_editor.py`：行号随行数变化、Tab 插入空格、高亮器对关键字/字符串/注释产生
  格式（用 `highlightBlock` 或格式区间断言）。
- `tests/gui/test_script_editor_page.py`：模板下拉加载内容、选空白清空、dirty/clean 切换、
  槽位菜单范围随 max_slot、保存写文件到 write 目录 `<slot>.py`、未保存下发被中止并提示、
  空内容/无串口下发被拦、进度/日志/状态更新（手动 emit 信号驱动）。
- `tests/gui/test_main_window.py`：editor 项启用、scripts 项隐藏、导航到编辑页、脚本下发线程接线
  （用 fake transport/deployer 或手动 emit，不碰真串口）。
- `tests/backend/test_profile.py`：max_slot 解析、templates_dir 推导。
- worker：`run_script` 用 DeviceSimulator + fake serial 验证下发链路（对齐现有 worker 线程测试）。

## 非目标（YAGNI）

- 不做查找替换、括号自动配对、自动补全（编辑器只做行号+高亮+缩进+当前行）。
- 不做多标签页 / 多文件同时编辑。
- 不迁移到 PyQt/QScintilla。
- 不做模板的增删改管理（模板文件由用户手动放入 templates 目录）。
