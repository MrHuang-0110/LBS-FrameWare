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
    assert "固件更新" in labels and "代码编辑" in labels and "设置" in labels
    assert "脚本下发" not in labels          # scripts 项已隐藏（合并进代码编辑页）
    assert w.is_nav_enabled("固件更新") is True
    assert w.is_nav_enabled("代码编辑") is True   # editor 现已启用


def test_nav_switches_page(qtbot, tmp_path):
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w.navigate("设置")
    assert w.current_page_name() == "设置"


def test_switch_product_button_emits(qtbot, tmp_path):
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    with qtbot.waitSignal(w.switch_product_requested, timeout=500):
        w.click_switch_product()


def test_state_updates_statusbar_and_locks(qtbot, tmp_path):
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w._on_state("transfering")
    assert w.is_busy() is True
    assert "传输" in w.status_bar_text()
    w._on_state("done")
    assert w.is_busy() is False


def test_start_firmware_no_port_returns_early(qtbot, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(w._port, "selected_port", lambda: None)
    w._start_firmware()  # no port -> early return, must not become busy / crash
    assert w.is_busy() is False


def test_start_firmware_reentrancy_guard(qtbot, tmp_path):
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w._on_state("transfering")   # simulate busy
    assert w.is_busy() is True
    w._start_firmware()          # busy -> guard returns, no second thread
    assert w._thread is None     # never created a thread while busy


def test_navigate_to_editor_page(qtbot, tmp_path):
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w.navigate("代码编辑")
    assert w.current_page_name() == "代码编辑"


def test_start_script_no_port_returns_early(qtbot, tmp_path, monkeypatch):
    from pathlib import Path as _P
    from PySide6.QtWidgets import QMessageBox
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(w._port, "selected_port", lambda: None)
    w._start_script(_P("x/0.py"), 0)   # 无串口 -> 提前返回，不进入 busy
    assert w.is_busy() is False
    assert w._thread is None


def test_start_script_reentrancy_guard(qtbot, tmp_path):
    from pathlib import Path as _P
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w._on_state("transfering")   # 模拟忙
    w._start_script(_P("x/0.py"), 0)
    assert w._thread is None      # 忙时不建第二个线程
