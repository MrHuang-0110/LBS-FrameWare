# GUI 打包分发 + 固件路径可选 · 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 LBS Firmware Studio 打包成 Windows onedir 可分发文件夹（PyInstaller），去除 cwd 依赖，并让用户在设置页为每个产品自选固件目录（写回 products.yaml）。

**Architecture:** 三块改动，依赖顺序 块1→块2/块3。块1：新增 `paths.base_dir()`（入口层定位 products.yaml），`load_profiles` 按 yaml 自身位置 resolve 内部相对路径为绝对，backend 不感知打包。块2：设置页每产品一行固件目录选择，写回 products.yaml。块3：PyInstaller `.spec`（onedir）+ `scripts/build.py`（构建后复制资源到输出旁，不含 fwlib）。

**Tech Stack:** Python 3.13、PySide6、PyYAML、pytest/pytest-qt、PyInstaller>=6（可选 build 依赖）。

## Global Constraints

- Python 3.13、Windows；运行测试用 `python -m pytest`（非 python3）。
- backend 层纯逻辑、不感知打包：`base_dir()` 只在入口层（app.py/cli.py）；`load_profiles(path)` 只按 `path.parent` resolve。
- 深色主题 theme.*，禁止硬编码色值（设置页沿用现有样式，不引入新色值）。
- 必须 onedir 模式（onefile 写回配置/固件会丢）。
- 固件库 fwlib **不**进分发包；products.yaml、tools/、各产品 templates/ 与 write/ 复制到输出旁。
- 写回 products.yaml 用绝对路径；保存后「重启生效」，不做热重载。
- GUI 测试用 pytest-qt qtbot + qtbot.addWidget，可按文件单跑、容忍 teardown 段错误（以断言为准）；不碰真串口。
- 事件/信号处理器先 super() 再 emit。

---

## File Structure

**新增:**
- `src/lbs_firmware_studio/paths.py` — `base_dir()`，入口层定位资源根。
- `LBS-Firmware-Studio.spec` — PyInstaller onedir 打包配置。
- `scripts/build.py` — 一键构建 + 资源复制；含可测纯函数 `plan_resource_copy`。

**修改:**
- `src/lbs_firmware_studio/backend/profile.py` — `load_profiles` resolve 内部相对路径为绝对。
- `src/lbs_firmware_studio/gui/app.py` — 入口用 `base_dir()/products.yaml`。
- `src/lbs_firmware_studio/cli.py` — `--config` 默认 None，回退 `base_dir()/products.yaml`。
- `src/lbs_firmware_studio/gui/pages/settings_page.py` — 每产品固件目录行 + 保存写回。
- `pyproject.toml` — 加 `[project.optional-dependencies] build`。
- `tests/test_profile.py` — 更新受 resolve 影响的断言。

**新增测试:**
- `tests/test_paths.py`、`tests/test_profile_resolve.py`、`tests/test_build_plan.py`
- 修改 `tests/gui/test_settings_page.py`

---

## Task 1: paths.base_dir()

**Files:**
- Create: `src/lbs_firmware_studio/paths.py`
- Test: `tests/test_paths.py`

**Interfaces:**
- Consumes: 无。
- Produces: `base_dir() -> Path`。打包(`sys.frozen`)返回 `Path(sys.executable).parent`；开发返回项目根（`paths.py` 上溯 2 层，即含 products.yaml 的根）；若该根无 products.yaml 则回退 `Path.cwd()`。

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_paths.py
import sys
from pathlib import Path
from lbs_firmware_studio.paths import base_dir


def test_dev_mode_returns_project_root_with_products_yaml():
    d = base_dir()
    assert (d / "products.yaml").is_file()   # 开发态：项目根含 products.yaml


def test_frozen_mode_returns_exe_dir(monkeypatch, tmp_path):
    fake_exe = tmp_path / "app" / "LBS-Firmware-Studio.exe"
    fake_exe.parent.mkdir(parents=True)
    fake_exe.write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))
    assert base_dir() == fake_exe.parent


def test_dev_mode_fallback_to_cwd_when_root_missing(monkeypatch, tmp_path):
    # 模拟项目根探测失败：把 _project_root 指向一个无 products.yaml 的目录
    import lbs_firmware_studio.paths as paths_mod
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(paths_mod, "_dev_root", lambda: tmp_path)  # tmp_path 无 products.yaml
    monkeypatch.chdir(tmp_path)
    assert base_dir() == tmp_path   # 回退 cwd（此处 cwd==tmp_path）
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_paths.py -v`
Expected: FAIL（`ModuleNotFoundError: lbs_firmware_studio.paths`）

- [ ] **Step 3: Write minimal implementation**

```python
# src/lbs_firmware_studio/paths.py
"""资源根定位：打包(sys.frozen)时为 exe 同级目录，开发时为项目根。
只供入口层(app.py/cli.py)使用；backend 不依赖此模块。"""
from __future__ import annotations
import sys
from pathlib import Path


def _dev_root() -> Path:
    # src/lbs_firmware_studio/paths.py -> parents[2] = 项目根
    return Path(__file__).resolve().parents[2]


def base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    root = _dev_root()
    if (root / "products.yaml").is_file():
        return root
    return Path.cwd()   # 目录结构异常时回退，不崩溃
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_paths.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/paths.py tests/test_paths.py
git commit -m "feat: base_dir() resource-root locator for frozen/dev"
```

---

## Task 2: load_profiles resolve 内部相对路径

**Files:**
- Modify: `src/lbs_firmware_studio/backend/profile.py`
- Test: `tests/test_profile_resolve.py`
- Modify: `tests/test_profile.py`（更新 templates_dir 断言）

**Interfaces:**
- Consumes: 无（backend 内部）。
- Produces: `load_profiles(path)` 返回的 `DeviceProfile` 中 `compiler_path`、`firmware_dir`、`script_dirs`（key/value）、`templates_dir` 均为**绝对路径**，基准是 `path.resolve().parent`。绝对路径输入原样保留。

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_profile_resolve.py
import textwrap
from pathlib import Path
from lbs_firmware_studio.backend.profile import load_profiles


def _write(tmp_path):
    yaml_text = textwrap.dedent("""
        compiler_path: ./tools/comp.exe
        products:
          NEW-AI:
            protocol: custom_frame
            firmware_dir: ./products/NEW-AI/fwlib
            script_dirs: {./products/NEW-AI/write: ./products/NEW-AI/app}
    """)
    p = tmp_path / "products.yaml"; p.write_text(yaml_text)
    return p


def test_firmware_dir_resolved_absolute(tmp_path):
    p = _write(tmp_path)
    prof = load_profiles(p)["NEW-AI"]
    assert prof.firmware_dir.is_absolute()
    assert prof.firmware_dir == (tmp_path / "products/NEW-AI/fwlib").resolve()


def test_compiler_path_resolved_absolute(tmp_path):
    p = _write(tmp_path)
    prof = load_profiles(p)["NEW-AI"]
    assert prof.compiler_path == (tmp_path / "tools/comp.exe").resolve()


def test_script_dirs_key_and_value_resolved(tmp_path):
    p = _write(tmp_path)
    prof = load_profiles(p)["NEW-AI"]
    items = list(prof.script_dirs.items())
    assert items[0][0] == (tmp_path / "products/NEW-AI/write").resolve()
    assert items[0][1] == (tmp_path / "products/NEW-AI/app").resolve()


def test_templates_dir_resolved_absolute(tmp_path):
    p = _write(tmp_path)
    prof = load_profiles(p)["NEW-AI"]
    assert prof.templates_dir == (tmp_path / "products/NEW-AI/templates").resolve()


def test_absolute_input_preserved(tmp_path):
    abs_fw = (tmp_path / "elsewhere" / "fw").resolve()
    yaml_text = f"""
compiler_path: ./tools/comp.exe
products:
  NEW-AI:
    protocol: custom_frame
    firmware_dir: {abs_fw.as_posix()}
"""
    p = tmp_path / "products.yaml"; p.write_text(yaml_text)
    prof = load_profiles(p)["NEW-AI"]
    assert prof.firmware_dir == abs_fw   # 绝对路径原样
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_profile_resolve.py -v`
Expected: FAIL（当前返回相对路径，`is_absolute()` 为 False / 不等于绝对期望）

- [ ] **Step 3: Modify profile.py**

3a. 在 `load_profiles` 顶部（读取 raw 之前）确定 base，并加内部 helper。当前代码：

```python
def load_profiles(path: Path) -> dict[str, DeviceProfile]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    compiler = Path(raw.get("compiler_path", "./tools/rust-msc-latest-win10.exe"))
```

改为：

```python
def _resolve(base: Path, p) -> Path:
    """相对路径基于 base 解析为绝对；绝对路径原样(经 resolve 规整)。"""
    p = Path(p)
    return p.resolve() if p.is_absolute() else (base / p).resolve()


def load_profiles(path: Path) -> dict[str, DeviceProfile]:
    path = Path(path).resolve()
    base = path.parent
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    compiler = _resolve(base, raw.get("compiler_path", "./tools/rust-msc-latest-win10.exe"))
```

3b. 在构造 `DeviceProfile` 处，把 4 个路径字段改用 `_resolve(base, ...)`。当前代码：

```python
            compiler_path=compiler,
            script_dirs={Path(k): Path(v) for k, v in cfg.get("script_dirs", {}).items()},
            firmware_dir=Path(cfg.get("firmware_dir", ".")),
            reopen_retries=cfg.get("reopen_retries", 5),
            reopen_delay=cfg.get("reopen_delay", 2.0),
            post_reopen_delay=cfg.get("post_reopen_delay", 5.0),
            disappear_timeout=cfg.get("disappear_timeout", 5.0),
            display_ports=cfg.get("display_ports", 0),
            max_slot=cfg.get("max_slot", 0),
            templates_dir=Path(cfg.get("firmware_dir", ".")).parent / "templates",
```

改为（`compiler` 已在 3a resolve 完成，直接用）：

```python
            compiler_path=compiler,
            script_dirs={_resolve(base, k): _resolve(base, v) for k, v in cfg.get("script_dirs", {}).items()},
            firmware_dir=_resolve(base, cfg.get("firmware_dir", ".")),
            reopen_retries=cfg.get("reopen_retries", 5),
            reopen_delay=cfg.get("reopen_delay", 2.0),
            post_reopen_delay=cfg.get("post_reopen_delay", 5.0),
            disappear_timeout=cfg.get("disappear_timeout", 5.0),
            display_ports=cfg.get("display_ports", 0),
            max_slot=cfg.get("max_slot", 0),
            templates_dir=_resolve(base, Path(cfg.get("firmware_dir", ".")).parent / "templates"),
```

- [ ] **Step 4: Update the stale assertion in tests/test_profile.py**

`test_max_slot_and_templates_dir` 末尾断言当前期望相对路径，改为绝对：

```python
    # templates_dir 推导为 firmware_dir 的父目录下的 templates（现 resolve 为绝对）
    assert profiles["NEW-AI"].templates_dir == (p.parent / "products/NEW-AI/templates").resolve()
```

（`p` 是该测试里 `tmp_path / "products.yaml"`，`Path` 已在文件顶部 import。）

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_profile_resolve.py tests/test_profile.py -v`
Expected: PASS（新 5 + 原 2，共 7 passed）

- [ ] **Step 6: Commit**

```bash
git add src/lbs_firmware_studio/backend/profile.py tests/test_profile_resolve.py tests/test_profile.py
git commit -m "feat(backend): resolve yaml-relative paths against config dir"
```

---

## Task 3: 入口层用 base_dir 定位 products.yaml

**Files:**
- Modify: `src/lbs_firmware_studio/gui/app.py`
- Modify: `src/lbs_firmware_studio/cli.py`
- Test: `tests/test_cli.py`（新增用例，验证默认 config 回退）

**Interfaces:**
- Consumes: `paths.base_dir()`（Task 1）。
- Produces: app `main()` 用 `base_dir()/"products.yaml"`；cli `main()` 在 `--config` 未给时回退 `base_dir()/"products.yaml"`。

- [ ] **Step 1: Write the failing test**（追加到 `tests/test_cli.py`）

先看现有 test_cli.py 的风格再追加。新增一个用例：不传 `--config` 且用 `--list` 时，应能从 base_dir 加载（这里 monkeypatch base_dir 指向 tmp yaml）：

```python
def test_cli_defaults_config_to_base_dir(tmp_path, monkeypatch, capsys):
    import lbs_firmware_studio.cli as cli
    yaml_text = "compiler_path: ./c.exe\nproducts:\n  NEW-AI:\n    protocol: custom_frame\n"
    (tmp_path / "products.yaml").write_text(yaml_text)
    monkeypatch.setattr(cli, "base_dir", lambda: tmp_path)
    rc = cli.main(["--list"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "NEW-AI" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py::test_cli_defaults_config_to_base_dir -v`
Expected: FAIL（`AttributeError: module ... has no attribute 'base_dir'` 或 config 默认仍 "products.yaml"）

- [ ] **Step 3: Modify app.py**

顶部 import 加：

```python
from ..paths import base_dir
```

把 `main()` 中：

```python
    config_path = Path("products.yaml")
```

改为：

```python
    config_path = base_dir() / "products.yaml"
```

- [ ] **Step 4: Modify cli.py**

顶部 import 加：

```python
from .paths import base_dir
```

把 argparse 默认与加载改为回退式。当前：

```python
    parser.add_argument("--config", default="products.yaml")
    ...
    profiles = load_profiles(Path(args.config))
```

改为：

```python
    parser.add_argument("--config", default=None)
    ...
    config = Path(args.config) if args.config else base_dir() / "products.yaml"
    profiles = load_profiles(config)
```

（`base_dir` 作为模块级名字导入，测试可 monkeypatch `cli.base_dir`。）

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py -v`
Expected: PASS（原有用例 + 新用例）

- [ ] **Step 6: Commit**

```bash
git add src/lbs_firmware_studio/gui/app.py src/lbs_firmware_studio/cli.py tests/test_cli.py
git commit -m "feat: entry points locate products.yaml via base_dir"
```

---

## Task 4: 设置页每产品固件目录选择

**Files:**
- Modify: `src/lbs_firmware_studio/gui/pages/settings_page.py`
- Test: `tests/gui/test_settings_page.py`（新增用例）

**Interfaces:**
- Consumes: `save_profiles`（已有）。
- Produces: `SettingsPage` 新增：为 `raw_config["products"]` 每个 key 渲染一行固件目录（只读 QLineEdit + 浏览按钮）；`save()` 除写回 compiler_path，另把各产品固件目录写回 `raw["products"][name]["firmware_dir"]`。测试访问器：`firmware_dir_text(name: str) -> str`、`set_firmware_dir(name: str, path: str) -> None`、`product_rows() -> list[str]`。

- [ ] **Step 1: Write the failing tests**（追加到 `tests/gui/test_settings_page.py`）

```python
def _raw_multi():
    return {"compiler_path": "./tools/comp.exe",
            "products": {
                "NEW-AI": {"protocol": "custom_frame", "firmware_dir": "./products/NEW-AI/fwlib"},
                "SPARK-AI": {"protocol": "custom_frame", "firmware_dir": "./products/SPARK-AI/fwlib"},
            }}


def test_renders_row_per_product(qtbot, tmp_path):
    w = SettingsPage(_raw_multi(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    assert set(w.product_rows()) == {"NEW-AI", "SPARK-AI"}


def test_shows_initial_firmware_dir(qtbot, tmp_path):
    w = SettingsPage(_raw_multi(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    assert w.firmware_dir_text("NEW-AI") == "./products/NEW-AI/fwlib"


def test_save_writes_firmware_dirs(qtbot, tmp_path):
    import yaml
    cfg = tmp_path / "products.yaml"
    w = SettingsPage(_raw_multi(), cfg); qtbot.addWidget(w)
    w.set_firmware_dir("NEW-AI", "D:/fw/new-ai")
    w.save()
    back = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert back["products"]["NEW-AI"]["firmware_dir"] == "D:/fw/new-ai"
    assert back["products"]["SPARK-AI"]["firmware_dir"] == "./products/SPARK-AI/fwlib"  # 未改保持


def test_browse_cancel_keeps_value(qtbot, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **k: "")  # 取消
    w = SettingsPage(_raw_multi(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w._browse_firmware("NEW-AI")
    assert w.firmware_dir_text("NEW-AI") == "./products/NEW-AI/fwlib"   # 未变
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/gui/test_settings_page.py -v`
Expected: FAIL（`product_rows`/`firmware_dir_text` 不存在）

- [ ] **Step 3: Rewrite settings_page.py**

完整替换文件内容：

```python
"""设置页：编辑编译器路径 + 每产品固件目录，保存写回 products.yaml。"""
from __future__ import annotations
from pathlib import Path
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QFileDialog, QGroupBox)
from ...backend.profile import save_profiles


class SettingsPage(QWidget):
    def __init__(self, raw_config: dict, config_path: Path, parent=None):
        super().__init__(parent)
        self._raw = raw_config
        self._path = Path(config_path)
        self._compiler = QLineEdit(str(raw_config.get("compiler_path", "")))
        browse = QPushButton("浏览"); browse.clicked.connect(self._browse)
        self._status = QLabel("")
        save_btn = QPushButton("保存"); save_btn.setObjectName("primary")
        save_btn.clicked.connect(self.save)

        # 每产品固件目录行
        self._fw_edits: dict[str, QLineEdit] = {}
        fw_group = QGroupBox("固件目录（每产品）")
        fw_lay = QVBoxLayout(fw_group)
        for name, cfg in raw_config.get("products", {}).items():
            edit = QLineEdit(str(cfg.get("firmware_dir", "")))
            edit.setReadOnly(True)
            btn = QPushButton("浏览…")
            btn.clicked.connect(lambda _=False, n=name: self._browse_firmware(n))
            row = QHBoxLayout()
            row.addWidget(QLabel(name)); row.addWidget(edit, 1); row.addWidget(btn)
            fw_lay.addLayout(row)
            self._fw_edits[name] = edit

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("设置"))
        row = QHBoxLayout(); row.addWidget(QLabel("编译器路径:"))
        row.addWidget(self._compiler, 1); row.addWidget(browse)
        lay.addLayout(row)
        lay.addWidget(fw_group)
        lay.addWidget(save_btn)
        lay.addWidget(self._status)
        lay.addStretch()

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择编译器", "", "可执行文件 (*.exe);;所有文件 (*)")
        if path:
            self._compiler.setText(path)

    def _browse_firmware(self, name: str) -> None:
        path = QFileDialog.getExistingDirectory(self, f"选择 {name} 固件目录", "")
        if path:
            self._fw_edits[name].setText(path)

    def set_compiler_path(self, path: str) -> None:
        self._compiler.setText(path)

    def compiler_path_text(self) -> str:
        return self._compiler.text()

    # --- 固件目录访问器 ---
    def product_rows(self) -> list[str]:
        return list(self._fw_edits.keys())

    def firmware_dir_text(self, name: str) -> str:
        return self._fw_edits[name].text()

    def set_firmware_dir(self, name: str, path: str) -> None:
        self._fw_edits[name].setText(path)

    def save(self) -> None:
        self._raw["compiler_path"] = self._compiler.text()
        for name, edit in self._fw_edits.items():
            self._raw["products"][name]["firmware_dir"] = edit.text()
        save_profiles(self._raw, self._path)
        self._status.setText("已保存，重启后生效")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/gui/test_settings_page.py -v`
Expected: PASS（原 2 + 新 4，共 6 passed）

- [ ] **Step 5: Commit**

```bash
git add src/lbs_firmware_studio/gui/pages/settings_page.py tests/gui/test_settings_page.py
git commit -m "feat(gui): per-product firmware dir selection in settings"
```

---

## Task 5: build.py 资源复制清单（纯逻辑）

**Files:**
- Create: `scripts/build.py`
- Test: `tests/test_build_plan.py`

**Interfaces:**
- Consumes: 无。
- Produces: `plan_resource_copy(src_root: Path, dst_root: Path) -> list[tuple[Path, Path]]`：返回 (源, 目标) 复制清单——含 `products.yaml`、`tools/`、每个 `products/<产品>/templates` 与 `products/<产品>/write`；**不含** 任何 `fwlib`。产品列表由 `src_root/products/` 下的子目录决定。

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_build_plan.py
from pathlib import Path
import sys, importlib.util


def _load_build():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("build_mod", root / "scripts" / "build.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def _make_src(tmp_path):
    (tmp_path / "products.yaml").write_text("products: {}")
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "comp.exe").write_bytes(b"")
    for name in ("NEW-AI", "SPARK-AI"):
        base = tmp_path / "products" / name
        (base / "fwlib" / "app").mkdir(parents=True)
        (base / "templates").mkdir(parents=True)
        (base / "write").mkdir(parents=True)
    return tmp_path


def test_plan_includes_yaml_and_tools(tmp_path):
    build = _load_build()
    src = _make_src(tmp_path); dst = tmp_path / "out"
    plan = build.plan_resource_copy(src, dst)
    srcs = {s for s, _ in plan}
    assert (src / "products.yaml") in srcs
    assert (src / "tools") in srcs


def test_plan_includes_templates_and_write_per_product(tmp_path):
    build = _load_build()
    src = _make_src(tmp_path); dst = tmp_path / "out"
    plan = build.plan_resource_copy(src, dst)
    srcs = {s for s, _ in plan}
    assert (src / "products" / "NEW-AI" / "templates") in srcs
    assert (src / "products" / "NEW-AI" / "write") in srcs
    assert (src / "products" / "SPARK-AI" / "templates") in srcs


def test_plan_excludes_fwlib(tmp_path):
    build = _load_build()
    src = _make_src(tmp_path); dst = tmp_path / "out"
    plan = build.plan_resource_copy(src, dst)
    for s, _ in plan:
        assert "fwlib" not in s.parts   # 固件库绝不复制


def test_plan_targets_under_dst(tmp_path):
    build = _load_build()
    src = _make_src(tmp_path); dst = tmp_path / "out"
    plan = build.plan_resource_copy(src, dst)
    for _, d in plan:
        assert str(d).startswith(str(dst))   # 目标都在 dst 下
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_build_plan.py -v`
Expected: FAIL（`scripts/build.py` 不存在 / 无 `plan_resource_copy`）

- [ ] **Step 3: Write scripts/build.py**

```python
"""一键构建：PyInstaller onedir + 复制资源到输出目录旁（不含 fwlib 固件库）。
用法: python scripts/build.py
"""
from __future__ import annotations
import shutil
import subprocess
import sys
from pathlib import Path

SPEC = "LBS-Firmware-Studio.spec"
DIST_NAME = "LBS-Firmware-Studio"


def plan_resource_copy(src_root: Path, dst_root: Path) -> list[tuple[Path, Path]]:
    """算出要复制的 (源, 目标) 清单：products.yaml、tools/、各产品 templates/ 与 write/。
    不含 fwlib。产品由 src_root/products/ 下的子目录决定。"""
    plan: list[tuple[Path, Path]] = []
    yaml_src = src_root / "products.yaml"
    if yaml_src.is_file():
        plan.append((yaml_src, dst_root / "products.yaml"))
    tools_src = src_root / "tools"
    if tools_src.is_dir():
        plan.append((tools_src, dst_root / "tools"))
    products = src_root / "products"
    if products.is_dir():
        for prod in sorted(p for p in products.iterdir() if p.is_dir()):
            for sub in ("templates", "write"):
                s = prod / sub
                if s.is_dir():
                    plan.append((s, dst_root / "products" / prod.name / sub))
    return plan


def _copy(plan: list[tuple[Path, Path]]) -> None:
    for src, dst in plan:
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("未安装 PyInstaller，请先: pip install -e .[build]", file=sys.stderr)
        return 1
    rc = subprocess.call([sys.executable, "-m", "PyInstaller", SPEC, "--noconfirm"], cwd=root)
    if rc != 0:
        return rc
    dst_root = root / "dist" / DIST_NAME
    _copy(plan_resource_copy(root, dst_root))
    print(f"构建完成: {dst_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_build_plan.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add scripts/build.py tests/test_build_plan.py
git commit -m "feat(build): resource-copy plan (yaml/tools/templates/write, no fwlib)"
```

---

## Task 6: PyInstaller spec + pyproject build 依赖

**Files:**
- Create: `LBS-Firmware-Studio.spec`
- Modify: `pyproject.toml`
- Test: `tests/test_build_plan.py`（追加：spec 文件存在且含关键项的静态检查）

**Interfaces:**
- Consumes: 无。
- Produces: `LBS-Firmware-Studio.spec`（onedir，入口 app.py，收集 qtawesome 数据，excludes 测试）；pyproject 新增 `[project.optional-dependencies] build = ["pyinstaller>=6"]`。

- [ ] **Step 1: Write the failing test**（追加到 `tests/test_build_plan.py`）

spec 是 PyInstaller 执行的 Python 脚本，不在单测里 exec（依赖 PyInstaller 运行时符号）。改为静态断言其含关键配置：

```python
def test_spec_file_has_key_settings():
    root = Path(__file__).resolve().parents[1]
    spec = (root / "LBS-Firmware-Studio.spec").read_text(encoding="utf-8")
    assert "app.py" in spec                    # 入口
    assert "qtawesome" in spec                 # 字体数据收集
    assert "COLLECT" in spec                   # onedir（非 onefile）
    assert "LBS-Firmware-Studio" in spec       # 产物名


def test_pyproject_has_build_extra():
    root = Path(__file__).resolve().parents[1]
    txt = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "pyinstaller" in txt.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_build_plan.py::test_spec_file_has_key_settings tests/test_build_plan.py::test_pyproject_has_build_extra -v`
Expected: FAIL（spec 不存在；pyproject 无 pyinstaller）

- [ ] **Step 3: Write LBS-Firmware-Studio.spec**

```python
# -*- mode: python ; coding: utf-8 -*-
# PyInstaller onedir 打包配置。资源(products.yaml/products/tools)不在此收集，
# 由 scripts/build.py 于构建后复制到 dist/LBS-Firmware-Studio/ 旁。
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

datas = collect_data_files("qtawesome")   # fontawesome 字体 .ttf/.json

a = Analysis(
    ["src/lbs_firmware_studio/gui/app.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=["serial.tools.list_ports"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "tests"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LBS-Firmware-Studio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="LBS-Firmware-Studio",
)
```

- [ ] **Step 4: Modify pyproject.toml**

在 `[project.scripts]` 段之后追加：

```toml
[project.optional-dependencies]
build = ["pyinstaller>=6"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_build_plan.py -v`
Expected: PASS（全部，含新 2）

- [ ] **Step 6: Commit**

```bash
git add LBS-Firmware-Studio.spec pyproject.toml tests/test_build_plan.py
git commit -m "feat(build): PyInstaller onedir spec + build extra dependency"
```

---

## Task 7: 文档（构建步骤 + 首次设固件目录）

**Files:**
- Create: `docs/BUILD.md`

**Interfaces:**
- Consumes: 无。
- Produces: `docs/BUILD.md` 说明构建与首次使用。

- [ ] **Step 1: Write docs/BUILD.md**

```markdown
# 构建与分发

## 构建 onedir 可分发文件夹

1. 安装构建依赖：`pip install -e .[build]`
2. 运行：`python scripts/build.py`
3. 产物在 `dist/LBS-Firmware-Studio/`：
   - `LBS-Firmware-Studio.exe`（双击运行）
   - `_internal/`（依赖，勿删）
   - `products.yaml`、`tools/`、`products/<产品>/templates|write`
   - **不含 fwlib 固件库**——由用户自选目录

整个 `dist/LBS-Firmware-Studio/` 文件夹即可压缩分发。

## 首次使用：设置固件目录

分发包不带固件库。用户首次要用「固件更新」前：

1. 启动后进入 **设置** 页。
2. 在「固件目录（每产品）」区，为对应产品点 **浏览…** 选择本地 fwlib 目录。
3. 点 **保存**（写回 products.yaml），提示「已保存，重启后生效」。
4. 重启程序，固件目录生效。

脚本编辑/数据监控功能无需固件目录即可使用。
```

- [ ] **Step 2: Commit**

```bash
git add docs/BUILD.md
git commit -m "docs: build and first-run firmware-dir setup guide"
```

- [ ] **Step 3: 集成手动验证（非自动测试，记录到报告）**

在装了 build 依赖的环境执行 `python scripts/build.py`，确认：dist 文件夹生成、双击 exe 能启动到启动窗、products.yaml/tools/templates/write 在 exe 同级、无 fwlib。（此步由人工执行，实施子代理仅记录待验证项，不因无 PyInstaller 而阻塞。）

---

## Self-Review

**1. Spec coverage:**
- base_dir 定位 → Task 1 ✓
- load_profiles resolve（compiler/firmware_dir/script_dirs/templates_dir，绝对幂等）→ Task 2 ✓
- 入口层 app/cli 用 base_dir → Task 3 ✓
- 设置页每产品固件目录 + 写回绝对 + 重启生效 → Task 4 ✓
- build.py 复制清单（yaml/tools/templates/write，不含 fwlib）→ Task 5 ✓
- PyInstaller onedir spec + qtawesome datas + excludes + pyproject build extra → Task 6 ✓
- 文档（构建 + 首次设固件）→ Task 7 ✓
- 错误处理：base_dir 回退 cwd（Task 1 测试）、resolve 先 path.resolve（Task 2）、浏览取消不改值（Task 4）、PyInstaller 未装提示（Task 5 main）✓

**2. Placeholder scan:** 无 TBD/TODO；每个 code step 均含完整代码。集成验证（Task 7 Step 3）明确标注为人工步骤，非自动测试占位。

**3. Type consistency:**
- `base_dir() -> Path`：Task 1 定义，Task 3 用（app/cli import）✓
- `_resolve(base, p) -> Path`：Task 2 内部，一致 ✓
- 设置页访问器 `product_rows/firmware_dir_text/set_firmware_dir/_browse_firmware`：Task 4 定义与测试一致 ✓
- `plan_resource_copy(src_root, dst_root) -> list[tuple[Path,Path]]`：Task 5 定义与测试一致 ✓
- cli monkeypatch 点 `cli.base_dir`：Task 3 以模块级 import 暴露，测试可 patch ✓

无签名冲突、无悬空引用。
