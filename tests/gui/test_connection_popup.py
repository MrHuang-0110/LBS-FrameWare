"""ConnectionPopup 设备连接浮窗测试（qtbot）。

覆盖：构造显示当前产品、Qt.Popup 窗口标志与固定宽度、标题存在、
点产品项透传 product_changed、连接区控件齐备（radio/端口下拉/刷新/连接按钮/状态点）、
连接区竖向堆叠、set_locked 禁用产品选择与连接按钮。
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from lbs_firmware_studio.backend.profile import DeviceProfile
from lbs_firmware_studio.gui.widgets.connection_popup import ConnectionPopup
from lbs_firmware_studio.gui.widgets.connection_selector import ConnectionSelector


def _profiles():
    return {name: DeviceProfile(name=name, protocol="custom_frame")
            for name in ("NEW-AI", "SPARK-AI", "NEXT-AI")}


def _popup(qtbot, **kw):
    popup = ConnectionPopup(_profiles(), "NEW-AI",
                            port_lister=lambda: [], ble_scan=lambda t: [], **kw)
    qtbot.addWidget(popup)
    return popup


def test_init_shows_current_product(qtbot):
    popup = _popup(qtbot)
    assert isinstance(popup, QWidget)
    assert popup.current_product() == "NEW-AI"
    assert "NEW-AI" in popup._product.trigger_button().text()


def test_is_popup_window_with_fixed_width(qtbot):
    popup = _popup(qtbot)
    assert popup.windowFlags() & Qt.Popup
    assert popup.minimumWidth() == 300
    assert popup.maximumWidth() == 300


def test_title_present(qtbot):
    popup = _popup(qtbot)
    labels = [lbl.text() for lbl in popup.findChildren(QLabel)]
    assert "设备连接" in labels


def test_product_changed_passthrough(qtbot):
    popup = _popup(qtbot)
    popup._product.trigger_button().click()
    assert popup._product.is_popup_open() is True
    with qtbot.waitSignal(popup.product_changed, timeout=500) as blocker:
        popup._product._list.itemClicked.emit(popup._product._list.item(1))  # SPARK-AI
    assert blocker.args == ["SPARK-AI"]
    assert popup.current_product() == "SPARK-AI"


def test_connection_section_controls_exist(qtbot):
    popup = _popup(qtbot)
    conn = popup.connection()
    assert isinstance(conn, ConnectionSelector)
    # 串口/蓝牙 radio
    assert conn._rb_serial.isChecked() is True
    assert conn._rb_ble is not None
    # 端口下拉 + 刷新
    assert conn._port._combo is not None
    assert conn._port._refresh_btn.text() == "刷新"
    # 连接按钮 + 状态点
    assert conn._connect_btn.text() == "连接"
    assert conn._dot is not None


def test_connection_section_vertical(qtbot):
    """连接区在浮窗内为竖向堆叠：radio 一行 / 下拉+刷新 一行 / 连接按钮+状态点 一行。"""
    popup = _popup(qtbot)
    assert isinstance(popup.connection().layout(), QVBoxLayout)


def test_set_locked_disables_product_and_connect(qtbot):
    popup = _popup(qtbot)
    assert popup._product.trigger_button().isEnabled() is True
    assert popup.connection()._connect_btn.isEnabled() is True
    popup.set_locked(True)
    assert popup._product.trigger_button().isEnabled() is False
    assert popup.connection()._connect_btn.isEnabled() is False
    popup.set_locked(False)
    assert popup._product.trigger_button().isEnabled() is True
    assert popup.connection()._connect_btn.isEnabled() is True
