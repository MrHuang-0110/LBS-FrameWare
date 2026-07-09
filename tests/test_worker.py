import pathlib, tempfile
from lbs_firmware_studio.backend.profile import DeviceProfile
from lbs_firmware_studio.backend.deployer import DeviceDeployer
from lbs_firmware_studio.backend.serial_transport import SerialTransport
from lbs_firmware_studio.gui.worker import DeployWorker
from tests.fakes import make_fake_serial_pair
from tests.simulator import DeviceSimulator


def _profile(d):
    return DeviceProfile(name="NEW-AI", protocol="custom_frame",
                         firmware_enter_cmd=b"RESET_FWLIB", script_enter_cmd=b"RESET_FWLIB",
                         folders=["app"], chunk_size=248, last_frame_ack="wait_2s",
                         filename_encoding="gbk", firmware_dir=pathlib.Path(d),
                         reopen_retries=3, reopen_delay=0.02, post_reopen_delay=0.0,
                         disappear_timeout=0.0)


def test_worker_runs_firmware_and_emits_finished(qtbot):
    host_ser, dev_ser = make_fake_serial_pair()
    sim = DeviceSimulator(dev_ser, protocol="custom_frame"); sim.start()
    # 固件更新内部会复位并重新枚举端口(wait_for_reopen)。用假串口驱动模拟器时，
    # 注入 reopen_factory 复用同一 host_ser（与 test_deployer.py 相同做法），否则会
    # 尝试真实 serial.Serial("COM_FAKE") 而失败。
    def reopen_factory(port, baud):
        host_ser.is_open = True
        return host_ser
    t = SerialTransport(host_ser, reopen_factory=reopen_factory); t.start_rx()
    try:
        with tempfile.TemporaryDirectory() as d:
            app = pathlib.Path(d) / "app"; app.mkdir()
            (app / "0.o").write_bytes(b"firmware data")
            dep = DeviceDeployer(t)
            worker = DeployWorker(t, dep)
            states = []
            dep.state_changed.connect(lambda s: states.append(s))
            with qtbot.waitSignal(worker.finished, timeout=5000):
                worker.run_firmware(_profile(d), "COM_FAKE")
            assert "done" in states
            assert sim.received_files.get("0.o") == b"firmware data"
    finally:
        t.stop_rx(); sim.stop()


def test_worker_emits_finished_on_error(qtbot):
    # 传一个协议会失败的场景：不启动模拟器 -> 无 ACK -> error，但 finished 仍应发出
    host_ser, dev_ser = make_fake_serial_pair()
    t = SerialTransport(host_ser); t.start_rx()
    try:
        with tempfile.TemporaryDirectory() as d:
            app = pathlib.Path(d) / "app"; app.mkdir()
            (app / "0.o").write_bytes(b"x" * 500)
            prof = _profile(d); prof.ack_timeout = 0.1; prof.last_frame_ack = "skip"
            dep = DeviceDeployer(t)
            worker = DeployWorker(t, dep)
            errors = []
            dep.error.connect(lambda e: errors.append(e))
            with qtbot.waitSignal(worker.finished, timeout=5000):
                worker.run_firmware(prof, "COM_FAKE")
            assert errors  # 有错误上报
    finally:
        t.stop_rx(); sim_close(t)


def sim_close(t):
    try: t.stop_rx()
    except Exception: pass
