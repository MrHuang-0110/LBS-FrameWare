"""FirmwareUpdateSection 固件更新区组件测试（qtbot）。

覆盖：固件源目录（set_profile / set_firmware_dir_getter）、开始按钮二次确认、
进度条与单行进度文本（on_progress/on_log/on_state）、set_busy 禁用开始按钮。
"""
from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from lbs_firmware_studio.backend.profile import DeviceProfile
from lbs_firmware_studio.gui import theme
from lbs_firmware_studio.gui.widgets.firmware_update_section import FirmwareUpdateSection


def _profile():
    return DeviceProfile(name="NEW-AI", protocol="custom_frame",
                         folders=["app", "music", "boot", "config", "version"],
                         firmware_dir=Path("./products/NEW-AI/fwlib"))


def test_set_profile_shows_folders_and_dir(qtbot):
    w = FirmwareUpdateSection(); qtbot.addWidget(w)
    w.set_profile(_profile())
    txt = w.summary_text()
    assert "app" in txt and "music" in txt
    assert "NEW-AI/fwlib" in w.firmware_dir_text().replace("\\", "/")


def test_set_firmware_dir_getter_updates_dir(qtbot):
    """固件源目录 getter：目录文本刷新为 getter 返回值（浮窗场景无 profile）。"""
    w = FirmwareUpdateSection(); qtbot.addWidget(w)
    w.set_firmware_dir_getter(lambda: "C:/fw/lib")
    assert "fw/lib" in w.firmware_dir_text().replace("\\", "/")


def test_summary_hidden_without_profile(qtbot):
    """未设 profile（浮窗场景）时不显示「待发送」摘要。"""
    w = FirmwareUpdateSection(); qtbot.addWidget(w)
    assert w._summary.isHidden() is True
    w.set_profile(_profile())
    assert w._summary.isHidden() is False


def test_start_button_emits_signal(qtbot, monkeypatch):
    """点开始按钮，确认框返回 Yes 后触发 start_requested。"""
    w = FirmwareUpdateSection(); qtbot.addWidget(w)
    w.set_profile(_profile())
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    with qtbot.waitSignal(w.start_requested, timeout=500):
        w.start_button().click()


def test_confirm_start_no_does_not_emit(qtbot, monkeypatch):
    """二次确认（B2）：No 不发 start_requested。"""
    w = FirmwareUpdateSection(); qtbot.addWidget(w)
    w.set_profile(_profile())
    emitted = []
    w.start_requested.connect(lambda: emitted.append(1))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.No)
    w.start_button().click()
    assert emitted == []


def test_set_busy_disables_start(qtbot):
    w = FirmwareUpdateSection(); qtbot.addWidget(w)
    w.set_profile(_profile())
    w.set_busy(True)
    assert not w.start_button().isEnabled()
    w.set_busy(False)
    assert w.start_button().isEnabled()


def test_on_progress_updates_bar(qtbot):
    w = FirmwareUpdateSection(); qtbot.addWidget(w)
    w.on_progress(50, 100)
    assert w.progress_value() == 50
    assert w._bar.format() == "50%"
    assert "50%" in w.current_progress_text()


def test_on_log_updates_progress_text(qtbot):
    w = FirmwareUpdateSection(); qtbot.addWidget(w)
    w.on_log("发送 A.wav")
    assert "A.wav" in w.current_progress_text()


def test_on_state_updates_stage_and_resets(qtbot):
    """活动状态清空上一轮残留并显示「就绪」；阶段 chip 文案随状态。"""
    w = FirmwareUpdateSection(); qtbot.addWidget(w)
    w.on_log("旧日志")
    w.on_progress(20, 100)
    w.on_state("transfering")
    assert "传输" in w.stage_text()
    assert w.current_progress_text() == theme.STAGE_TEXT["idle"]
    w.on_progress(45, 100)
    assert "45%" in w.current_progress_text()


def test_set_progress_pct_direct(qtbot):
    """set_progress_pct(pct)：直接设置百分比（浮窗回填接口的基础）。"""
    w = FirmwareUpdateSection(); qtbot.addWidget(w)
    w.set_progress_pct(72)
    assert w.progress_value() == 72
    assert w._bar.format() == "72%"
    assert "72%" in w.current_progress_text()


def test_set_current_text_direct(qtbot):
    """set_current_text(text)：直接覆盖单行进度文本（浮窗回填接口的基础）。"""
    w = FirmwareUpdateSection(); qtbot.addWidget(w)
    w.set_current_text("正在发送 app/")
    assert w.current_progress_text() == "正在发送 app/"
