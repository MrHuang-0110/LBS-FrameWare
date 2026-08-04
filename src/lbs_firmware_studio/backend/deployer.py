"""编排层：按 DeviceProfile 驱动编译->连接->进升级->传输->收尾，用 Qt 信号上报。"""
from __future__ import annotations
from pathlib import Path
try:
    from PySide6.QtCore import QObject, Signal
except ImportError:  # 后端可脱离 PySide6 运行（CLI/测试）
    class QObject:  # type: ignore
        def __init__(self, *a, **k): pass
    class Signal:  # type: ignore
        def __init__(self, *a, **k): self._fns = []
        def connect(self, fn): self._fns.append(fn)
        def emit(self, *a, **k):
            for fn in self._fns: fn(*a, **k)

from .transfer_protocol import CustomFrameProtocol, YmodemProtocol
from .pika_compiler import compile_py
from .profile import DeviceProfile


class DeviceDeployer(QObject):
    progress = Signal(int, int)
    log = Signal(str)
    state_changed = Signal(str)
    error = Signal(str)

    def __init__(self, transport=None):
        super().__init__()
        self._transport = transport

    def set_transport(self, transport) -> None:
        self._transport = transport

    def _compile_to_slot(self, profile: DeviceProfile, py_path: Path, slot: int) -> Path:
        """把单个 .py 编译成 <slot>.o（设备端按槽位命名）。"""
        self.state_changed.emit("compiling")
        out = Path(py_path).parent / f"{slot}.o"
        self.log.emit(f"compile {Path(py_path).name} -> {slot}.o")
        compile_py(Path(py_path), out, profile.compiler_path)
        return out

    def _make_protocol(self, profile: DeviceProfile):
        is_ble = getattr(self._transport, "link_kind", "serial") == "ble"
        if profile.protocol == "custom_frame":
            # BLE 链路：设备接收缓冲有限，减 chunk 避免单帧过大导致设备不收
            return CustomFrameProtocol(chunk_size=200 if is_ble else profile.chunk_size,
                                       ack_timeout=profile.ack_timeout,
                                       last_frame_ack=profile.last_frame_ack,
                                       filename_encoding=profile.filename_encoding,
                                       log_cb=self.log.emit)
        # YMODEM 块大小按链路区分：蓝牙(ECB02 透传)单帧 ≤248B，1024 块会被拆多片致设备缓冲
        # 溢出→NAK→CAN(真机复现)。故蓝牙用 128B 块(YMODEM 包 133B 一次发出)，USB 沿用 1024。
        # 对齐参考工具 LBS-NEXT-AI/tools/pika_deploy.py 的 BT_YMODEM_BLOCK/USB_YMODEM_BLOCK。
        block_size = 128 if is_ble else profile.chunk_size
        return YmodemProtocol(block_size=block_size, ack_timeout=90.0 if is_ble else 12.0,
                              log_cb=self.log.emit)

    def _enter_and_reconnect(self, proto, profile: DeviceProfile, port: str, *, firmware: bool) -> None:
        """进入升级模式 -> USB 复位 -> 轮询重连 -> 重新武装 RX（spec §5.2-5.4 强制流程）。"""
        self.state_changed.emit("entering_upgrade")
        enter_cmd = profile.firmware_enter_cmd if firmware else profile.script_enter_cmd
        proto.enter_upgrade_mode(self._transport, firmware=firmware, enter_cmd=enter_cmd)
        self.state_changed.emit("reconnecting")
        ok = self._transport.wait_for_reopen(port, profile.baud, profile.reopen_retries,
                                             profile.reopen_delay, profile.post_reopen_delay,
                                             profile.disappear_timeout)
        if not ok:
            raise RuntimeError(f"device did not re-enumerate on {port}")
        self._transport.start_rx()  # wait_for_reopen 内的 close() 停了 RX 线程，这里再武装

    def _validate_firmware_sources(self, profile: DeviceProfile) -> None:
        """发送前校验固件源，防止零文件/多文件静默误报 done。

        - ymodem(NEXT-AI，folders=[__single__] 单文件约定)：固件目录必须恰好一个文件，
          0 个/多个均抛清晰异常（单文件约定被破坏）。
        - custom_frame(NEW-AI/SPARK-AI)：缺失或为空的 folders 目录经 log 信号告警（不静默
          跳过）；全部目录均不可用时直接抛错，避免空会话报"完成"。
        """
        fw_dir = Path(profile.firmware_dir)
        if profile.protocol == "ymodem":
            files = [f for f in sorted(fw_dir.glob("*")) if f.is_file()]
            if not files:
                raise RuntimeError(
                    f"固件目录无任何固件文件: {fw_dir}（NEXT-AI [__single__] 单文件约定被破坏）")
            if len(files) > 1:
                names = ", ".join(f.name for f in files)
                raise RuntimeError(
                    f"固件目录含 {len(files)} 个文件（{names}），期望恰好 1 个"
                    f"（NEXT-AI [__single__] 单文件约定被破坏）")
            return
        # custom_frame：缺失/空目录告警，全部不可用时报错
        for folder in profile.folders:
            sub = fw_dir / folder
            if not sub.is_dir():
                self.log.emit(f"WARN: 固件文件夹缺失: {sub}")
            elif not any(p.is_file() for p in sub.iterdir()):
                self.log.emit(f"WARN: 固件文件夹为空: {sub}")
        usable = [f for f in profile.folders
                  if (fw_dir / f).is_dir() and any(p.is_file() for p in (fw_dir / f).iterdir())]
        if not usable:
            raise RuntimeError(
                f"固件目录 {fw_dir} 下 folders 全部缺失或为空: {profile.folders}"
                f"（firmware_dir 与配置不同步）")

    def update_firmware(self, profile: DeviceProfile, port: str) -> None:
        try:
            self._validate_firmware_sources(profile)
            self.state_changed.emit("connecting")
            proto = self._make_protocol(profile)
            self._enter_and_reconnect(proto, profile, port, firmware=True)
            self.state_changed.emit("transfering")
            if profile.protocol == "custom_frame":
                fw_dir = Path(profile.firmware_dir)
                for folder in profile.folders:
                    sub = fw_dir / folder
                    if sub.is_dir():
                        proto.send_folder(self._transport, sub, folder, self._on_progress)  # type: ignore[attr-defined]
            else:
                for fw in sorted(Path(profile.firmware_dir).glob("*")):
                    if fw.is_file():
                        proto.send_file(self._transport, fw, self._on_progress, firmware=True)
                        break
            proto.finish_session(self._transport, firmware=True)
            self.state_changed.emit("done")
        except Exception as e:
            self.error.emit(str(e))
            self.state_changed.emit("error")
            raise

    def deploy_script(self, profile: DeviceProfile, port: str, py_path: Path, slot: int = 0) -> None:
        """把单个 .py 编译为 <slot>.o 并下发到设备对应槽位（阶段1固定 slot=0）。

        脚本下发**不复位设备、不重连**（区别于固件更新）：
        - custom_frame(NEW-AI/SPARK-AI): 直接在当前串口发 <slot>.o(0xDA)，无进入命令。
        - ymodem(NEXT-AI): 发 script_enter_cmd("ymodem\\r\\n") 让运行中的 app 进 YMODEM
          接收态（非固件复位、不重新枚举），随后同串口 YMODEM 传输。
        """
        try:
            o_file = self._compile_to_slot(profile, py_path, slot)
            self.state_changed.emit("connecting")
            proto = self._make_protocol(profile)
            if profile.protocol == "ymodem":
                # 仅发进入 YMODEM 的命令，不复位/不重连
                proto.enter_upgrade_mode(self._transport, firmware=False,
                                         enter_cmd=profile.script_enter_cmd)
            self.state_changed.emit("transfering")
            proto.send_file(self._transport, o_file, self._on_progress, firmware=False)
            proto.finish_session(self._transport, firmware=False)
            self.state_changed.emit("done")
        except Exception as e:
            self.error.emit(str(e))
            self.state_changed.emit("error")
            raise

    def _on_progress(self, done: int, total: int) -> None:
        self.progress.emit(done, total)
