import pathlib, tempfile
import pytest
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


class _FakeLink:
    """最小 transport 桩：只提供 link_kind，供 _make_protocol 选块大小。"""
    def __init__(self, kind):
        self.link_kind = kind


def test_ymodem_block_size_128_over_ble_1024_over_serial():
    """蓝牙 YMODEM 用 128B 块(ECB02 透传单帧≤248B)，串口沿用 profile.chunk_size(1024)。
    真机根因：1024 块经蓝牙拆多片致设备缓冲溢出→NAK。对齐 pika_deploy.py BT_YMODEM_BLOCK。"""
    prof = _profile("NEXT-AI", "ymodem")   # chunk_size=1024
    ble_proto = DeviceDeployer(transport=_FakeLink("ble"))._make_protocol(prof)
    assert ble_proto.block_size == 128
    ser_proto = DeviceDeployer(transport=_FakeLink("serial"))._make_protocol(prof)
    assert ser_proto.block_size == 1024


def test_ymodem_firmware_dir_requires_exactly_one_file():
    """NEXT-AI 单文件约定（folders=[__single__]）：固件目录空/多文件时抛清晰异常，不发 done。
    review T4-D1/D6：sorted(glob) 取第一个文件零防御，目录空/多文件静默误报 done。"""
    host_ser, dev_ser = make_fake_serial_pair()
    sim = DeviceSimulator(dev_ser, protocol="ymodem"); sim.start()
    t = SerialTransport(host_ser); t.start_rx()
    try:
        dep = DeviceDeployer(transport=t)
        with tempfile.TemporaryDirectory() as d:
            prof = _profile("NEXT-AI", "ymodem")
            prof.firmware_dir = pathlib.Path(d)   # 空目录：零文件
            errors, states = [], []
            dep.error.connect(lambda e: errors.append(e))
            dep.state_changed.connect(lambda s: states.append(s))
            with pytest.raises(RuntimeError, match="单文件约定"):
                dep.update_firmware(prof, "COM_FAKE")
            assert errors and "done" not in states
            # 多文件：单文件约定被破坏，不得静默取第一个
            (pathlib.Path(d) / "a.bin").write_bytes(b"\xAA" * 32)
            (pathlib.Path(d) / "b.bin").write_bytes(b"\xBB" * 32)
            errors.clear(); states.clear()
            with pytest.raises(RuntimeError, match="单文件约定"):
                dep.update_firmware(prof, "COM_FAKE")
            assert errors and "done" not in states
    finally:
        t.stop_rx(); sim.stop()


def test_custom_frame_missing_folder_logs_warning():
    """custom_frame 某 folders 目录缺失：经 log 信号告警而非静默跳过，其余目录照常发送。
    review T4-D2：if sub.exists() 静默跳过缺失目录，用户误以为全部已升级。"""
    host_ser, dev_ser = make_fake_serial_pair()
    sim = DeviceSimulator(dev_ser, protocol="custom_frame"); sim.start()
    def reopen_factory(port, baud):
        host_ser.is_open = True
        return host_ser
    t = SerialTransport(host_ser, reopen_factory=reopen_factory); t.start_rx()
    try:
        dep = DeviceDeployer(transport=t)
        with tempfile.TemporaryDirectory() as d:
            app = pathlib.Path(d) / "app"; app.mkdir()
            (app / "0.o").write_bytes(b"app data")
            prof = _profile("NEW-AI", "custom_frame")
            prof.firmware_dir = pathlib.Path(d)
            prof.folders = ["app", "music"]   # music 目录缺失
            logs, states, errors = [], [], []
            dep.log.connect(lambda m: logs.append(m))
            dep.state_changed.connect(lambda s: states.append(s))
            dep.error.connect(lambda e: errors.append(e))
            dep.update_firmware(prof, "COM_FAKE")
            assert sim.received_files.get("0.o") == b"app data"
            assert any("music" in m and "缺失" in m for m in logs)
            assert "done" in states and not errors
    finally:
        t.stop_rx(); sim.stop()


def test_custom_frame_empty_folders_not_done():
    """folders 目录全部缺失/为空：发 error 而非 done（空会话不再静默报完成）。
    review T4-D2：全部缺失时仅 enter->reconnect->空 finish_session 仍报 done。"""
    host_ser, dev_ser = make_fake_serial_pair()
    sim = DeviceSimulator(dev_ser, protocol="custom_frame"); sim.start()
    def reopen_factory(port, baud):
        host_ser.is_open = True
        return host_ser
    t = SerialTransport(host_ser, reopen_factory=reopen_factory); t.start_rx()
    try:
        dep = DeviceDeployer(transport=t)
        with tempfile.TemporaryDirectory() as d:
            prof = _profile("NEW-AI", "custom_frame")
            prof.firmware_dir = pathlib.Path(d)   # 无任何 folders 子目录
            errors, states = [], []
            dep.error.connect(lambda e: errors.append(e))
            dep.state_changed.connect(lambda s: states.append(s))
            with pytest.raises(RuntimeError):
                dep.update_firmware(prof, "COM_FAKE")
            assert errors and "done" not in states and "error" in states
            # 目录存在但为空：同样不得报 done
            app = pathlib.Path(d) / "app"; app.mkdir()
            with pytest.raises(RuntimeError):
                dep.update_firmware(prof, "COM_FAKE")
            assert "done" not in states and "error" in states
    finally:
        t.stop_rx(); sim.stop()


def test_signal_stub_multiple_connect(monkeypatch):
    """PySide6 缺失降级 Signal 桩：多 connect 不覆盖，emit 触发全部回调。
    review T4-D3：原桩 connect 只存单个 _fn，二次 connect 覆盖首个致回调丢失。
    通过把 sys.modules["PySide6"] 置 None 强制 deployer 重新导入走 except 桩分支。"""
    import importlib, sys
    mod_name = "lbs_firmware_studio.backend.deployer"
    saved = sys.modules.get(mod_name)
    monkeypatch.setitem(sys.modules, "PySide6", None)   # 强制走桩分支
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", None)  # 否则 from PySide6.QtCore import Signal 直接取真实模块跳过桩
    try:
        if saved is not None:
            sys.modules.pop(mod_name, None)
        dep = importlib.import_module(mod_name)
        got = []
        sig = dep.Signal(str)
        sig.connect(lambda s: got.append(("a", s)))
        sig.connect(lambda s: got.append(("b", s)))
        sig.emit("hi")
        assert got == [("a", "hi"), ("b", "hi")]
    finally:
        if saved is not None:
            sys.modules[mod_name] = saved
