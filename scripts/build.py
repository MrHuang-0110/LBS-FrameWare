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
