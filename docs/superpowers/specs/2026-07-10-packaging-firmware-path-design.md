# GUI 打包分发 + 固件路径可选 · 设计文档

> 状态：设计已与用户确认（架构/路径解析/设置页/打包/错误处理与测试 五段均通过），待写实施计划。

## 目标

把 LBS Firmware Studio 打包成 Windows 可分发的 **onedir 文件夹**（PyInstaller），让用户
双击 exe 即可运行；固件库不写死进包，用户在 **设置页** 为每个产品自选固件目录（写回
products.yaml，重启生效）。为此先做 **路径解析去 cwd 依赖** 的基础改造，使程序不再依赖
「当前工作目录 = 项目根」这一开发期假设。

## 背景与约束（已核实）

- 运行时读写的外部资源：`products.yaml`（配置，设置页会**写回**）、`products/<产品>/`
  （fwlib 固件库、templates 模板、write 脚本输出目录，脚本部署会**写入** .o）、
  `tools/rust-msc-latest-win10.exe`（外部编译器，subprocess 调用）、qtawesome 字体资源。
- 现状 cwd 依赖点：[app.py:49](src/lbs_firmware_studio/gui/app.py#L49) `Path("products.yaml")`、
  [cli.py:12](src/lbs_firmware_studio/cli.py#L12) `--config` 默认 `"products.yaml"`；
  yaml 内相对路径（`compiler_path`、`firmware_dir`、`script_dirs`）目前也按 cwd 解析。
- 因需写回配置、写入固件 .o，**必须用 onedir 模式**（onefile 解压到只读临时目录，写入会丢）。
- products/ 体积小（三产品 fwlib 合计 <1.7MB），但 `.gitignore` 忽略 `products/`（固件是本地资源）。
- 沿用项目既定：backend 只做纯逻辑不感知打包；深色主题 theme.*；测试 pytest/pytest-qt，
  Windows 用 `python`（非 python3）；GUI 测试可按文件单跑、容忍 teardown 段错误。

## 架构：三块改动及依赖关系

```
块1 路径解析去 cwd 依赖（基础，其余都依赖它）
  ├─ paths.base_dir(): 定位 products.yaml（打包=exe 同级；开发=项目根）
  └─ load_profiles(path): 按 path.parent resolve yaml 内相对路径 → 绝对
块2 设置页固件目录选择（GUI，纯功能）
  └─ 每产品一行「固件目录 + 浏览…」，保存写回 products.yaml
块3 PyInstaller 打包（构建产物）
  └─ .spec(onedir) + scripts/build.py：构建 → 复制资源到输出旁
```

**职责边界（关键设计原则）：**
- `base_dir()` 只活在入口层（app.py/cli.py），判定 `sys.frozen`。
- backend 的 `load_profiles(path)` 只按 `path.parent` resolve 内部相对路径，**不引入 base_dir 概念**，保持 backend 纯净。
- 设置页写回复用已有的 `save_profiles`。

## 块1：路径解析去 cwd 依赖

### 新增 `src/lbs_firmware_studio/paths.py`

```python
def base_dir() -> Path:
    """打包(sys.frozen)时返回 exe 所在目录；开发时返回项目根(含 products.yaml)。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[2]   # src/lbs_firmware_studio/paths.py → 项目根
```
- 错误处理：开发态若 `parents[2]` 下无 products.yaml，回退到 `Path.cwd()`，不崩溃。

### 入口层改动
- [app.py:49](src/lbs_firmware_studio/gui/app.py#L49)：`config_path = base_dir() / "products.yaml"`。
- [cli.py:12](src/lbs_firmware_studio/cli.py#L12)：`--config` 默认改为 `default=None`；`main` 里
  `config = Path(args.config) if args.config else base_dir() / "products.yaml"`（避免 argparse
  在导入期计算路径）。

### backend resolve（`profile.py` 的 `load_profiles`）
- 在 [profile.py](src/lbs_firmware_studio/backend/profile.py) 内，先 `path = path.resolve()`，
  以 `base = path.parent` 为基准把 yaml 内相对路径 resolve 成绝对：
  - 顶层 `compiler_path`（不在 products 下）
  - 每产品 `firmware_dir`、`script_dirs`（key 与 value 都要）、`templates_dir`
    （现由 `firmware_dir.parent/templates` 推导，推导后同样按 base resolve）
- 加内部 helper：`_resolve(base: Path, p) -> Path`，规则 `p if p.is_absolute() else (base / p)`，
  末尾 `.resolve()`。绝对路径幂等，相对路径基于 base。
- 更新 `test_profile.py` 中受 resolve 影响的断言（按 path.parent 基准算期望绝对值）。

## 块2：设置页固件目录选择

扩展 [settings_page.py](src/lbs_firmware_studio/gui/pages/settings_page.py)（已能编辑 compiler_path 并 save_profiles 写回）。

### 界面
在编译器路径下方，为 `raw_config["products"]` 的**每个** key 加一行（动态，不写死三个）：
```
<产品名>  固件目录:  [__只读路径__]  [浏览…]
```
- 只读 QLineEdit 显示当前 `raw_config["products"][name]["firmware_dir"]`（**原始 yaml 值**，非 resolve 后的绝对路径，保持用户可读）。
- 「浏览…」→ `QFileDialog.getExistingDirectory` 选文件夹；用户取消（空）则不改原值。

### 保存
现有「保存」按钮扩展：写回 `compiler_path` 外，把各产品选中的固件目录写回
`raw_config["products"][name]["firmware_dir"]`，调 `save_profiles(raw, path)`。
- 写回**绝对路径**（浏览选出的即绝对，最直观，支持固件在任意盘符任意目录）。
- 状态提示沿用现有「已保存，重启后生效」（不做 profile 热重载）。

### 测试
- 多产品各渲染一行固件目录（数量 = products keys 数）。
- monkeypatch `QFileDialog.getExistingDirectory` 桩返回路径 → 对应行 QLineEdit 更新。
- 保存后 `raw["products"][name]["firmware_dir"]` == 新路径，且 `save_profiles` 被调用
  （monkeypatch 捕获参数）。
- 取消浏览（桩返回空）不改原值。

## 块3：PyInstaller 打包

### `LBS-Firmware-Studio.spec`（项目根）
- 入口：`src/lbs_firmware_studio/gui/app.py`。
- 模式：**onedir**（`EXE` + `COLLECT`，非 onefile）。
- 名称：`LBS-Firmware-Studio`（暂无 .ico，后续可加 `icon=`）。
- `datas`：`collect_data_files('qtawesome')`（fontawesome 字体 .ttf/.json）。
- `hiddenimports`：必要时补 `serial.tools.list_ports`（PySide6 一般自动检测）。
- `excludes`：`pytest`、`tests`（减小体积）。
- **不**把 products.yaml / products/ / tools/ 打进包（由 build.py 复制到输出旁）。

### `scripts/build.py`（一键构建）
1. 检查 PyInstaller 是否安装；未装则提示 `pip install -e .[build]` 并退出。
2. subprocess 跑 `pyinstaller LBS-Firmware-Studio.spec --noconfirm`（覆盖已存在 dist）。
3. 构建后 `dist/LBS-Firmware-Studio/` 含 exe + `_internal/`；**复制资源到该目录旁**：
   - `products.yaml` → 输出根
   - `tools/` → 输出根（整目录）
   - 每个 `products/<产品>/` 只复制 `templates/`（模板）与 `write/`（建空目录结构）
   - **fwlib 固件库不复制**（用户在设置页自选路径）
4. products.yaml 里 firmware_dir 保持默认相对值 `./products/<产品>/fwlib`；用户首次用固件功能
   前需在设置页指定真实固件目录（目录无效时部署报错，沿用现有 deployer 行为，不新增逻辑）。

### 可测性
- 把「算复制清单/目标路径」的纯逻辑抽成可测函数 `plan_resource_copy(src_root, dst_root) -> list[(src, dst)]`。
- 单测断言清单：含 products.yaml、tools/、各产品 templates/ 与 write/；**不含** fwlib。
- PyInstaller 调用本身不在单测跑（集成手动验证）。

### pyproject.toml
```toml
[project.optional-dependencies]
build = ["pyinstaller>=6"]
```

## 错误处理汇总
- `base_dir()` 开发态目录结构异常 → 回退 cwd，不崩溃。
- `load_profiles`：`path` 相对时先 `resolve()` 再取 parent，保证 base 绝对。
- 设置页浏览取消 → 不改原值。
- 固件目录不存在 → 部署时 deployer glob 空 → 现有「无固件」报错，不新增逻辑。
- build.py：PyInstaller 未装提示装 `.[build]`；dist 已存在用 `--noconfirm` 覆盖。

## 测试（遵循 TDD）
- `paths.base_dir()`：开发态返回目录含 products.yaml；monkeypatch `sys.frozen=True`+`sys.executable` → 返回其 parent。
- `load_profiles` resolve：tmp yaml 内相对 `./x/fwlib` → 返回 `tmp/x/fwlib` 绝对；绝对输入原样。更新 `test_profile.py`。
- 设置页：多产品行渲染、浏览桩设置、保存写回 raw 且 save_profiles 被调、取消不改值。
- `plan_resource_copy`：清单含 products.yaml/tools/templates/write、不含 fwlib。

## 交付清单
1. `src/lbs_firmware_studio/paths.py`（新）
2. 改 `app.py`、`cli.py`（入口用 base_dir）
3. 改 `profile.py`（load_profiles resolve）+ 更新 `test_profile.py`
4. 改 `settings_page.py`（每产品固件目录）+ 测试
5. `LBS-Firmware-Studio.spec`（新）
6. `scripts/build.py`（新）+ 复制逻辑单测
7. `pyproject.toml` 加 `build` optional-dependency
8. 更新文档：构建步骤 + 用户首次设固件目录说明

## 交付范围（YAGNI）
- 不做 onefile；不做自动更新；不做安装器（Inno Setup 等，后续可选）。
- 不做固件目录热重载（重启生效）。
- 不做固件路径在固件页快捷更改（只设置页集中管理）。
- 不做 .ico 图标（后续补）。
