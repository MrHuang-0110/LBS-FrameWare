"""产品配置：DeviceProfile 数据类 + 从 YAML 加载。"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import yaml


@dataclass
class DeviceProfile:
    name: str
    protocol: str                          # "custom_frame" | "ymodem"
    baud: int = 115200
    firmware_enter_cmd: bytes = b""
    script_enter_cmd: bytes = b""
    folders: list[str] = field(default_factory=list)
    chunk_size: int = 248
    ack_timeout: float = 2.0
    last_frame_ack: str = "wait_2s"
    filename_encoding: str = "gbk"
    compiler_path: Path = Path("./tools/rust-msc-latest-win10.exe")
    script_dirs: dict = field(default_factory=dict)
    firmware_dir: Path = Path(".")
    reopen_retries: int = 5
    reopen_delay: float = 2.0
    post_reopen_delay: float = 5.0   # 重开串口成功后等待设备 USB CDC/固件初始化（原工具经验值 5s）
    disappear_timeout: float = 5.0   # 等端口从存在->消失的最长时间（复位到端口消失实测~1.4s）


def _to_bytes(val) -> bytes:
    if isinstance(val, bytes):
        return val
    if isinstance(val, str):
        # 允许含转义序列的字符串（如 "ymodem\r\n"）按字面解释
        return val.encode("utf-8").decode("unicode_escape").encode("latin-1")
    return b""


def load_profiles(path: Path) -> dict[str, DeviceProfile]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    compiler = Path(raw.get("compiler_path", "./tools/rust-msc-latest-win10.exe"))
    out: dict[str, DeviceProfile] = {}
    for name, cfg in raw.get("products", {}).items():
        out[name] = DeviceProfile(
            name=name,
            protocol=cfg["protocol"],
            baud=cfg.get("baud", 115200),
            firmware_enter_cmd=_to_bytes(cfg.get("firmware_enter_cmd", "")),
            script_enter_cmd=_to_bytes(cfg.get("script_enter_cmd", "")),
            folders=cfg.get("folders", []),
            chunk_size=cfg.get("chunk_size", 248),
            ack_timeout=cfg.get("ack_timeout", 2.0),
            last_frame_ack=cfg.get("last_frame_ack", "wait_2s"),
            filename_encoding=cfg.get("filename_encoding", "gbk"),
            compiler_path=compiler,
            script_dirs={Path(k): Path(v) for k, v in cfg.get("script_dirs", {}).items()},
            firmware_dir=Path(cfg.get("firmware_dir", ".")),
            reopen_retries=cfg.get("reopen_retries", 5),
            reopen_delay=cfg.get("reopen_delay", 2.0),
            post_reopen_delay=cfg.get("post_reopen_delay", 5.0),
            disappear_timeout=cfg.get("disappear_timeout", 5.0),
        )
    return out
