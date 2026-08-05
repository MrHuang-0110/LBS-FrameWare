from lbs_firmware_studio.gui.widgets.activity_bar import ActivityBar
from lbs_firmware_studio.gui import theme

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


def test_locked_dims_non_current_enabled_icons(qtbot):
    w = ActivityBar(_ITEMS); qtbot.addWidget(w)
    w.set_current("firmware")   # current
    w.set_locked(True)
    # 当前项保持选中样式（白色），非当前启用项置灰
    assert w.icon_color("firmware") == theme.TEXT_ON_ACCENT
    assert w.icon_color("settings") == theme.ICON_DISABLED
    # 解锁后恢复：当前仍白，其余回到 idle
    w.set_locked(False)
    assert w.current_key() == "firmware"
    assert w.icon_color("firmware") == theme.TEXT_ON_ACCENT
    assert w.icon_color("settings") == theme.ICON_IDLE


# ---- 浮窗触发图标（Task 1）：浮窗类 key 点击只发 action_triggered，页面类仍走 current_changed ----
_POPUP_ITEMS = [
    ("device", "fa5s.microchip", True),
    ("firmware", "fa5s.download", True),
]


def test_popup_icon_click_emits_action_triggered_only(qtbot):
    """浮窗类图标（device）：点击只发 action_triggered，不发 current_changed，不改变选中态。"""
    w = ActivityBar(_POPUP_ITEMS); qtbot.addWidget(w)
    current, actions = [], []
    w.current_changed.connect(current.append)
    w.action_triggered.connect(actions.append)
    w._buttons["device"].click()
    assert actions == ["device"]
    assert current == []
    assert w.current_key() is None   # 浮窗触发不切页、不改变选中态


def test_page_icon_click_emits_current_changed_only(qtbot):
    """页面类图标（firmware）：点击只发 current_changed，不发 action_triggered。"""
    w = ActivityBar(_POPUP_ITEMS); qtbot.addWidget(w)
    current, actions = [], []
    w.current_changed.connect(current.append)
    w.action_triggered.connect(actions.append)
    w._buttons["firmware"].click()
    assert current == ["firmware"]
    assert actions == []
    assert w.current_key() == "firmware"


def test_popup_key_via_custom_keys(qtbot):
    """构造参数 popup_keys 可自定义浮窗类集合（默认 _POPUP_KEYS={"device","sensor"}）。"""
    w = ActivityBar(_POPUP_ITEMS, popup_keys={"firmware"}); qtbot.addWidget(w)
    actions = []
    w.action_triggered.connect(actions.append)
    w._buttons["firmware"].click()   # firmware 被标为浮窗类 → 只发 action_triggered
    assert actions == ["firmware"]
    assert w.current_key() is None


# ---- 底部设置键（布局重构 v3 Task 1）：settings_key 沉底渲染，点击发 action_triggered，不参与选中态 ----
_NAV_ITEMS = [
    ("device", "fa5s.microchip", True),
    ("editor", "fa5s.code", True),
    ("settings", "fa5s.cog", True),
]


def test_settings_key_excluded_from_nav_keys(qtbot):
    """settings_key 指定底部键：nav_keys() 不含它（nav 语义）；keys() 仍含全部项。"""
    w = ActivityBar(_NAV_ITEMS, settings_key="settings"); qtbot.addWidget(w)
    assert w.nav_keys() == ["device", "editor"]
    assert w.keys() == ["device", "editor", "settings"]


def test_settings_click_emits_action_without_nav(qtbot):
    """底部设置键点击：发 action_triggered("settings")，不发 current_changed，不改变选中态。"""
    w = ActivityBar(_NAV_ITEMS, settings_key="settings"); qtbot.addWidget(w)
    w.set_current("editor")
    current, actions = [], []
    w.current_changed.connect(current.append)
    w.action_triggered.connect(actions.append)
    w._buttons["settings"].click()
    assert actions == ["settings"]
    assert current == []
    assert w.current_key() == "editor"


def test_settings_key_not_selectable(qtbot):
    """settings_key 不参与选中态：set_current 拒绝它（settings 不成为页面）。"""
    w = ActivityBar(_NAV_ITEMS, settings_key="settings"); qtbot.addWidget(w)
    w.set_current("editor")
    w.set_current("settings")
    assert w.current_key() == "editor"
