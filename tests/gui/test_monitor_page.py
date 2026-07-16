from PySide6.QtCore import Signal

from lbs_firmware_studio.gui.pages.monitor_page import MonitorPage
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


def test_new_ai_has_8_cards_and_update_button(qtbot):
    p = MonitorPage(); qtbot.addWidget(p)
    p.set_profile(_profile("NEW-AI"))
    assert p.card_count() == 8
    assert p.has_sensor_update_button() is True


def test_spark_ai_has_4_cards_no_update_button(qtbot):
    p = MonitorPage(); qtbot.addWidget(p)
    p.set_profile(_profile("SPARK-AI"))
    assert p.card_count() == 4
    assert p.has_sensor_update_button() is False


def test_next_ai_has_2_cards(qtbot):
    p = MonitorPage(); qtbot.addWidget(p)
    p.set_profile(_profile("NEXT-AI"))
    assert p.card_count() == 2


def test_render_updates_cards_and_status(qtbot):
    p = MonitorPage(); qtbot.addWidget(p)
    p.set_profile(_profile("NEW-AI"))
    p._on_frame(NEW_AI_FRAME)
    p._render()                        # 直接触发渲染（绕过节流 timer）
    assert p.card_at(0).title_text() == "端口 0 · 颜色"
    assert ("cm", "255") in p.card_at(2).rows()
    assert p.card_at(1).rows() == []   # 空端口占位
    assert p._status.field_text("版本") == "317"
    assert p._status.field_text("IMU") == "60.31/179.39/-0.34"


def test_on_frame_only_caches_latest(qtbot):
    p = MonitorPage(); qtbot.addWidget(p)
    p.set_profile(_profile("NEW-AI"))
    p._on_frame({"deviceList": [], "version": 1})
    p._on_frame({"deviceList": [], "version": 2})   # 覆盖
    assert p.latest_frame()["version"] == 2         # 只保留最新
    p._render()
    assert p._status.field_text("版本") == "2"


def test_unknown_product_shows_message_no_crash(qtbot):
    p = MonitorPage(); qtbot.addWidget(p)
    p.set_profile(_profile("MYSTERY"))
    assert p.card_count() == 0        # 无卡片，不崩溃


def test_host_state_changed_emits_on_start(qtbot):
    """监控帧中运行状态为 start 时 emit host_state_changed("start")"""
    p = MonitorPage(); qtbot.addWidget(p)
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
    p = MonitorPage(); qtbot.addWidget(p)
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
    p = MonitorPage(); qtbot.addWidget(p)
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
    p = MonitorPage(); qtbot.addWidget(p)
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
    p = MonitorPage(); qtbot.addWidget(p)
    p.set_profile(_profile("MYSTERY"))
    states = []
    p.host_state_changed.connect(lambda s: states.append(s))
    p._on_frame({"version": 1})
    p._render()
    assert states == []


def test_host_state_changed_spark_ai_uses_will_ai_state(qtbot):
    """SPARK-AI 用 WillAiState 路径提取运行状态。"""
    p = MonitorPage(); qtbot.addWidget(p)
    p.set_profile(_profile("SPARK-AI"))
    states = []
    p.host_state_changed.connect(lambda s: states.append(s))
    p._on_frame({"WillAiState": "start"})
    p._render()
    assert states == ["start"]


def test_host_state_changed_next_ai_uses_state(qtbot):
    """NEXT-AI 用 State 路径提取运行状态。"""
    p = MonitorPage(); qtbot.addWidget(p)
    p.set_profile(_profile("NEXT-AI"))
    states = []
    p.host_state_changed.connect(lambda s: states.append(s))
    p._on_frame({"State": "stop"})
    p._render()
    assert states == ["stop"]
