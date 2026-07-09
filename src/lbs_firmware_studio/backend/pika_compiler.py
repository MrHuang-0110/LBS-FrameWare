"""调用 rust-msc 编译器把 .py 编译成 .py.o 字节码。"""
from __future__ import annotations
import subprocess
from pathlib import Path


def compile_py(py_path: Path, out_path: Path, compiler_path: Path, cwd: Path | None = None) -> Path:
    if not compiler_path.is_file():
        raise FileNotFoundError(f"compiler not found: {compiler_path}")
    if not py_path.is_file():
        raise FileNotFoundError(f"source not found: {py_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [str(compiler_path), "-c", str(py_path), "-o", str(out_path)]
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"compile failed, exit={proc.returncode}: {proc.stderr.strip()}")
    if not out_path.is_file():
        raise FileNotFoundError(f"output not generated: {out_path}")
    return out_path
