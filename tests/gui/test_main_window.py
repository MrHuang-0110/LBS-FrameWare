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
    assert "固件与监控" in labels and "代码编辑" in labels and "设置" in labels
    assert "脚本下发" not in labels          # scripts 项已隐藏（合并进代码编辑页）
    assert "固件更新" not in labels          # 固件更新已合并进"固件与监控"
    assert "数据监控" not in labels          # 数据监控已合并进"固件与监控"
    assert w.is_nav_enabled("固件与监控") is True
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
    monkeypatch.setattr(w._conn, "selected_target", lambda: None)
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
    monkeypatch.setattr(w._conn, "selected_target", lambda: None)
    w._start_script(_P("x/0.py"), 0)   # 无串口 -> 提前返回，不进入 busy
    assert w.is_busy() is False
    assert w._thread is None


def test_start_script_reentrancy_guard(qtbot, tmp_path):
    from pathlib import Path as _P
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w._on_state("transfering")   # 模拟忙
    w._start_script(_P("x/0.py"), 0)
    assert w._thread is None      # 忙时不建第二个线程


def test_main_window_initial_size(qtbot, tmp_path):
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    # resize 在无 show 时 size() 可能未生效，断言 minimumSize（最稳）
    assert w.minimumWidth() >= 900
    assert w.minimumHeight() >= 600
    assert (w.minimumWidth(), w.minimumHeight()) == (900, 600)


def test_device_nav_enabled(qtbot, tmp_path):
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    assert "固件与监控" in w.nav_labels()
    assert w.is_nav_enabled("固件与监控") is True


def test_navigate_to_device_page(qtbot, tmp_path):
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w.navigate("代码编辑")
    w.navigate("固件与监控")
    assert w.current_page_name() == "固件与监控"


def test_leaving_device_stops_monitor(qtbot, tmp_path):
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w.navigate("固件与监控")
    w._monitor._monitoring = True  # 模拟监控正在运行
    stopped = []
    w._monitor.stop_monitor = lambda: stopped.append(True)  # 打桩
    w.navigate("设置")     # 离开设备页到非编辑页
    assert stopped == [True]


def test_connection_auto_starts_monitor(qtbot, tmp_path):
    """连接成功后自动开始监控，断开后自动停止（无需手动按钮）。"""
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    started, stopped = [], []
    w._monitor.start_monitor = lambda: started.append(True)
    w._monitor.stop_monitor = lambda: stopped.append(True)
    w._on_connection_changed(True)
    assert started == [True] and stopped == []
    w._on_connection_changed(False)
    assert stopped == [True]


def test_monitor_start_button_hidden(qtbot, tmp_path):
    """监控自动启动后，手动"开始监控"按钮不再显示。"""
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    assert w._monitor._start_btn.isVisible() is False
