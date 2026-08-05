from lbs_firmware_studio.gui.main_window import MainWindow
from lbs_firmware_studio.backend.profile import DeviceProfile
from pathlib import Path


def _profile(**kw):
    return DeviceProfile(name="NEW-AI", protocol="custom_frame", display_ports=8,
                         folders=["app", "version"], firmware_dir=Path("./x"), **kw)


def _two_profiles(baud_new=115200, baud_spark=115200):
    """两个产品（NEW-AI 当前 + SPARK-AI 可切换），可分别指定 baud（决策点 2 测试）。
    SPARK-AI 用独立 firmware_dir，供产品切换后浮窗固件目录 getter 刷新断言。"""
    return {
        "NEW-AI": _profile(baud=baud_new),
        "SPARK-AI": DeviceProfile(name="SPARK-AI", protocol="custom_frame",
                                  display_ports=4, folders=["app"],
                                  firmware_dir=Path("./x-spark"), baud=baud_spark),
    }


def _raw():
    return {"compiler_path": "./t.exe", "products": {"NEW-AI": {"protocol": "custom_frame"}}}


def test_shows_product_name(qtbot, tmp_path):
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    assert "NEW-AI" in w.header_text()


def test_nav_items_present_and_locked(qtbot, tmp_path):
    """布局重构 v3：ActivityBar 精简为 设备连接(浮窗)/代码编辑(页面) + 左下角设置键。
    nav_labels() == [设备连接, 代码编辑]（设置是底部键，不进 nav 语义）。"""
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    assert w.nav_labels() == ["设备连接", "代码编辑"]
    assert "设置" not in w.nav_labels()
    assert "固件与监控" not in w.nav_labels()   # 固件与监控页已移除
    assert "传感器更新" not in w.nav_labels()   # 传感器更新入口移到设备浮窗
    assert w.is_nav_enabled("设备连接") is True
    assert w.is_nav_enabled("代码编辑") is True


def test_nav_switches_page(qtbot, tmp_path):
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w.navigate("代码编辑")
    assert w.current_page_name() == "代码编辑"


def test_product_switch_rebuilds_pages(qtbot, tmp_path):
    """切换产品 → header 更新 + 页面栈重建（Editor 新实例）与右侧监控栏重建。
    _firmware 为浮窗内固件更新区（单例，随产品切换刷新目录 getter，不重建）。"""
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml", profiles=_two_profiles())
    qtbot.addWidget(w)
    assert w.header_text() == "NEW-AI"
    assert "NEW-AI" in w.windowTitle()
    old = (w._monitor, w._editor_page)
    w._product_selector.select_product("SPARK-AI")
    assert w.header_text() == "SPARK-AI"              # selector 当前产品
    assert "SPARK-AI" in w.windowTitle()              # 窗口标题随产品切换（v3 用户反馈 bug）
    assert w.current_page_name() == "代码编辑"         # 默认停留在唯一页面
    assert w._monitor is not old[0]                   # 右侧监控栏重建（新实例）
    assert w._editor_page is not old[1]               # 编辑页重建（新实例）
    # 浮窗固件目录 getter 已随新产品刷新
    assert "x-spark" in w._firmware.firmware_dir_text().replace("\\", "/")


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


def test_deploy_log_shown_in_status_bar(qtbot, tmp_path, monkeypatch):
    """deployer 日志 → 状态栏单行文本（全部显示含 [DEBUG]，用户要求可见调试数据）；
    error/finished 清空。"""
    monkeypatch.setattr("lbs_firmware_studio.gui.main_window.QMessageBox.critical",
                        lambda *a, **k: None)  # 模态错误框在测试中阻塞，monkeypatch 掉
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml", profiles=_two_profiles())
    qtbot.addWidget(w)
    assert w._status.deploy_text() == ""
    w._on_deploy_log("[DEBUG] _send_packet_wait: 1024B sent, waiting for ACK")
    assert w._status.deploy_text() == "[DEBUG] _send_packet_wait: 1024B sent, waiting for ACK"
    w._on_deploy_log("[DEBUG] _wait_control: timeout waiting for 0x43")
    assert w._status.deploy_text().endswith("timeout waiting for 0x43")
    w._on_deploy_log("发送 NEXT-AI.bin")
    assert w._status.deploy_text() == "发送 NEXT-AI.bin"
    w._on_finished()
    assert w._status.deploy_text() == ""            # 结束后清空
    w._on_deploy_log("发送 NEXT-AI.bin")
    w._on_error("连接失败")
    assert w._status.deploy_text() == ""            # 出错后清空


def test_switch_baud_same_keeps_link(qtbot, tmp_path, monkeypatch):
    """决策点 2：切到 baud 一致产品 → 链路保持 + 自动重启监控。"""
    from lbs_firmware_studio.gui.widgets.monitor_panel import MonitorPanel
    started, stopped = [], []
    monkeypatch.setattr(MonitorPanel, "start_monitor", lambda self: started.append(True))
    monkeypatch.setattr(MonitorPanel, "stop_monitor", lambda self: stopped.append(True))
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
    assert "设备连接" in w.nav_labels()
    assert w.is_nav_enabled("设备连接") is True


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


# ---- 布局重构 v2：顶栏主机信息 + 设备浮窗入口 ----
def test_topbar_shows_host_status_bar(qtbot, tmp_path):
    """顶栏只放主机信息：host_bar() 访问器返回 HostStatusBar，字段随产品初始化。"""
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    bar = w.host_bar()
    assert bar is not None
    assert bar.field_text("版本") == "--"        # 字段已按 NEW-AI status_fields 挂载，初始未连接为占位
    assert bar.field_text("运行状态") == "--"


def test_host_status_bar_updates_from_monitor_frame(qtbot, tmp_path):
    """监控数据经 monitor_panel 更新：帧渲染转发到顶栏 HostStatusBar（主机信息数据流）。"""
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


# ---- 布局重构 v3：主内容区右侧监控栏 / 浮窗固件 / 左下角设置 ----
def test_main_content_has_right_monitor_panel(qtbot, tmp_path):
    """主内容区含右侧监控栏：monitor_panel() 访问器返回 MonitorPanel，固定宽 280px。"""
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    panel = w.monitor_panel()
    assert panel is not None
    assert panel.minimumWidth() == 280
    assert panel.maximumWidth() == 280
    assert panel.card_count() == 8      # NEW-AI 卡片已按 profile 挂载


def test_popup_has_firmware_section(qtbot, tmp_path):
    """设备浮窗含固件更新区（FirmwareUpdateSection），_firmware 即该区。"""
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    fw = w._popup.firmware_section()
    assert fw is w._firmware
    assert fw.start_button().text() == "开始固件更新"


def test_settings_button_bottom_key(qtbot, tmp_path, monkeypatch):
    """左下角设置按钮：settings_button() 访问器返回底部设置键，点击经 action_triggered 弹设置。"""
    from lbs_firmware_studio.gui.main_window import MainWindow
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    btn = w.settings_button()
    assert btn is not None
    assert w._activity._settings_key == "settings"
    assert w._activity.nav_keys() == ["device", "editor"]   # settings 不进 nav 语义
    # 真实 _on_settings_action 会 exec() 模态对话框，测试中打桩验证「设置按钮 → 弹设置」接线
    opened = []
    monkeypatch.setattr(MainWindow, "_on_settings_action", lambda self: opened.append(True))
    actions = []
    w._activity.action_triggered.connect(actions.append)
    btn.click()
    assert opened == [True]          # 点击设置按钮触发了 _on_settings_action
    assert actions == ["settings"]   # 且发的是 action_triggered（不切页）


def test_firmware_start_from_popup_wired(qtbot, tmp_path, monkeypatch):
    """固件更新从浮窗发起：start_firmware_requested → _start_firmware；**浮窗保持打开**
    （用户要求：开始后不缩回，进度条/日志在浮窗内可见）。"""
    from PySide6.QtWidgets import QMessageBox
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    called = []
    w._start_firmware = lambda: called.append(True)
    w._popup.show()
    w._popup.start_firmware_requested.emit()
    assert called == [True]
    assert w.popup_visible() is True      # 开始后浮窗不收起（用户要求）


def test_sensor_update_from_popup_opens_dialog(qtbot, tmp_path, monkeypatch):
    """点浮窗传感器更新按钮 → sensor_update_requested → MainWindow 弹 SensorUpdateDialog。"""
    opened = []
    monkeypatch.setattr(
        "lbs_firmware_studio.gui.dialogs.sensor_update_dialog.SensorUpdateDialog.exec",
        lambda self: opened.append(True))
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w._monitor._monitoring = True   # 模拟监控中（守卫通过才弹对话框）
    w._popup._sensor_btn.click()
    assert opened == [True]


def test_sensor_update_blocked_when_not_monitoring(qtbot, tmp_path, monkeypatch):
    """守卫：未监控（未连接）时点传感器按钮不弹对话框，改为提示先连接并开始监控。"""
    from PySide6.QtWidgets import QMessageBox
    opened, informed = [], []
    monkeypatch.setattr(
        "lbs_firmware_studio.gui.dialogs.sensor_update_dialog.SensorUpdateDialog.exec",
        lambda self: opened.append(True))
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: informed.append(a))
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w._popup._sensor_btn.click()   # 未监控
    assert opened == []                        # 不弹对话框
    assert informed                            # 提示「请先连接并开始监控」
    assert any("连接" in str(x) for x in informed)


def test_sensor_update_blocked_when_product_unsupported(qtbot, tmp_path, monkeypatch):
    """守卫：产品不支持 sensor_update（SPARK-AI）时提示不支持，不弹对话框。"""
    from PySide6.QtWidgets import QMessageBox
    opened, informed = [], []
    monkeypatch.setattr(
        "lbs_firmware_studio.gui.dialogs.sensor_update_dialog.SensorUpdateDialog.exec",
        lambda self: opened.append(True))
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: informed.append(a))
    spark = DeviceProfile(name="SPARK-AI", protocol="custom_frame", display_ports=4,
                          folders=["app"], firmware_dir=Path("./x"))
    w = MainWindow(spark, _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    w._monitor._monitoring = True   # 监控中，但产品不支持
    w._popup._sensor_btn.click()
    assert opened == []
    assert any("不支持" in str(x) for x in informed)


def test_disconnect_clears_host_bar(qtbot, tmp_path):
    """断开连接时顶栏 HostStatusBar 清空为占位 '--'（不残留最后帧值）。"""
    w = MainWindow(_profile(), _raw(), tmp_path / "products.yaml"); qtbot.addWidget(w)
    frame = {"deviceList": [], "version": 317,
             "mem": {"yaw": "60.31", "pitch": "179.39", "roll": "-0.34"}}
    w._monitor.frame_rendered.emit(frame)
    assert w.host_bar().field_text("版本") == "317"     # 先有值
    w._on_connection_changed(False)                       # 断开
    assert w.host_bar().field_text("版本") == "--"        # 清空为占位
    assert w.host_bar().field_text("IMU") == "--"
