from pathlib import Path
import importlib.util


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


def test_spec_file_has_key_settings():
    root = Path(__file__).resolve().parents[1]
    spec = (root / "LBS-Firmware-Studio.spec").read_text(encoding="utf-8")
    assert "entry.py" in spec                   # 顶层入口垫片(非 app.py，相对导入冻结后会报错)
    assert "qtawesome" in spec                 # 字体数据收集
    assert "COLLECT" in spec                   # onedir（非 onefile）
    assert "LBS-Firmware-Studio" in spec       # 产物名
    assert "bleak" in spec                     # BLE 后端隐藏导入


def test_entry_shim_uses_absolute_import_of_main():
    """打包入口必须以绝对导入暴露 main：回归 'attempted relative import with no
    known parent package'——冻结后入口作为 __main__ 运行，相对导入无父包会崩。"""
    root = Path(__file__).resolve().parents[1]
    entry = (root / "scripts" / "entry.py").read_text(encoding="utf-8")
    assert "from lbs_firmware_studio.gui.app import main" in entry
    assert "main()" in entry



def test_pyproject_has_build_extra():
    root = Path(__file__).resolve().parents[1]
    txt = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "pyinstaller" in txt.lower()
