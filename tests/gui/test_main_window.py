from lbs_firmware_studio.gui.main_window import MainWindow
from lbs_firmware_studio.backend.profile import DeviceProfile
from pathlib import Path


def _profile(**kw):
    return DeviceProfile(name="NEW-AI", protocol="custom_frame", display_ports=8,
                         folders=["app", "version"], firmware_dir=Path("./x"), **kw)


def _two_profiles(baud_new=115200, baud_spark=115200):
    """两个产品（NEW-AI 当前 + SPARK-AI 可切换），可分别指定 baud（决策点 2 测试）。"""
    return {
        "NEW-AI": _profile(baud=baud_new),
        "SPARK-AI": DeviceProfile(name="SPARK-AI", protocol="custom_frame",
                                  display_ports=4, folders=["app"],
                                  firmware_dir=Path("./x"), baud=baud_spark),
    }


def _raw():
    return {"compiler_path": "./t.exe", "products": {"NEW-AI": {"protocol": "custom_frame"}}}


def test_shows_product_name(qtbot, tmp_path):
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    assert "NEW-AI" in w.header_text()


def test_nav_items_present_and_locked(qtbot, tmp_path):
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    labels = w.nav_labels()
    assert "固件与监控" in labels and "代码编辑" in labels and "设置" in labels
    # 布局重构 v2：device/sensor 为浮窗触发入口（设备连接/传感器更新），也在侧边栏
    assert "设备连接" in labels and "传感器更新" in labels
    assert "脚本下发" not in labels          # scripts 项已隐藏（合并进代码编辑页）
    assert "固件更新" not in labels          # 固件更新已合并进"固件与监控"
    assert "数据监控" not in labels          # 数据监控已合并进"固件与监控"
    assert w.is_nav_enabled("固件与监控") is True
    assert w.is_nav_enabled("代码编辑") is True   # editor 现已启用


def test_nav_switches_page(qtbot, tmp_path):
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w.navigate("设置")
    assert w.current_page_name() == "设置"


def test_product_switch_rebuilds_pages(qtbot, tmp_path):
    """切换产品 → header 更新 + 页面栈整体重建（Firmware/Monitor/Editor 新实例，属性名保留）。"""
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml", profiles=_two_profiles())
    qtbot.addWidget(w)
    assert w.header_text() == "NEW-AI"
    old = (w._firmware, w._monitor, w._editor_page)
    w._product_selector.select_product("SPARK-AI")
    assert w.header_text() == "SPARK-AI"              # selector 当前产品
    assert w.current_page_name() == "固件与监控"        # 重建后回到默认 device 页
    assert w._firmware is not old[0]                  # 页面重建（新实例）
    assert w._monitor is not old[1]
    assert w._editor_page is not old[2]


def test_switch_blocked_when_busy(qtbot, tmp_path):
    """busy 时切换产品被拒：selector 锁定 + 守卫回滚，header 不变。"""
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml", profiles=_two_profiles())
    qtbot.addWidget(w)
    w._on_state("transfering")
    assert w.is_busy() is True
    assert w._product_selector.select_product("SPARK-AI") is False   # 锁定拒绝
    assert w.header_text() == "NEW-AI"
    w._on_state("done")
    assert w.is_busy() is False


def test_switch_baud_same_keeps_link(qtbot, tmp_path, monkeypatch):
    """决策点 2：切到 baud 一致产品 → 链路保持 + 自动重启监控。"""
    from lbs_firmware_studio.gui.pages.monitor_page import MonitorPage
    started, stopped = [], []
    monkeypatch.setattr(MonitorPage, "start_monitor", lambda self: started.append(True))
    monkeypatch.setattr(MonitorPage, "stop_monitor", lambda self: stopped.append(True))
    w = MainWindow(_profile(baud=115200), _raw(), tmp_path / "products.yaml",
                   profiles=_two_profiles(115200, 115200))
    qtbot.addWidget(w)
    w._conn._transport = object()          # 模拟已连接（活链路）
    transport = w._conn.persistent_transport()
    assert transport is not None
    w._product_selector.select_product("SPARK-AI")
    assert w.header_text() == "SPARK-AI"
    assert w._conn.persistent_transport() is transport   # 链路保持（同一对象，未被断开）
    assert w._conn.is_connected() is True
    assert stopped == [True]               # 旧监控已停止
    assert started == [True]               # 新监控已自动启动


def test_switch_baud_diff_disconnects_and_warns(qtbot, tmp_path, monkeypatch):
    """决策点 2：切到 baud 不一致产品 → 断开链路 + 提示重新连接。"""
    from PySide6.QtWidgets import QMessageBox
    w = MainWindow(_profile(baud=115200), _raw(), tmp_path / "products.yaml",
                   profiles=_two_profiles(115200, 9600))
    qtbot.addWidget(w)
    w._conn._transport = object()          # 模拟已连接
    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warned.append(a))
    w._product_selector.select_product("SPARK-AI")
    assert w.header_text() == "SPARK-AI"
    assert w._conn.is_connected() is False   # 已断开
    assert warned                            # 弹了「产品波特率变化」提示框


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


def test_product_selector_min_width_after_show(qtbot, tmp_path):
    """BUG1 回归：浮窗内 ProductSelector 不能被布局压成 0 宽，popup show 后 width>=168。"""
    from PySide6.QtWidgets import QApplication
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml")
    qtbot.addWidget(w)
    w._popup.show()
    QApplication.processEvents()
    assert w._product_selector.width() >= 168


# ---- 布局重构 v2：顶栏主机信息 + 设备/传感器浮窗入口 ----
def test_topbar_shows_host_status_bar(qtbot, tmp_path):
    """顶栏只放主机信息：host_bar() 访问器返回 HostStatusBar，字段随产品初始化。"""
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    bar = w.host_bar()
    assert bar is not None
    assert bar.field_text("版本") == "--"        # 字段已按 NEW-AI status_fields 挂载，初始未连接为占位
    assert bar.field_text("运行状态") == "--"


def test_host_status_bar_updates_from_monitor_frame(qtbot, tmp_path):
    """监控页帧渲染转发到顶栏 HostStatusBar（主机信息数据流）。"""
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    frame = {"deviceList": [], "version": 317,
             "mem": {"yaw": "60.31", "pitch": "179.39", "roll": "-0.34"}}
    w._monitor.frame_rendered.emit(frame)
    assert w.host_bar().field_text("版本") == "317"
    assert w.host_bar().field_text("IMU") == "60.31/179.39/-0.34"


def test_device_icon_opens_popup(qtbot, tmp_path):
    """点 ActivityBar 的 device 图标弹出设备连接浮窗（Qt.Popup 顶层窗口）。"""
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    assert w.popup_visible() is False
    w._activity._buttons["device"].click()
    assert w.popup_visible() is True


def test_sensor_icon_opens_dialog(qtbot, tmp_path, monkeypatch):
    """点 ActivityBar 的 sensor 图标弹出传感器更新对话框（复用监控页对话框）。"""
    opened = []
    monkeypatch.setattr(
        "lbs_firmware_studio.gui.dialogs.sensor_update_dialog.SensorUpdateDialog.exec",
        lambda self: opened.append(True))
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w._activity._buttons["sensor"].click()
    assert opened == [True]
