"""ConnectionPopup 设备连接浮窗测试（qtbot）。

覆盖：构造显示当前产品、Qt.Popup 窗口标志与固定宽度、标题存在、
点产品项透传 product_changed、连接区控件齐备（radio/端口下拉/刷新/连接按钮/状态点）、
连接区竖向堆叠、set_locked 禁用产品选择与连接按钮。
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMessageBox, QVBoxLayout, QWidget

from lbs_firmware_studio.backend.profile import DeviceProfile
from lbs_firmware_studio.gui import theme
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


def test_set_locked_disables_radio_group(qtbot):
    """I1：busy 锁定时串口/蓝牙 radio 组必须禁用（防止点 radio 触发断开）。"""
    popup = _popup(qtbot)
    conn = popup.connection()
    assert conn._rb_serial.isEnabled() is True
    assert conn._rb_ble.isEnabled() is True
    popup.set_locked(True)
    assert conn._rb_serial.isEnabled() is False
    assert conn._rb_ble.isEnabled() is False
    popup.set_locked(False)
    assert conn._rb_serial.isEnabled() is True
    assert conn._rb_ble.isEnabled() is True


class _FakeTransport:
    """模拟活链路：记录 close() 调用，验证 busy 锁定时不得关闭复用链路。"""
    def __init__(self):
        self.closed = False
    def close(self):
        self.closed = True


def test_set_locked_blocks_radio_disconnect_while_connected(qtbot):
    """I1：已连接 → busy 锁定 → 点蓝牙 radio 不得触发 disconnect（transport.closed 保持 False）。"""
    popup = _popup(qtbot)
    conn = popup.connection()
    # 对照组：未锁定时点 radio 会断开已连接链路（disconnect 会 close 并清空 _transport）
    t1 = _FakeTransport()
    conn._transport = t1
    conn._rb_ble.click()
    assert t1.closed is True
    assert conn.is_connected() is False
    # busy 锁定：重新建立「已连接」状态，点 radio 不得断开
    t2 = _FakeTransport()
    conn._transport = t2
    conn._connect_btn.setText("断开")
    popup.set_locked(True)
    conn._rb_ble.click()          # 禁用态下点击应无效（QAbstractButton::click no-op）
    assert t2.closed is False
    assert conn._transport is t2  # 链路仍存活
    assert conn.is_connected() is True
    # 解锁后可恢复正常切换行为（点另一个 radio 触发断开）
    popup.set_locked(False)
    conn._rb_serial.click()
    assert t2.closed is True
    assert conn.is_connected() is False


# ===== Task 2: 浮窗内嵌固件更新区 + 传感器更新按钮 =====

def test_firmware_section_controls_exist(qtbot):
    """浮窗含固件更新区：开始按钮/进度条/单行进度文本 + 传感器更新按钮。"""
    popup = _popup(qtbot)
    fw = popup.firmware_section()
    assert fw.start_button().text() == "开始固件更新"
    assert fw.progress_value() == 0
    assert fw.current_progress_text() == theme.STAGE_TEXT["idle"]
    assert popup._sensor_btn.text() == "传感器更新"
    assert popup._sensor_btn.icon() is not None


def test_firmware_section_has_dir_edit(qtbot):
    """固件源目录只读框存在（可经 set_firmware_dir_getter 填充）。"""
    popup = _popup(qtbot)
    fw = popup.firmware_section()
    assert fw._dir_edit.isReadOnly() is True


def test_set_firmware_dir_getter_updates_dir_text(qtbot):
    """set_firmware_dir_getter 透传给固件区，目录文本刷新为 getter 返回值。"""
    popup = _popup(qtbot)
    popup.set_firmware_dir_getter(lambda: "C:/fw/lib/NEW-AI")
    assert "fw/lib/NEW-AI" in popup.firmware_section().firmware_dir_text().replace("\\", "/")


def test_start_button_emits_start_firmware_requested(qtbot, monkeypatch):
    """点开始按钮（确认框 Yes）→ 发 start_firmware_requested。"""
    popup = _popup(qtbot)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    with qtbot.waitSignal(popup.start_firmware_requested, timeout=500):
        popup.firmware_section().start_button().click()


def test_sensor_button_emits_sensor_update_requested(qtbot):
    """点传感器更新按钮 → 发 sensor_update_requested。"""
    popup = _popup(qtbot)
    with qtbot.waitSignal(popup.sensor_update_requested, timeout=500):
        popup._sensor_btn.click()


def test_set_firmware_progress_updates_bar(qtbot):
    """set_firmware_progress(pct) 回填进度条。"""
    popup = _popup(qtbot)
    popup.set_firmware_progress(45)
    assert popup.firmware_section().progress_value() == 45


def test_set_firmware_text_updates_single_line(qtbot):
    """set_firmware_text(text) 回填单行进度文本。"""
    popup = _popup(qtbot)
    popup.set_firmware_text("正在发送 app/")
    assert "app/" in popup.firmware_section().current_progress_text()


def test_set_locked_disables_firmware_and_sensor(qtbot):
    """set_locked 覆盖新增控件：固件开始按钮/固件源选择/传感器按钮全部禁用。"""
    popup = _popup(qtbot)
    popup.set_firmware_dir_getter(lambda: "C:/fw/lib")
    fw = popup.firmware_section()
    assert fw.start_button().isEnabled() is True
    assert fw._dir_edit.isEnabled() is True
    assert popup._sensor_btn.isEnabled() is True
    popup.set_locked(True)
    assert fw.start_button().isEnabled() is False
    assert fw._dir_edit.isEnabled() is False
    assert popup._sensor_btn.isEnabled() is False
    popup.set_locked(False)
    assert fw.start_button().isEnabled() is True
    assert fw._dir_edit.isEnabled() is True
    assert popup._sensor_btn.isEnabled() is True
