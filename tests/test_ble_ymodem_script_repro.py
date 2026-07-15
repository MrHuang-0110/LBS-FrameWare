"""Phase 3 判定性复现：真实时序「BLE 监控(挂handler)→停监控(摘handler)→YMODEM脚本下发」。
用于区分 NEXT-AI 蓝牙下发卡住的根因是主机侧(handler残留/read_byte死等)还是设备侧。"""
import pathlib, tempfile, time
from lbs_firmware_studio.backend.profile import DeviceProfile
from lbs_firmware_studio.backend.deployer import DeviceDeployer
from lbs_firmware_studio.backend.ble_transport import BleTransport
from tests.fakes import make_fake_ble_pair
from tests.simulator import DeviceSimulator


def _next_ai():
    return DeviceProfile(name="NEXT-AI", protocol="ymodem", baud=115200,
                         firmware_enter_cmd=b"ymodem update fmware\r\n",
                         script_enter_cmd=b"ymodem\r\n",
                         folders=["__single__"], chunk_size=1024,
                         last_frame_ack="skip", filename_encoding="utf-8",
                         reopen_retries=3, reopen_delay=0.02, post_reopen_delay=0.0,
                         disappear_timeout=0.0)


def test_ymodem_script_deploy_over_ble_after_monitor(tmp_path):
    """监控挂过 data_handler 后停监控摘掉，再经同一 BLE 链路做 YMODEM 脚本下发应成功。"""
    client, dev = make_fake_ble_pair(mtu_size=247)
    sim = DeviceSimulator(dev, protocol="ymodem", emit_json=True)  # 监控期设备持续吐 JSON
    sim.start()
    t = BleTransport(client_factory=lambda addr: client)
    t.open("addr")
    try:
        # 1) 模拟监控：挂 data_handler + start_rx（等价 MonitorWorker.start_on）
        frames = []
        t.set_data_handler(lambda d: frames.append(d))
        t.start_rx()
        time.sleep(0.1)
        # 2) 停监控：摘 handler（等价 MonitorWorker.stop 的 owns_lifecycle=False 分支）
        t.set_data_handler(None)
        # 3) YMODEM 脚本下发
        dep = DeviceDeployer(transport=t)
        py = tmp_path / "script.py"; py.write_text("print(1)")
        def fake_compile(profile, py_path, slot):
            out = tmp_path / f"{slot}.o"; out.write_bytes(b"\xBB" * 300); return out
        dep._compile_to_slot = fake_compile
        dep.deploy_script(_next_ai(), "addr", py, slot=0)
        time.sleep(0.2)
        assert sim.received_files.get("0.o") == b"\xBB" * 300
    finally:
        sim.stop(); t.close()
