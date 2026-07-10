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
