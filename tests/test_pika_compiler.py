import pathlib, subprocess
from unittest.mock import patch
import pytest
from lbs_firmware_studio.backend.pika_compiler import compile_py


def test_compile_success(monkeypatch, tmp_path):
    py = tmp_path / "main.py"; py.write_text("print(1)")
    out = tmp_path / "main.py.o"
    compiler = tmp_path / "rust-msc.exe"; compiler.write_bytes(b"")

    def fake_run(cmd, cwd=None, capture_output=True, text=True, encoding=None, errors=None):
        # 模拟编译器写出 .o
        out_path = pathlib.Path(cmd[cmd.index("-o") + 1])
        out_path.write_bytes(b"\x0F\x70 79o\x00")  # magic .pyo
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = compile_py(py, out, compiler)
    assert result == out and out.exists()


def test_compile_failure_raises(monkeypatch, tmp_path):
    py = tmp_path / "main.py"; py.write_text("x")
    out = tmp_path / "main.py.o"
    compiler = tmp_path / "rust-msc.exe"; compiler.write_bytes(b"")
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a[0], 1, stdout="", stderr="syntax error"))
    with pytest.raises(RuntimeError, match="exit=1"):
        compile_py(py, out, compiler)


def test_compile_missing_compiler(tmp_path):
    with pytest.raises(FileNotFoundError):
        compile_py(tmp_path / "a.py", tmp_path / "a.py.o", tmp_path / "nope.exe")
