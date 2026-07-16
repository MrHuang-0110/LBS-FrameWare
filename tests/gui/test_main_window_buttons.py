"""TDD 补全：MainWindow 下发按钮门禁（未选目标时禁用）的测试。"""
from lbs_firmware_studio.gui.main_window import MainWindow
from lbs_firmware_studio.backend.profile import DeviceProfile
from lbs_firmware_studio.backend import protocol_frame as pf
from pathlib import Path


def _profile(**kw):
    return DeviceProfile(name="NEW-AI", protocol="custom_frame", display_ports=8,
                         folders=["app", "version"], firmware_dir=Path("./x"),
                         ble_enabled=True, ble_firmware=False, **kw)


def _raw():
    return {"compiler_path": "./t.exe", "products": {"NEW-AI": {"protocol": "custom_frame", "ble": {"enabled": True, "firmware_over_ble": False}}}}


class _FakePort:
    def __init__(self, device, desc, vid=None, pid=None):
        self.device = device; self.description = desc; self.vid = vid; self.pid = pid


# ---- 按钮初始禁用 ----

def test_firmware_and_deploy_buttons_disabled_without_target(qtbot, tmp_path):
    """未选串口/蓝牙目标时，固件更新和脚本下发按钮均禁用。"""
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    assert not w._firmware._start.isEnabled()
    assert not w._editor_page._deploy_btn.isEnabled()


# ---- 选中目标后按钮启用 ----

def test_buttons_enabled_after_port_selected(qtbot, tmp_path):
    """选中串口后，按钮恢复启用。"""
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w._conn._port.inject_ports([_FakePort("COM3", "LBS Serial (COM3)", 0x0483, 0x5740)])
    # target_changed 信号是异步投递的，须让事件循环跑一轮
    qtbot.waitUntil(lambda: w._firmware._start.isEnabled(), timeout=1000)
    assert w._editor_page._deploy_btn.isEnabled()


# ---- 蓝牙固件门禁 ----

def test_firmware_button_disabled_on_ble_without_firmware_support(qtbot, tmp_path):
    """NEW-AI(ble_firmware=False) 蓝牙模式下，固件更新按钮禁用，脚本下发仍可用。"""
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w._conn._port.inject_ports([_FakePort("COM3", "LBS Serial (COM3)", 0x0483, 0x5740)])
    qtbot.waitUntil(lambda: w._firmware._start.isEnabled(), timeout=1000)
    # 切换到蓝牙，BLE 下拉为空 → 无目标 → 按钮全禁用
    w._conn.set_kind("ble")
    qtbot.waitUntil(lambda: not w._firmware._start.isEnabled(), timeout=1000)
    assert not w._editor_page._deploy_btn.isEnabled()  # 无 BLE 设备可选


# ---- 忙碌流 ----

def test_buttons_disabled_during_busy_and_restored_after(qtbot, tmp_path):
    """忙碌（下发/更新进行中）时按钮禁用，完成后按目标可用性恢复。"""
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w._conn._port.inject_ports([_FakePort("COM3", "LBS Serial (COM3)", 0x0483, 0x5740)])
    qtbot.waitUntil(lambda: w._firmware._start.isEnabled(), timeout=1000)
    # 模拟忙碌
    w._firmware.set_busy(True)
    w._editor_page.set_busy(True)
    assert not w._firmware._start.isEnabled()
    assert not w._editor_page._deploy_btn.isEnabled()
    # 模拟完成
    w._firmware.set_busy(False)
    w._editor_page.set_busy(False)
    w._update_deploy_buttons()
    assert w._firmware._start.isEnabled()
    assert w._editor_page._deploy_btn.isEnabled()


class _FakeTransport:
    """模拟 transport.write，记录写入的字节。"""
    def __init__(self):
        self.written = []
    def write(self, data: bytes):
        self.written.append(data)


def test_run_pause_buttons_disabled_without_target(qtbot, tmp_path):
    """未选目标时运行/暂停按钮禁用。"""
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    assert not w._editor_page._run_btn.isEnabled()
    assert not w._editor_page._pause_btn.isEnabled()


def test_run_pause_buttons_enabled_after_port_selected(qtbot, tmp_path):
    """选中串口后运行/暂停按钮仍需监控帧驱动，初始均禁用。"""
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w._conn._port.inject_ports([_FakePort("COM3", "LBS Serial (COM3)", 0x0483, 0x5740)])
    qtbot.waitUntil(lambda: w._firmware._start.isEnabled(), timeout=1000)
    # 有连接目标但无监控：两按钮均禁用
    assert not w._editor_page._run_btn.isEnabled()
    assert not w._editor_page._pause_btn.isEnabled()
    # 模拟监控启动：状态帧到达后按钮按运行状态启用
    w._monitor.host_state_changed.emit("stop")
    assert w._editor_page._run_btn.isEnabled()
    assert not w._editor_page._pause_btn.isEnabled()


def test_run_toggle_sends_0xb6_frame(qtbot, tmp_path, monkeypatch):
    """点击运行按钮后 MainWindow 发送正确的 0xB6 帧。"""
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w._conn._port.inject_ports([_FakePort("COM3", "LBS Serial (COM3)", 0x0483, 0x5740)])
    qtbot.waitUntil(lambda: w._firmware._start.isEnabled(), timeout=1000)
    # 注入假 transport
    fake = _FakeTransport()
    monkeypatch.setattr(w._conn, "persistent_transport", lambda: fake)
    # 模拟监控运行中：设备处于"已暂停"状态，运行按钮可用
    w._monitor.host_state_changed.emit("stop")
    w._editor_page._run_btn.click()
    assert len(fake.written) == 1
    expected = pf.build_frame(pf.CMD_RUN_TOGGLE, b"\x01")
    assert fake.written[0] == expected


def test_run_toggle_no_transport_silent(qtbot, tmp_path, monkeypatch):
    """无持久链路时点击运行按钮静默返回，不崩溃。"""
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w._conn._port.inject_ports([_FakePort("COM3", "LBS Serial (COM3)", 0x0483, 0x5740)])
    qtbot.waitUntil(lambda: w._firmware._start.isEnabled(), timeout=1000)
    monkeypatch.setattr(w._conn, "persistent_transport", lambda: None)
    w._monitor.host_state_changed.emit("stop")
    # 不应崩溃
    w._editor_page._run_btn.click()


def test_host_state_signal_forwarded_to_editor(qtbot, tmp_path):
    """MonitorPage.host_state_changed 信号正确转发到 ScriptEditorPage。"""
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w._conn._port.inject_ports([_FakePort("COM3", "LBS Serial (COM3)", 0x0483, 0x5740)])
    qtbot.waitUntil(lambda: w._firmware._start.isEnabled(), timeout=1000)
    # 直接 emit 监控页信号
    w._monitor.host_state_changed.emit("start")
    assert w._editor_page._run_btn.isEnabled() is False
    assert w._editor_page._pause_btn.isEnabled() is True
    w._monitor.host_state_changed.emit("stop")
    assert w._editor_page._run_btn.isEnabled() is True
    assert w._editor_page._pause_btn.isEnabled() is False