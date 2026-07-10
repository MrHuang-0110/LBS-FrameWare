from pathlib import Path
from lbs_firmware_studio.gui.pages.script_editor_page import ScriptEditorPage
from lbs_firmware_studio.backend.profile import DeviceProfile


def _profile(tmp_path):
    tpl = tmp_path / "templates"; tpl.mkdir()
    (tpl / "blink.py").write_text("led.on()\n", encoding="utf-8")
    write = tmp_path / "write"; write.mkdir()
    return DeviceProfile(name="NEW-AI", protocol="custom_frame",
                         script_dirs={write: tmp_path / "app"},
                         templates_dir=tpl, max_slot=19)


def test_templates_listed(qtbot, tmp_path):
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    names = page.template_names()
    assert "(空白)" == names[0]
    assert "blink.py" in names


def test_select_template_loads_content(qtbot, tmp_path):
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    page.select_template("blink.py")
    assert page.editor_text() == "led.on()\n"
    assert page.is_dirty() is False   # 加载后为 clean


def test_select_blank_clears(qtbot, tmp_path):
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    page.select_template("blink.py")
    page.select_template("(空白)")
    assert page.editor_text() == ""


def test_edit_marks_dirty(qtbot, tmp_path):
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    page._editor.set_text("changed")
    assert page.is_dirty() is True


def test_save_writes_slot_py(qtbot, tmp_path):
    prof = _profile(tmp_path)
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(prof)
    page._editor.set_text("y = 2\n")
    page._set_slot(3)
    assert page.save() is True
    write_dir = next(iter(prof.script_dirs))   # key 是 write 目录
    saved = write_dir / "3.py"
    assert saved.read_text(encoding="utf-8") == "y = 2\n"
    assert page.is_dirty() is False


from PySide6.QtCore import Qt


def test_slot_menu_range_follows_max_slot(qtbot, tmp_path):
    prof = _profile(tmp_path)   # max_slot=19
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(prof)
    assert page.slot_menu_values() == list(range(0, 20))


def test_slot_menu_single_when_max_slot_zero(qtbot, tmp_path):
    prof = _profile(tmp_path); prof.max_slot = 0
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(prof)
    assert page.slot_menu_values() == [0]


def test_deploy_blocked_when_no_port(qtbot, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    page.set_port_getter(lambda: None)   # 无串口
    page._editor.set_text("z = 3\n"); page.save()
    fired = []
    page.deploy_requested.connect(lambda p, s: fired.append((p, s)))
    page._on_deploy()
    assert fired == []   # 被拦截，未发下发信号


def test_deploy_blocked_when_dirty(qtbot, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    page.set_port_getter(lambda: "COM3")
    page._editor.set_text("dirty content")   # 未保存
    fired = []
    page.deploy_requested.connect(lambda p, s: fired.append((p, s)))
    page._on_deploy()
    assert fired == []   # 未保存被拦截


def test_deploy_emits_when_valid(qtbot, tmp_path, monkeypatch):
    prof = _profile(tmp_path)
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(prof)
    page.set_port_getter(lambda: "COM3")
    page._set_slot(2)
    page._editor.set_text("w = 4\n"); page.save()
    fired = []
    page.deploy_requested.connect(lambda p, s: fired.append((p, s)))
    page._on_deploy()
    write_dir = next(iter(prof.script_dirs))
    assert fired == [(write_dir / "2.py", 2)]
