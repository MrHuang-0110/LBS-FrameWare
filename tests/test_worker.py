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
                worker.set_job(_profile(d), "COM_FAKE"); worker.run_firmware()
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
                worker.set_job(prof, "COM_FAKE"); worker.run_firmware()
            assert errors  # 有错误上报
    finally:
        t.stop_rx(); sim_close(t)


def test_worker_reports_open_failure(qtbot):
    # transport.open() 在 update_firmware 之前抛出（端口占用/拔线），
    # worker 应补发 deployer.error，并且 finished 仍必发。
    class FailingTransport:
        def open(self, port, baud):
            raise OSError("port busy")
        def start_rx(self):
            pass
        def close(self):
            pass
    t = FailingTransport()
    with tempfile.TemporaryDirectory() as d:
        dep = DeviceDeployer(t)
        worker = DeployWorker(t, dep)
        errors = []
        dep.error.connect(lambda e: errors.append(e))
        with qtbot.waitSignal(worker.finished, timeout=5000):
            worker.set_job(_profile(d), "COM_FAKE"); worker.run_firmware()
        assert errors  # open() 失败已上报
        assert any("port busy" in e for e in errors)


def sim_close(t):
    try: t.stop_rx()
    except Exception: pass


def test_run_firmware_executes_off_main_thread(qtbot):
    """回归锁定：用 MainWindow 的接线方式(moveToThread + started 直连 run_firmware 槽)，
    run_firmware 必须在子线程执行，绝不在主线程——否则阻塞式串口 I/O 会卡死 GUI。
    历史 bug: started.connect(lambda: worker.run_firmware(...)) 会跑在主线程。"""
    import threading
    from PySide6.QtCore import QThread

    class _Probe:
        """替身 transport：open 时记录线程 ident，不做真 I/O。"""
        ran_thread = None
        def open(self, port, baud): _Probe.ran_thread = threading.get_ident()
        def start_rx(self): pass
        def close(self): pass

    main_ident = threading.get_ident()
    probe = _Probe()
    dep = DeviceDeployer(probe)
    thread = QThread()
    worker = DeployWorker(probe, dep)
    with tempfile.TemporaryDirectory() as d:
        worker.set_job(_profile(d), "COM_FAKE")
        worker.moveToThread(thread)
        thread.started.connect(worker.run_firmware)   # ← MainWindow 的正确接线
        worker.finished.connect(thread.quit)
        with qtbot.waitSignal(worker.finished, timeout=5000):
            thread.start()
        thread.wait(3000)
    assert _Probe.ran_thread is not None
    assert _Probe.ran_thread != main_ident, "run_firmware 跑在主线程 => GUI 会卡死"
