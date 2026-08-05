"""ProductSelector 顶栏产品选择器测试（qtbot）。

覆盖：初始化展示当前产品、触发器开合弹层、单击选择发信号并关层、
当前项高亮、程序化切换、锁定禁用、键盘导航。
"""
from PySide6.QtCore import Qt

from lbs_firmware_studio.backend.profile import DeviceProfile
from lbs_firmware_studio.gui.widgets.product_selector import ProductSelector


def _profiles():
    return {name: DeviceProfile(name=name, protocol="custom_frame")
            for name in ("NEW-AI", "SPARK-AI", "NEXT-AI")}


def test_init_shows_current_product(qtbot):
    sel = ProductSelector(_profiles(), "NEW-AI")
    qtbot.addWidget(sel)
    assert "NEW-AI" in sel.trigger_button().text()
    assert sel.current_product() == "NEW-AI"
    assert sel.product_names() == ["NEW-AI", "SPARK-AI", "NEXT-AI"]


def test_click_trigger_opens_popup(qtbot):
    sel = ProductSelector(_profiles(), "NEW-AI")
    qtbot.addWidget(sel)
    assert sel.is_popup_open() is False
    # 第一次点击展开
    sel.trigger_button().click()
    assert sel.is_popup_open() is True
    # 再次点击收起
    sel.trigger_button().click()
    assert sel.is_popup_open() is False
    # Esc 收起
    sel.trigger_button().click()
    assert sel.is_popup_open() is True
    qtbot.keyClick(sel._list, Qt.Key_Escape)
    assert sel.is_popup_open() is False


def test_select_product_emits_and_closes(qtbot):
    sel = ProductSelector(_profiles(), "NEW-AI")
    qtbot.addWidget(sel)
    sel.trigger_button().click()
    assert sel.is_popup_open() is True
    with qtbot.waitSignal(sel.product_changed, timeout=500) as blocker:
        sel._list.itemClicked.emit(sel._list.item(1))  # SPARK-AI
    assert blocker.args == ["SPARK-AI"]
    assert sel.is_popup_open() is False
    assert sel.current_product() == "SPARK-AI"
    assert "SPARK-AI" in sel.trigger_button().text()


def test_current_item_highlighted(qtbot):
    sel = ProductSelector(_profiles(), "NEW-AI")
    qtbot.addWidget(sel)
    sel.trigger_button().click()
    assert sel._list.currentRow() == 0
    assert sel._list.item(0).isSelected() is True
    assert sel._list.item(1).isSelected() is False
    # 收起后程序化切换，再打开时高亮跟随新当前项
    sel.trigger_button().click()
    assert sel.is_popup_open() is False
    sel.select_product("SPARK-AI")
    sel.trigger_button().click()
    assert sel._list.currentRow() == 1
    assert sel._list.item(1).isSelected() is True
    assert sel._list.item(0).isSelected() is False


def test_programmatic_select(qtbot):
    sel = ProductSelector(_profiles(), "NEW-AI")
    qtbot.addWidget(sel)
    assert sel.select_product("NEXT-AI") is True
    assert sel.current_product() == "NEXT-AI"
    # 不存在的名字返回 False 且 current 不变
    assert sel.select_product("UNKNOWN") is False
    assert sel.current_product() == "NEXT-AI"


def test_set_locked_disables_trigger(qtbot):
    sel = ProductSelector(_profiles(), "NEW-AI")
    qtbot.addWidget(sel)
    sel.trigger_button().click()
    assert sel.is_popup_open() is True
    sel.set_locked(True)
    assert sel.trigger_button().isEnabled() is False
    assert sel.is_popup_open() is False
    # 锁定时程序化切换也应被拒绝
    assert sel.select_product("SPARK-AI") is False
    assert sel.current_product() == "NEW-AI"
    sel.set_locked(False)
    assert sel.trigger_button().isEnabled() is True
    assert sel.select_product("SPARK-AI") is True
    assert sel.current_product() == "SPARK-AI"


def test_keyboard_navigation(qtbot):
    sel = ProductSelector(_profiles(), "NEW-AI")
    qtbot.addWidget(sel)
    sel.trigger_button().click()
    assert sel.is_popup_open() is True
    qtbot.keyClick(sel._list, Qt.Key_Down)
    assert sel._list.currentRow() == 1
    with qtbot.waitSignal(sel.product_changed, timeout=500) as blocker:
        qtbot.keyClick(sel._list, Qt.Key_Return)
    assert blocker.args == ["SPARK-AI"]
    assert sel.current_product() == "SPARK-AI"
    assert sel.is_popup_open() is False
