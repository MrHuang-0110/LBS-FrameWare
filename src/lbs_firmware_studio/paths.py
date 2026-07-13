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
