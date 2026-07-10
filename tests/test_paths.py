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
    # 模拟项目根探测失败：把 _dev_root 指向一个无 products.yaml 的目录
    import lbs_firmware_studio.paths as paths_mod
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(paths_mod, "_dev_root", lambda: tmp_path)  # tmp_path 无 products.yaml
    monkeypatch.chdir(tmp_path)
    assert base_dir() == tmp_path   # 回退 cwd（此处 cwd==tmp_path）
