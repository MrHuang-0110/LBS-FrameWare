from lbs_firmware_studio.gui.pages.firmware_page import FirmwarePage
from lbs_firmware_studio.backend.profile import DeviceProfile
from lbs_firmware_studio.gui import theme
from pathlib import Path
from PySide6.QtWidgets import QMessageBox


def _profile():
    return DeviceProfile(name="NEW-AI", protocol="custom_frame",
                         folders=["app", "music", "boot", "config", "version"],
                         firmware_dir=Path("./products/NEW-AI/fwlib"))


def test_set_profile_shows_folders_and_dir(qtbot):
    w = FirmwarePage(); qtbot.addWidget(w)
    w.set_profile(_profile())
    txt = w.summary_text()
    assert "app" in txt and "music" in txt
    assert "NEW-AI/fwlib" in w.firmware_dir_text().replace("\\", "/")


def test_start_button_emits_signal(qtbot, monkeypatch):
    """点击开始按钮，确认框返回 Yes 后触发 start_requested。"""
    w = FirmwarePage(); qtbot.addWidget(w)
    w.set_profile(_profile())
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    with qtbot.waitSignal(w.start_requested, timeout=500):
        w.start_button().click()


def test_confirm_start_required(qtbot, monkeypatch):
    """开始按钮先弹二次确认（B2）：No 不发 start_requested，Yes 才发。"""
    w = FirmwarePage(); qtbot.addWidget(w)
    w.set_profile(_profile())
    emitted = []
    w.start_requested.connect(lambda: emitted.append(1))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.No)
    w.start_button().click()
    assert emitted == []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    w.start_button().click()
    assert emitted == [1]


def test_confirm_start_direct(qtbot, monkeypatch):
    """confirm_start() 直通方法：No 不发、Yes 发 start_requested。"""
    w = FirmwarePage(); qtbot.addWidget(w)
    w.set_profile(_profile())
    emitted = []
    w.start_requested.connect(lambda: emitted.append(1))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.No)
    w.confirm_start()
    assert emitted == []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    w.confirm_start()
    assert emitted == [1]


def test_set_busy_disables_start(qtbot):
    w = FirmwarePage(); qtbot.addWidget(w)
    w.set_profile(_profile())
    w.set_busy(True)
    assert not w.start_button().isEnabled()
    w.set_busy(False)
    assert w.start_button().isEnabled()


def test_on_progress_updates_bar(qtbot):
    w = FirmwarePage(); qtbot.addWidget(w)
    w.on_progress(50, 100)
    assert w.progress_value() == 50


def test_progress_format_shows_percent(qtbot):
    """进度更新后进度条 setFormat 为 f"{pct}%"（B10）。"""
    w = FirmwarePage(); qtbot.addWidget(w)
    w.on_progress(50, 100)
    assert w.progress_value() == 50
    assert w._bar.format() == "50%"


def test_on_state_updates_stage_text(qtbot):
    w = FirmwarePage(); qtbot.addWidget(w)
    w.on_state("transfering")
    assert "传输" in w.stage_text()


def test_stage_chip_dot_and_color_follow_state(qtbot):
    """阶段 chip：色点矢量图标 + 阶段文案随状态，_stage 文字用 state_color 变色。"""
    w = FirmwarePage(); qtbot.addWidget(w)
    w.on_state("transfering")
    assert "传输" in w.stage_text()
    assert not w.stage_dot().pixmap().isNull()
    assert theme.state_color("transfering") in w._stage.styleSheet()


def test_initial_progress_text_ready(qtbot):
    """无活动时单行进度文本显示「就绪」。"""
    w = FirmwarePage(); qtbot.addWidget(w)
    assert w.current_progress_text() == theme.STAGE_TEXT["idle"]


def test_on_log_updates_progress_text(qtbot):
    """log 信号到达后，单行进度文本更新为该条日志。"""
    w = FirmwarePage(); qtbot.addWidget(w)
    w.on_log("发送 A.wav")
    assert "A.wav" in w.current_progress_text()


def test_progress_text_uses_last_log(qtbot):
    """多条日志到达时取最后一条。"""
    w = FirmwarePage(); qtbot.addWidget(w)
    w.on_log("发送 A.wav")
    w.on_log("发送 B.wav")
    txt = w.current_progress_text()
    assert "B.wav" in txt and "A.wav" not in txt


def test_progress_text_shows_percent(qtbot):
    """进度信号到达后文本含百分比。"""
    w = FirmwarePage(); qtbot.addWidget(w)
    w.on_progress(45, 100)
    assert "45%" in w.current_progress_text()


def test_progress_text_combines_last_log_and_percent(qtbot):
    """log + 进度信号后，文本由最后一条日志与百分比合成（如「正在发送 app/ 45%」）。"""
    w = FirmwarePage(); qtbot.addWidget(w)
    w.on_log("发送 app/")
    w.on_progress(45, 100)
    txt = w.current_progress_text()
    assert "app/" in txt and "45%" in txt


def test_on_state_idle_resets_progress_text(qtbot):
    """回到 idle 状态（无活动）时重置为「就绪」。"""
    w = FirmwarePage(); qtbot.addWidget(w)
    w.on_log("发送 A.wav")
    w.on_progress(50, 100)
    w.on_state("idle")
    assert w.current_progress_text() == theme.STAGE_TEXT["idle"]


def test_on_state_connecting_resets_previous_round(qtbot):
    """新一轮开始（connecting，不经 idle）清除上一轮残留文本并刷新为「就绪」。"""
    w = FirmwarePage(); qtbot.addWidget(w)
    w.on_log("发送 A.wav")      # 第一轮残留
    w.on_progress(50, 100)
    w.on_state("connecting")    # 第二轮开始
    assert w.current_progress_text() == theme.STAGE_TEXT["idle"]
    assert "A.wav" not in w.current_progress_text()
    assert "50%" not in w.current_progress_text()


def test_on_state_transfering_resets_previous_round(qtbot):
    """其它活动状态（transfering）同样清空上一轮残留，不破坏新进度累计。"""
    w = FirmwarePage(); qtbot.addWidget(w)
    w.on_log("旧日志")
    w.on_progress(20, 100)
    w.on_state("transfering")
    assert w.current_progress_text() == theme.STAGE_TEXT["idle"]
    w.on_progress(45, 100)      # 新一轮进度照常累计
    assert "45%" in w.current_progress_text()


def test_on_state_done_keeps_last_log_snapshot(qtbot):
    """done 保留「最后日志 + 进度」快照（成功语义），不被新一轮连接清空前仍可见。"""
    w = FirmwarePage(); qtbot.addWidget(w)
    w.on_log("发送 B.wav")
    w.on_progress(100, 100)
    w.on_state("done")
    assert "B.wav" in w.current_progress_text()
    assert "100%" in w.current_progress_text()
