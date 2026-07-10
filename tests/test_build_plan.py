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
