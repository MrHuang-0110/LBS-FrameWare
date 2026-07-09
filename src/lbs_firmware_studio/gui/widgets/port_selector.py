"""串口选择：下拉 + 刷新，自动识别 LBS Serial 设备置顶默认选中。"""
from __future__ import annotations
from typing import Callable
from PySide6.QtWidgets import QWidget, QHBoxLayout, QComboBox, QPushButton

_LBS_VID_PID = (0x0483, 0x5740)


def _default_lister():
    import serial.tools.list_ports
    return list(serial.tools.list_ports.comports())


def _is_lbs(p) -> bool:
    desc = (getattr(p, "description", "") or "")
    if "LBS Serial" in desc:
        return True
    vid = getattr(p, "vid", None); pid = getattr(p, "pid", None)
    return (vid, pid) == _LBS_VID_PID


class PortSelector(QWidget):
    def __init__(self, lister: "Callable[[], list] | None" = None, parent=None):
        super().__init__(parent)
        self._lister = lister or _default_lister
        self._combo = QComboBox()
        self._refresh_btn = QPushButton("刷新")
        self._refresh_btn.clicked.connect(self.refresh)
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._combo, 1); lay.addWidget(self._refresh_btn)
        self.refresh()

    def refresh(self) -> None:
        ports = list(self._lister())
        # LBS 设备排前
        ports.sort(key=lambda p: 0 if _is_lbs(p) else 1)
        self._combo.clear()
        lbs_index = -1
        for i, p in enumerate(ports):
            label = getattr(p, "description", None) or p.device
            self._combo.addItem(label, p.device)
            if lbs_index < 0 and _is_lbs(p):
                lbs_index = i
        if lbs_index >= 0:
            self._combo.setCurrentIndex(lbs_index)

    def selected_port(self) -> "str | None":
        if self._combo.count() == 0:
            return None
        return self._combo.currentData()
