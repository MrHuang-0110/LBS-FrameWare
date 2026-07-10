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
