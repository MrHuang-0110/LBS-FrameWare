"""串口选择：下拉 + 刷新，自动识别 LBS Serial 设备置顶默认选中。
枚举串口在后台 QThread 执行，避免 com ports() 阻塞主线程（Windows 上某些坏端口
可卡 40 秒+，导致窗口无响应被系统杀掉）。"""
from __future__ import annotations
import sys
from typing import Callable
from PySide6.QtCore import QObject, QThread, Signal, Slot
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


class _PortScanWorker(QObject):
    """把阻塞的 com ports() 丢到后台线程跑，扫完 emit ports 回主线程。"""
    done = Signal(object)   # payload: list[comport]
    failed = Signal(str)

    def __init__(self, lister: Callable, parent=None):
        super().__init__(parent)
        self._lister = lister

    @Slot()
    def run(self) -> None:
        try:
            self.done.emit(list(self._lister()))
        except Exception as e:
            self.failed.emit(str(e))


class PortSelector(QWidget):
    def __init__(self, lister: "Callable[[], list] | None" = None, parent=None):
        super().__init__(parent)
        self._lister = lister or _default_lister
        self._scan_thread = None
        self._scan_worker = None
        self._combo = QComboBox()
        self._refresh_btn = QPushButton("刷新")
        self._refresh_btn.clicked.connect(self.refresh)
        self._scan_started = False
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._combo, 1); lay.addWidget(self._refresh_btn)

    def showEvent(self, event) -> None:
        """首次显示时触发异步扫描，避免构造期 QThread 竞态。"""
        super().showEvent(event)
        if not self._scan_started:
            self._scan_started = True
            self._scan()

    # ---- 异步扫描 ----
    def _scan(self) -> None:
        """后台线程跑 com ports()，期间下拉显示"扫描中..."；扫完在主线程填充。"""
        if self._scan_thread is not None and self._scan_thread.isRunning():
            return
        # PortSelector 可能被快速创建/销毁（如 MonitorPage 测试），QTimer 回调时
        # widget 可能已被父控件销毁，需检查 C++ 对象存活再操作。
        try:
            _ = self._combo.count()
        except RuntimeError:
            return  # C++ 对象已删除，放弃扫描
        self._combo.clear()
        self._combo.addItem("扫描中...", None)
        self._refresh_btn.setEnabled(False)
        self._scan_thread = QThread()
        self._scan_worker = _PortScanWorker(self._lister)
        self._scan_worker.moveToThread(self._scan_thread)
        self._scan_thread.started.connect(self._scan_worker.run)
        self._scan_worker.done.connect(self._on_scan_done)
        self._scan_worker.failed.connect(self._on_scan_failed)
        self._scan_worker.done.connect(self._scan_thread.quit)
        self._scan_worker.failed.connect(self._scan_thread.quit)
        self._scan_thread.start()

    @Slot(object)
    def _on_scan_done(self, ports) -> None:
        try:
            _ = self._combo.count()
        except RuntimeError:
            return  # C++ 对象已删除
        self._populate(ports)
        self._refresh_btn.setEnabled(True)

    @Slot(str)
    def _on_scan_failed(self, _msg: str) -> None:
        try:
            _ = self._combo.count()
        except RuntimeError:
            return  # C++ 对象已删除
        self._combo.clear()
        self._combo.addItem("(串口不可用)", None)
        self._refresh_btn.setEnabled(True)

    # ---- 同步刷新（供外部测试注入，不走 QThread） ----
    def refresh(self) -> None:
        """用户点"刷新"：后台异步扫描。"""
        self._scan()

    def _populate(self, ports) -> None:
        """把端口列表填进下拉（必须在主线程调用）。"""
        self._combo.clear()
        ports.sort(key=lambda p: 0 if _is_lbs(p) else 1)
        lbs_index = -1
        for i, p in enumerate(ports):
            label = getattr(p, "description", None) or p.device
            self._combo.addItem(label, p.device)
            if lbs_index < 0 and _is_lbs(p):
                lbs_index = i
        if lbs_index >= 0:
            self._combo.setCurrentIndex(lbs_index)

    # ---- 同步注入（测试用：绕过异步扫描，直接填数据） ----
    def inject_ports(self, ports) -> None:
        """测试直接注入端口列表，跳过异步扫描。"""
        self._populate(ports)

    def selected_port(self) -> "str | None":
        if self._combo.count() == 0:
            return None
        data = self._combo.currentData()
        return data if isinstance(data, str) else None