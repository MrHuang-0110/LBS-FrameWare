"""NEW-AI 传感器更新对话框：8 端口各选目标设备类型 -> 组帧 -> frame_ready(bytes)。
即发即忘，不等 ACK；效果在后续监控帧体现。仅监控中可打开（页面侧控制）。"""
from __future__ import annotations
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QLabel, QComboBox, QPushButton)
from PySide6.QtCore import Signal
from ...backend.sensor_update import SENSOR_UPDATE_OPTIONS, build_sensor_update_frame
from .. import theme


class SensorUpdateDialog(QDialog):
    frame_ready = Signal(object)   # payload: bytes 完整帧

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("传感器更新")
        self._combos: list[QComboBox] = []

        grid = QGridLayout()
        grid.setHorizontalSpacing(theme.SPACE_MD)
        grid.setVerticalSpacing(theme.SPACE_XS)
        for port in range(8):
            grid.addWidget(QLabel(f"端口 {port}"), port, 0)
            combo = QComboBox()
            for name, id_value in SENSOR_UPDATE_OPTIONS:
                combo.addItem(name, id_value)
            grid.addWidget(combo, port, 1)
            self._combos.append(combo)

        self._status = QLabel("")
        self._submit_btn = QPushButton("下发"); self._submit_btn.setObjectName("primary")
        self._submit_btn.clicked.connect(self._submit)
        btn_row = QHBoxLayout(); btn_row.setSpacing(theme.SPACE_MD)
        self._status.setStyleSheet(f"color:{theme.SUCCESS}; background:transparent;")
        btn_row.addWidget(self._status, 1); btn_row.addWidget(self._submit_btn)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(theme.SPACE_LG, theme.SPACE_LG, theme.SPACE_LG, theme.SPACE_LG)
        lay.setSpacing(theme.SPACE_MD)
        lay.addLayout(grid)
        lay.addLayout(btn_row)

    def selected_ids(self) -> list[int]:
        return [c.currentData() for c in self._combos]

    def set_port_selection(self, port: int, id_value: int) -> None:
        combo = self._combos[port]
        idx = combo.findData(id_value)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _submit(self) -> None:
        frame = build_sensor_update_frame(self.selected_ids())
        self.frame_ready.emit(frame)
        self._status.setText("已下发")
