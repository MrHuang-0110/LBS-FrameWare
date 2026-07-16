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


def test_deploy_blocked_when_slot_not_saved(qtbot, tmp_path, monkeypatch):
    # 编辑并保存到槽0(clean)后切到槽5(该槽无文件)，下发应被存在性校验拦截。
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    page.set_port_getter(lambda: "COM3")
    page._editor.set_text("saved = 0\n"); page.save()   # 保存到槽0 -> clean
    page._set_slot(5)                                     # 切到槽5(无文件)
    fired = []
    page.deploy_requested.connect(lambda p, s: fired.append((p, s)))
    page._on_deploy()
    assert fired == []   # 目标文件不存在，被拦截


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


def test_progress_and_state_and_log(qtbot, tmp_path):
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    page.on_progress(50, 100)
    assert page.progress_value() == 50
    page.on_state("transfering")
    assert "传输" in page.stage_text()
    page.on_log("compile 0.py -> 0.o")
    assert "0.o" in page.log_text()


def test_set_busy_disables_controls(qtbot, tmp_path):
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    page.set_busy(True)
    assert page._deploy_btn.isEnabled() is False
    assert page._save_btn.isEnabled() is False
    page.set_busy(False)
    assert page._deploy_btn.isEnabled() is True


def test_load_file_loads_content_and_clean(qtbot, tmp_path):
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    src = tmp_path / "any.py"
    src.write_text("import time\nx = 1\n", encoding="utf-8")
    assert page.load_file(str(src)) is True
    assert page.editor_text() == "import time\nx = 1\n"
    assert page.is_dirty() is False
    assert "any.py" in page.log_text()


def test_open_button_exists(qtbot, tmp_path):
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    assert hasattr(page, "_open_btn")
    assert "打开" in page._open_btn.text()


def test_log_has_max_height(qtbot, tmp_path):
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    assert page._log.maximumHeight() <= 140


def test_set_busy_disables_open(qtbot, tmp_path):
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    page.set_busy(True)
    assert page._open_btn.isEnabled() is False
    page.set_busy(False)
    assert page._open_btn.isEnabled() is True


def test_run_pause_buttons_exist(qtbot, tmp_path):
    """运行和暂停按钮在页面创建后存在。"""
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    assert hasattr(page, "_run_btn")
    assert hasattr(page, "_pause_btn")
    assert "运行" in page._run_btn.toolTip()
    assert "暂停" in page._pause_btn.toolTip()


def test_run_pause_buttons_initially_disabled(qtbot, tmp_path):
    """初始状态（未知）两个按钮均禁用。"""
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    assert page._run_btn.isEnabled() is False
    assert page._pause_btn.isEnabled() is False


def test_run_pause_buttons_are_children_of_editor(qtbot, tmp_path):
    """运行/暂停按钮是编辑器子控件（浮动定位）。"""
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    assert page._run_btn.parent() is page._editor
    assert page._pause_btn.parent() is page._editor


def test_on_host_state_changed_start_enables_pause_disables_run(qtbot, tmp_path):
    """监控状态 start → 运行禁用、暂停启用。"""
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    page.set_has_target(True)
    page.on_host_state_changed("start")
    assert page._run_btn.isEnabled() is False
    assert page._pause_btn.isEnabled() is True


def test_on_host_state_changed_stop_enables_run_disables_pause(qtbot, tmp_path):
    """监控状态 stop → 运行启用、暂停禁用。"""
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    page.set_has_target(True)
    page.on_host_state_changed("stop")
    assert page._run_btn.isEnabled() is True
    assert page._pause_btn.isEnabled() is False


def test_on_host_state_changed_empty_disables_both(qtbot, tmp_path):
    """监控状态 "" → 监控未运行，两按钮均禁用。"""
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    page.set_has_target(True)
    page.on_host_state_changed("stop")   # 先设一个有效状态
    page.on_host_state_changed("")        # 再清空 → 监控停止
    assert page._run_btn.isEnabled() is False
    assert page._pause_btn.isEnabled() is False


def test_run_button_click_emits_run_toggle(qtbot, tmp_path):
    """点击运行按钮 emit run_toggle_requested 信号，并乐观切换状态。"""
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    page.set_has_target(True)
    page.on_host_state_changed("stop")   # 初始：已暂停
    fired = []
    page.run_toggle_requested.connect(lambda: fired.append(True))
    page._run_btn.click()
    assert fired == [True]
    # 乐观更新：运行按钮禁用、暂停按钮启用
    assert page._run_btn.isEnabled() is False
    assert page._pause_btn.isEnabled() is True


def test_pause_button_click_emits_run_toggle(qtbot, tmp_path):
    """点击暂停按钮 emit run_toggle_requested 信号，并乐观切换状态。"""
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    page.set_has_target(True)
    page.on_host_state_changed("start")  # 初始：运行中
    fired = []
    page.run_toggle_requested.connect(lambda: fired.append(True))
    page._pause_btn.click()
    assert fired == [True]
    # 乐观更新：暂停按钮禁用、运行按钮启用
    assert page._pause_btn.isEnabled() is False
    assert page._run_btn.isEnabled() is True


def test_set_busy_disables_run_pause_buttons(qtbot, tmp_path):
    """下发忙碌时运行/暂停按钮均禁用。"""
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    page.set_has_target(True)
    page.on_host_state_changed("stop")   # 运行按钮应启用
    assert page._run_btn.isEnabled() is True
    page.set_busy(True)
    assert page._run_btn.isEnabled() is False
    assert page._pause_btn.isEnabled() is False
    page.set_busy(False)
    assert page._run_btn.isEnabled() is True   # 恢复


def test_set_busy_false_restores_run_state(qtbot, tmp_path):
    """忙碌结束后恢复为运行状态对应的按钮启用态。"""
    page = ScriptEditorPage(); qtbot.addWidget(page)
    page.set_profile(_profile(tmp_path))
    page.set_has_target(True)
    page.on_host_state_changed("start")  # 运行中
    page.set_busy(True)
    assert page._run_btn.isEnabled() is False
    page.set_busy(False)
    assert page._run_btn.isEnabled() is False   # 运行中，运行按钮仍禁用
    assert page._pause_btn.isEnabled() is True  # 运行中，暂停按钮启用
