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
                         filename_encoding="gbk",
                         reopen_retries=3, reopen_delay=0.02, post_reopen_delay=0.0,
                         disappear_timeout=0.0)


def test_deploy_script_custom_frame_slot0():
    """单脚本下发到槽 0：编译为 0.o，经 app 通道发送。脚本下发不复位/不重连设备。"""
    host_ser, dev_ser = make_fake_serial_pair()
    sim = DeviceSimulator(dev_ser, protocol="custom_frame"); sim.start()
    reopened = []
    def reopen_factory(port, baud):
        reopened.append(port)
        host_ser.is_open = True
        return host_ser
    t = SerialTransport(host_ser, reopen_factory=reopen_factory); t.start_rx()
    try:
        dep = DeviceDeployer(transport=t)
        with tempfile.TemporaryDirectory() as d:
            py = pathlib.Path(d) / "my_remote.py"; py.write_text("print(1)")
            # mock 编译：把 <slot>.o 造出来（避免调真编译器）
            def fake_compile(profile, py_path, slot):
                out = pathlib.Path(d) / f"{slot}.o"
                out.write_bytes(b"\x0F\x70 79o compiled")
                return out
            dep._compile_to_slot = fake_compile
            states = []
            dep.state_changed.connect(lambda s: states.append(s))
            dep.deploy_script(_profile("NEW-AI", "custom_frame"), "COM_FAKE", py, slot=0)
            # 设备应收到 0.o
            assert sim.received_files.get("0.o") == b"\x0F\x70 79o compiled"
            assert "done" in states
            # 脚本下发不复位/不重连设备
            assert "reconnecting" not in states
            assert reopened == []
    finally:
        t.stop_rx(); sim.stop()


def test_deploy_script_ymodem_slot0():
    """NEXT-AI 单脚本下发到槽 0：编译为 0.o，经 YMODEM 发送。脚本下发不复位设备。"""
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
            py = pathlib.Path(d) / "script.py"; py.write_text("print(1)")
            def fake_compile(profile, py_path, slot):
                out = pathlib.Path(d) / f"{slot}.o"
                out.write_bytes(b"\xBB" * 300)
                return out
            dep._compile_to_slot = fake_compile
            dep.deploy_script(_profile("NEXT-AI", "ymodem"), "COM_FAKE", py, slot=0)
            assert sim.received_files.get("0.o") == b"\xBB" * 300
            assert reopened == []  # 不重连
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
