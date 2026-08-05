import pytest
from PySide6.QtWidgets import QApplication
from lbs_firmware_studio.backend.ble_scanner import BleDevice
from lbs_firmware_studio.gui.widgets.connection_selector import ConnectionSelector


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _FakePort:
    def __init__(self, device, desc):
        self.device = device; self.description = desc; self.vid = None; self.pid = None


def test_default_kind_serial_and_target(app):
    cs = ConnectionSelector(port_lister=lambda: [_FakePort("COM3", "LBS Serial")],
                            ble_scan=lambda timeout=5.0: [])
    # 串口枚举已异步化，测试用同步注入
    cs._port.inject_ports([_FakePort("COM3", "LBS Serial")])
    assert cs.selected_kind() == "serial"
    assert cs.selected_target() == "COM3"
    assert cs.selected_name() is None


def test_switch_to_ble_lists_devices_and_target(app, qtbot):
    cs = ConnectionSelector(
        port_lister=lambda: [],
        ble_scan=lambda timeout=5.0: [BleDevice("ECB02", "AA:BB", -40)])
    cs._port.inject_ports([])
    cs.set_kind("ble")
    cs.scan_ble()                        # 触发后台扫描
    qtbot.waitUntil(lambda: cs._ble_combo.count() > 0, timeout=2000)  # 等后台填充完成
    assert cs.selected_kind() == "ble"
    assert cs.selected_target() == "AA:BB"
    assert cs.selected_name() == "ECB02"


def test_make_transport_by_kind(app, qtbot):
    from lbs_firmware_studio.backend.serial_transport import SerialTransport
    from lbs_firmware_studio.backend.ble_transport import BleTransport
    cs = ConnectionSelector(port_lister=lambda: [_FakePort("COM3", "x")],
                            ble_scan=lambda timeout=5.0: [BleDevice("ECB02", "AA:BB", -40)])
    cs._port.inject_ports([_FakePort("COM3", "x")])
    assert isinstance(cs.make_transport(), SerialTransport)
    cs.set_kind("ble"); cs.scan_ble()
    qtbot.waitUntil(lambda: cs._ble_combo.count() > 0, timeout=2000)  # 等后台填充完成
    assert isinstance(cs.make_transport(), BleTransport)


def test_radio_qss_converged_into_global(app):
    """E1：QRadioButton 样式收敛进 theme.app_qss()（indicator 16px 绿色小圆点），
    connection_selector 不再维护局部 _RADIO_QSS。"""
    from lbs_firmware_studio.gui import theme
    cs = ConnectionSelector(port_lister=lambda: [], ble_scan=lambda t: [])
    assert cs._rb_serial.styleSheet() == ""      # 无局部 QSS
    assert "QRadioButton::indicator" in theme.app_qss()


def test_transport_lost_updates_ui_to_disconnected(app, qtbot):
    """链路丢失（拔线/BLE 断开，transport 内部线程调回调）：经 _transport_lost 信号
    排队到主线程 → UI 切回未连接 + connection_changed(False)（用户反馈：拔线后不实时刷新）。"""
    import time

    class FakeTrans:
        def set_disconnected_callback(self, cb):
            self._cb = cb

        def open(self, port, baud):
            pass

        def start_rx(self):
            pass

        def close(self):
            pass

    cs = ConnectionSelector(port_lister=lambda: [_FakePort("COM3", "x")],
                            ble_scan=lambda timeout=5.0: [],
                            serial_factory=lambda: FakeTrans())
    cs._port.inject_ports([_FakePort("COM3", "x")])
    qtbot.addWidget(cs)
    cs.set_baud_getter(lambda: 115200)
    events = []
    cs.connection_changed.connect(lambda ok: events.append(ok))
    cs.connect()
    # 等后台建连 done → _transport 落成
    qtbot.waitUntil(lambda: cs.is_connected(), timeout=2000)
    trans = cs._transport
    assert trans is not None
    # 模拟拔线：transport 内部线程调用注册的回调 → 信号排队到主线程
    trans._cb()
    qtbot.waitUntil(lambda: not cs.is_connected(), timeout=2000)
    assert events and events[-1] is False
    assert "连接" in cs._connect_btn.text()
    assert cs._dot.toolTip() == "未连接"

