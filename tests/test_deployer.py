import pathlib, tempfile
from lbs_firmware_studio.backend.profile import DeviceProfile
from lbs_firmware_studio.backend.deployer import DeviceDeployer
from lbs_firmware_studio.backend.serial_transport import SerialTransport
from tests.fakes import make_fake_serial_pair
from tests.simulator import DeviceSimulator


def _profile(name, protocol):
    return DeviceProfile(name=name, protocol=protocol, baud=115200,
                         firmware_enter_cmd=b"RESET_FWLIB" if protocol=="custom_frame" else b"ymodem update fmware\r\n",
                         script_enter_cmd=b"RESET_FWLIB" if protocol=="custom_frame" else b"ymodem\r\n",
                         folders=["app"] if protocol=="custom_frame" else ["__single__"],
                         chunk_size=248 if protocol=="custom_frame" else 1024,
                         last_frame_ack="wait_2s" if protocol=="custom_frame" else "skip",
                         filename_encoding="gbk")


def test_deploy_scripts_custom_frame():
    host_ser, dev_ser = make_fake_serial_pair()
    sim = DeviceSimulator(dev_ser, protocol="custom_frame"); sim.start()
    reopened = []
    def reopen_factory(port, baud):
        reopened.append(port)
        host_ser.is_open = True  # 模拟同一 FakeSerial 重新枚举（模拟器持续在跑）
        return host_ser
    t = SerialTransport(host_ser, reopen_factory=reopen_factory); t.start_rx()
    try:
        dep = DeviceDeployer(transport=t)
        with tempfile.TemporaryDirectory() as d:
            (pathlib.Path(d) / "main.py").write_text("print(1)")
            # 用真编译器会失败；这里 mock compile_scripts 产物
            dep.compile_scripts = lambda profile, py_dir: [pathlib.Path(py_dir) / "main.py.o"]
            # 手动造 .py.o
            (pathlib.Path(d) / "main.py.o").write_bytes(b"\x0F\x70 79o compiled")
            states = []
            dep.state_changed.connect(lambda s: states.append(s))
            dep.deploy_scripts(_profile("NEW-AI", "custom_frame"), "COM_FAKE", pathlib.Path(d))
            assert sim.received_files.get("main.py.o") == b"\x0F\x70 79o compiled"
            assert "done" in states
            assert "reconnecting" in states
            assert reopened == ["COM_FAKE"]
    finally:
        t.stop_rx(); sim.stop()


def test_update_firmware_ymodem():
    host_ser, dev_ser = make_fake_serial_pair()
    sim = DeviceSimulator(dev_ser, protocol="ymodem"); sim.start()
    reopened = []
    def reopen_factory(port, baud):
        reopened.append(port)
        host_ser.is_open = True
        return host_ser
    t = SerialTransport(host_ser, reopen_factory=reopen_factory); t.start_rx()
    try:
        dep = DeviceDeployer(transport=t)
        with tempfile.TemporaryDirectory() as d:
            fw = pathlib.Path(d) / "next.bin"; fw.write_bytes(b"\xAA" * 2048)
            prof = _profile("NEXT-AI", "ymodem")
            prof.firmware_dir = pathlib.Path(d)
            states = []
            dep.state_changed.connect(lambda s: states.append(s))
            dep.update_firmware(prof, "COM_FAKE")
            assert sim.received_files.get("next.bin") == b"\xAA" * 2048
            assert "reconnecting" in states
            assert reopened == ["COM_FAKE"]
    finally:
        t.stop_rx(); sim.stop()
