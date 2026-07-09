from lbs_firmware_studio.gui.main_window import MainWindow
from lbs_firmware_studio.backend.profile import DeviceProfile
from pathlib import Path


def _profile():
    return DeviceProfile(name="NEW-AI", protocol="custom_frame", display_ports=8,
                         folders=["app", "version"], firmware_dir=Path("./x"))


def _raw():
    return {"compiler_path": "./t.exe", "products": {"NEW-AI": {"protocol": "custom_frame"}}}


def test_shows_product_name(qtbot, tmp_path):
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    assert "NEW-AI" in w.header_text()


def test_nav_items_present_and_locked(qtbot, tmp_path):
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    labels = w.nav_labels()
    assert "固件更新" in labels
    assert "脚本下发" in labels  # 存在但置灰
    assert "设置" in labels
    # 固件更新可用，脚本下发禁用
    assert w.is_nav_enabled("固件更新") is True
    assert w.is_nav_enabled("脚本下发") is False


def test_nav_switches_page(qtbot, tmp_path):
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w.navigate("设置")
    assert w.current_page_name() == "设置"


def test_switch_product_button_emits(qtbot, tmp_path):
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    with qtbot.waitSignal(w.switch_product_requested, timeout=500):
        w.click_switch_product()


def test_state_updates_badge_and_locks(qtbot, tmp_path):
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    # 模拟 deployer 发状态：transfering -> 锁定、状态灯琥珀
    w._on_state("transfering")
    assert w.is_busy() is True
    w._on_state("done")
    assert w.is_busy() is False


def test_start_firmware_no_port_returns_early(qtbot, tmp_path, monkeypatch):
    # 未选串口 -> 提前返回，不创建线程、不置忙
    import lbs_firmware_studio.gui.main_window as mw
    monkeypatch.setattr(mw.QMessageBox, "warning", lambda *a, **k: None)
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w._port.selected_port = lambda: None
    w._start_firmware()
    assert w._thread is None
    assert w.is_busy() is False


def test_start_firmware_reentrancy_guard(qtbot, tmp_path):
    # 已忙时二次点击 -> 不创建第二个线程
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w._port.selected_port = lambda: "COM_FAKE"
    w._on_state("transfering")  # 置忙
    assert w.is_busy() is True
    w._start_firmware()
    assert w._thread is None  # 忙时不创建线程
