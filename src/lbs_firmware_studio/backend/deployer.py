"""编排层：按 DeviceProfile 驱动编译->连接->进升级->传输->收尾，用 Qt 信号上报。"""
from __future__ import annotations
from pathlib import Path
try:
    from PySide6.QtCore import QObject, Signal
except ImportError:  # 后端可脱离 PySide6 运行（CLI/测试）
    class QObject:  # type: ignore
        def __init__(self, *a, **k): pass
    class Signal:  # type: ignore
        def __init__(self, *a, **k): pass
        def connect(self, fn): self._fn = fn
        def emit(self, *a, **k):
            if hasattr(self, "_fn"): self._fn(*a, **k)

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

    def compile_scripts(self, profile: DeviceProfile, py_dir: Path) -> list[Path]:
        self.state_changed.emit("compiling")
        outs = []
        for py in sorted(Path(py_dir).glob("*.py")):
            out = Path(py_dir) / (py.stem + ".py.o")
            self.log.emit(f"compile {py.name}")
            compile_py(py, out, profile.compiler_path)
            outs.append(out)
        return outs

    def _make_protocol(self, profile: DeviceProfile):
        if profile.protocol == "custom_frame":
            return CustomFrameProtocol(chunk_size=profile.chunk_size, ack_timeout=profile.ack_timeout,
                                       last_frame_ack=profile.last_frame_ack,
                                       filename_encoding=profile.filename_encoding)
        return YmodemProtocol(block_size=profile.chunk_size, ack_timeout=12.0)

    def _enter_and_reconnect(self, proto, profile: DeviceProfile, port: str, *, firmware: bool) -> None:
        """进入升级模式 -> USB 复位 -> 轮询重连 -> 重新武装 RX（spec §5.2-5.4 强制流程）。"""
        self.state_changed.emit("entering_upgrade")
        enter_cmd = profile.firmware_enter_cmd if firmware else profile.script_enter_cmd
        proto.enter_upgrade_mode(self._transport, firmware=firmware, enter_cmd=enter_cmd)
        self.state_changed.emit("reconnecting")
        ok = self._transport.wait_for_reopen(port, profile.baud, profile.reopen_retries, profile.reopen_delay)
        if not ok:
            raise RuntimeError(f"device did not re-enumerate on {port}")
        self._transport.start_rx()  # wait_for_reopen 内的 close() 停了 RX 线程，这里再武装

    def update_firmware(self, profile: DeviceProfile, port: str) -> None:
        try:
            self.state_changed.emit("connecting")
            proto = self._make_protocol(profile)
            self._enter_and_reconnect(proto, profile, port, firmware=True)
            self.state_changed.emit("transfering")
            if profile.protocol == "custom_frame":
                fw_dir = Path(profile.firmware_dir)
                for folder in profile.folders:
                    sub = fw_dir / folder
                    if sub.exists():
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

    def deploy_scripts(self, profile: DeviceProfile, port: str, py_dir: Path) -> None:
        try:
            outs = self.compile_scripts(profile, py_dir)
            self.state_changed.emit("connecting")
            proto = self._make_protocol(profile)
            self._enter_and_reconnect(proto, profile, port, firmware=False)
            self.state_changed.emit("transfering")
            if profile.protocol == "custom_frame":
                # 脚本作为 app 文件夹下发
                import tempfile, shutil
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmp = Path(tmpdir)
                    for o in outs:
                        shutil.copy(o, tmp / o.name)
                    proto.send_folder(self._transport, tmp, "app", self._on_progress)  # type: ignore[attr-defined]
            else:
                if len(outs) > 1:
                    raise RuntimeError("multi-file YMODEM script deploy not supported in Phase 1a — deploy one .py at a time")
                for o in outs:
                    proto.send_file(self._transport, o, self._on_progress, firmware=False)
            proto.finish_session(self._transport, firmware=False)
            self.state_changed.emit("done")
        except Exception as e:
            self.error.emit(str(e))
            self.state_changed.emit("error")
            raise

    def _on_progress(self, done: int, total: int) -> None:
        self.progress.emit(done, total)
