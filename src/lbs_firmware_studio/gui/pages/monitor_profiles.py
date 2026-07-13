"""数据监控的产品参数化：卡片数 / 底部状态字段 / 是否显示传感器更新，
以及传感器 JSON key -> 中文名映射。纯数据 + 取值辅助，无 Qt 依赖。"""
from __future__ import annotations

MONITOR_PROFILES: dict[str, dict] = {
    "NEW-AI": {
        "ports": 8,
        "status_fields": [
            ("主机", "MAC"), ("版本", "version"), ("电量", "bat"),
            ("运行状态", "NewAiState"), ("IMU", "mem"),
            ("音量", "voic"), ("Heap", "heap"),
        ],
        "sensor_update": True,
    },
    "SPARK-AI": {
        "ports": 4,
        "status_fields": [
            ("版本", "version"), ("电量", "adc.bat"),
            ("运行状态", "WillAiState"), ("Heap", "heap"),
        ],
        "sensor_update": False,
    },
    "NEXT-AI": {
        "ports": 2,
        "status_fields": [
            ("蓝牙名", "btName"), ("版本", "version"), ("电量", "adc.bat"),
            ("IR", "adc.ir"), ("运行状态", "State"), ("Heap", "heap"),
        ],
        "sensor_update": False,
    },
}

SENSOR_NAMES: dict[str, str] = {
    "big_motor": "大电机", "small_motor": "中电机",
    "color": "颜色", "ultrasion": "超声波", "touch": "触摸",
    "camer": "摄像头", "gray": "灰度", "gray_v2": "灰度V2", "nfc": "NFC",
    "dev null": "无设备",
}


def get_by_path(data: dict, path: str):
    """点路径取嵌套值，如 'adc.bat'；任一层缺失返回 None。"""
    cur = data
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def sensor_display_name(key: str) -> str:
    return SENSOR_NAMES.get(key, key)
