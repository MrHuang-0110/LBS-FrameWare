from lbs_firmware_studio.gui.widgets.activity_bar import ActivityBar

# items: (key, icon_name, enabled)
_ITEMS = [
    ("firmware", "fa5s.download", True),
    ("scripts", "fa5s.upload", False),
    ("settings", "fa5s.cog", True),
]


def test_keys_and_enabled(qtbot):
    w = ActivityBar(_ITEMS); qtbot.addWidget(w)
    assert w.keys() == ["firmware", "scripts", "settings"]
    assert w.is_enabled("firmware") is True
    assert w.is_enabled("scripts") is False


def test_click_enabled_emits_current_changed(qtbot):
    w = ActivityBar(_ITEMS); qtbot.addWidget(w)
    with qtbot.waitSignal(w.current_changed, timeout=500) as blocker:
        w.set_current("settings")
    assert blocker.args == ["settings"]
    assert w.current_key() == "settings"


def test_disabled_item_not_selectable(qtbot):
    w = ActivityBar(_ITEMS); qtbot.addWidget(w)
    w.set_current("firmware")
    w.set_current("scripts")   # 禁用项：忽略
    assert w.current_key() == "firmware"


def test_set_locked_blocks_switch(qtbot):
    w = ActivityBar(_ITEMS); qtbot.addWidget(w)
    w.set_current("firmware")
    w.set_locked(True)
    w.set_current("settings")  # 锁定中：忽略
    assert w.current_key() == "firmware"
    w.set_locked(False)
    w.set_current("settings")
    assert w.current_key() == "settings"
