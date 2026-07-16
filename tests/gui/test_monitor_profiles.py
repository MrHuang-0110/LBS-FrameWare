from lbs_firmware_studio.gui.pages.monitor_profiles import (
    MONITOR_PROFILES, SENSOR_NAMES, get_by_path, sensor_display_name,
    get_host_state_path,
)


def test_profiles_ports():
    assert MONITOR_PROFILES["NEW-AI"]["ports"] == 8
    assert MONITOR_PROFILES["SPARK-AI"]["ports"] == 4
    assert MONITOR_PROFILES["NEXT-AI"]["ports"] == 2


def test_sensor_update_only_new_ai():
    assert MONITOR_PROFILES["NEW-AI"]["sensor_update"] is True
    assert MONITOR_PROFILES["SPARK-AI"]["sensor_update"] is False
    assert MONITOR_PROFILES["NEXT-AI"]["sensor_update"] is False


def test_status_fields_have_label_and_path():
    for prof in MONITOR_PROFILES.values():
        for item in prof["status_fields"]:
            assert isinstance(item, tuple) and len(item) == 2


def test_get_by_path_flat():
    assert get_by_path({"version": 317}, "version") == 317


def test_get_by_path_nested():
    assert get_by_path({"adc": {"bat": "82%"}}, "adc.bat") == "82%"


def test_get_by_path_missing_returns_none():
    assert get_by_path({"adc": {}}, "adc.bat") is None
    assert get_by_path({}, "x.y.z") is None


def test_sensor_display_name_known_and_unknown():
    assert sensor_display_name("big_motor") == "大电机"
    assert sensor_display_name("color") == "颜色"
    assert sensor_display_name("gray_v2") == "灰度V2"
    assert sensor_display_name("weird_key") == "weird_key"   # 未知原样返回


def test_get_host_state_path_new_ai():
    assert get_host_state_path("NEW-AI") == "NewAiState"


def test_get_host_state_path_spark_ai():
    assert get_host_state_path("SPARK-AI") == "WillAiState"


def test_get_host_state_path_next_ai():
    assert get_host_state_path("NEXT-AI") == "State"


def test_get_host_state_path_unknown_product():
    assert get_host_state_path("UNKNOWN") is None


def test_get_host_state_path_none():
    assert get_host_state_path(None) is None
