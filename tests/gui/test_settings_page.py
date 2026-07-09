import yaml
from pathlib import Path
from lbs_firmware_studio.gui.pages.settings_page import SettingsPage


def _raw():
    return {"compiler_path": "./tools/rust-msc-latest-win10.exe",
            "products": {"NEW-AI": {"protocol": "custom_frame"}}}


def test_shows_compiler_path(qtbot, tmp_path):
    w = SettingsPage(_raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    assert "rust-msc" in w.compiler_path_text()


def test_edit_and_save_writes_yaml(qtbot, tmp_path):
    cfg = tmp_path / "products.yaml"
    w = SettingsPage(_raw(), cfg); qtbot.addWidget(w)
    w.set_compiler_path("D:/tools/new-compiler.exe")
    w.save()
    back = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert back["compiler_path"] == "D:/tools/new-compiler.exe"
