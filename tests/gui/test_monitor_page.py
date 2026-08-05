"""右侧监控栏 MonitorPanel 测试（布局重构 v3：从 monitor_page 提取的传感器卡片网格 + 连接提示条）。
数据流与 monitor_page 一致：host_state_changed / frame_rendered / 卡片渲染 / 提示条两态。"""
from PySide6.QtCore import Signal

from lbs_firmware_studio.gui.widgets.monitor_panel import MonitorPanel
from lbs_firmware_studio.backend.profile import DeviceProfile


def _profile(name):
    return DeviceProfile(name=name, protocol="custom_frame")


NEW_AI_FRAME = {
    "deviceList": [
        {"port": 0, "color": {"r": 1, "g": 2, "b": 3, "lux": 1615}},
        {"port": 1}, {"port": 2, "ultrasion": {"cm": "255"}},
        {"port": 3}, {"port": 4}, {"port": 5}, {"port": 6}, {"port": 7},
    ],
    "version": 317, "bat": "100.00",
    "mem": {"yaw": "60.31", "pitch": "179.39", "roll": "-0.34"},
    "voic": "0.07", "heap": "236624", "MAC": "EC230905AA48",
    "NewAiState": "stop",
}


def test_new_ai_has_8_cards_and_update_action(qtbot):
    """NEW-AI 支持传感器更新（入口在设备浮窗，本组件仅报告能力）。"""
    p = MonitorPanel(); qtbot.addWidget(p)
    p.set_profile(_profile("NEW-AI"))
    assert p.card_count() == 8
    assert p.has_sensor_update_action() is True


def test_spark_ai_has_4_cards_no_update_action(qtbot):
    """SPARK-AI 不支持传感器更新，能力标记为 False。"""
    p = MonitorPanel(); qtbot.addWidget(p)
    p.set_profile(_profile("SPARK-AI"))
    assert p.card_count() == 4
    assert p.has_sensor_update_action() is False


def test_next_ai_has_2_cards(qtbot):
    p = MonitorPanel(); qtbot.addWidget(p)
    p.set_profile(_profile("NEXT-AI"))
    assert p.card_count() == 2


def test_render_updates_cards_and_status(qtbot):
    p = MonitorPanel(); qtbot.addWidget(p)
    p.set_profile(_profile("NEW-AI"))
    p._on_frame(NEW_AI_FRAME)
    p._render()                        # 直接触发渲染（绕过节流 timer）
    assert p.card_at(0).title_text() == "端口 0 · 颜色"
    assert ("cm", "255") in p.card_at(2).rows()
    assert p.card_at(1).rows() == []   # 空端口占位
    # 主机信息（版本/IMU）在顶栏 HostStatusBar，帧转发链路由
    # tests/gui/test_main_window.py::test_host_status_bar_updates_from_monitor_frame 覆盖。


def test_on_frame_only_caches_latest(qtbot):
    p = MonitorPanel(); qtbot.addWidget(p)
    p.set_profile(_profile("NEW-AI"))
    p._on_frame({"deviceList": [], "version": 1})
    p._on_frame({"deviceList": [], "version": 2})   # 覆盖
    assert p.latest_frame()["version"] == 2         # 只保留最新
    p._render()                                     # 渲染不崩溃；主机信息由顶栏承接


def test_unknown_product_shows_message_no_crash(qtbot):
    p = MonitorPanel(); qtbot.addWidget(p)
    p.set_profile(_profile("MYSTERY"))
    assert p.card_count() == 0        # 无卡片，不崩溃


def test_host_state_changed_emits_on_start(qtbot):
    """监控帧中运行状态为 start 时 emit host_state_changed("start")"""
    p = MonitorPanel(); qtbot.addWidget(p)
    p.set_profile(_profile("NEW-AI"))
    states = []
    p.host_state_changed.connect(lambda s: states.append(s))
    frame = dict(NEW_AI_FRAME)
    frame["NewAiState"] = "start"
    p._on_frame(frame)
    p._render()
    assert states == ["start"]


def test_host_state_changed_emits_on_stop(qtbot):
    """监控帧中运行状态为 stop 时 emit host_state_changed("stop")"""
    p = MonitorPanel(); qtbot.addWidget(p)
    p.set_profile(_profile("NEW-AI"))
    # 先发一次 start 建立初始状态
    frame_start = dict(NEW_AI_FRAME)
    frame_start["NewAiState"] = "start"
    p._on_frame(frame_start)
    p._render()
    states = []
    p.host_state_changed.connect(lambda s: states.append(s))
    frame_stop = dict(NEW_AI_FRAME)
    frame_stop["NewAiState"] = "stop"
    p._on_frame(frame_stop)
    p._render()
    assert states == ["stop"]


def test_host_state_changed_not_emitted_on_same_state(qtbot):
    """状态与上次相同时不重复 emit"""
    p = MonitorPanel(); qtbot.addWidget(p)
    p.set_profile(_profile("NEW-AI"))
    frame = dict(NEW_AI_FRAME)
    frame["NewAiState"] = "stop"
    p._on_frame(frame)
    p._render()
    states = []
    p.host_state_changed.connect(lambda s: states.append(s))
    # 再发一次相同状态
    p._on_frame(frame)
    p._render()
    assert states == []  # 未变化，不 emit


def test_host_state_changed_emits_empty_on_stop_monitor(qtbot):
    """监控停止时 emit host_state_changed("")"""
    p = MonitorPanel(); qtbot.addWidget(p)
    p.set_profile(_profile("NEW-AI"))
    frame = dict(NEW_AI_FRAME)
    frame["NewAiState"] = "start"
    p._on_frame(frame)
    p._render()
    states = []
    p.host_state_changed.connect(lambda s: states.append(s))
    p.stop_monitor()
    assert states == [""]


def test_host_state_changed_unknown_product_no_emit(qtbot):
    """未知产品不 emit host_state_changed"""
    p = MonitorPanel(); qtbot.addWidget(p)
    p.set_profile(_profile("MYSTERY"))
    states = []
    p.host_state_changed.connect(lambda s: states.append(s))
    p._on_frame({"version": 1})
    p._render()
    assert states == []


def test_host_state_changed_spark_ai_uses_will_ai_state(qtbot):
    """SPARK-AI 用 WillAiState 路径提取运行状态。"""
    p = MonitorPanel(); qtbot.addWidget(p)
    p.set_profile(_profile("SPARK-AI"))
    states = []
    p.host_state_changed.connect(lambda s: states.append(s))
    p._on_frame({"WillAiState": "start"})
    p._render()
    assert states == ["start"]


def test_host_state_changed_next_ai_uses_state(qtbot):
    """NEXT-AI 用 State 路径提取运行状态。"""
    p = MonitorPanel(); qtbot.addWidget(p)
    p.set_profile(_profile("NEXT-AI"))
    states = []
    p.host_state_changed.connect(lambda s: states.append(s))
    p._on_frame({"State": "stop"})
    p._render()
    assert states == ["stop"]


# --- 连接提示条（v3：连接入口在设备浮窗；设计 §4.5 两态）---
def test_connection_hint_shown(qtbot):
    """初始（未连接）显示 WARNING 提示条「请先在设备浮窗连接设备」。"""
    p = MonitorPanel(); qtbot.addWidget(p)
    assert p.has_connection_hint() is True
    assert "请先在设备浮窗连接设备" in p.connection_hint_text()


def test_connection_hint_stays_after_set_transport_getter(qtbot):
    """注入非 None 持久链路后提示条保持可见并切为已连接文案。"""
    p = MonitorPanel(); qtbot.addWidget(p)
    p.set_transport_getter(lambda: object())
    assert p.has_connection_hint() is True
    assert "已连接设备" in p.connection_hint_text()


def test_connection_hint_switches_with_state(qtbot):
    """提示条随链路可用性两态切换（连接→SUCCESS / 断开→WARNING）。"""
    p = MonitorPanel(); qtbot.addWidget(p)
    assert "请先在设备浮窗连接设备" in p.connection_hint_text()
    p.set_transport_getter(lambda: object())   # 连接建立
    assert "已连接设备" in p.connection_hint_text()
    p.set_transport_getter(lambda: None)       # 断开
    assert "请先在设备浮窗连接设备" in p.connection_hint_text()
