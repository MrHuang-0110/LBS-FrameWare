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
    display_ports: int = 0    # 启动卡片展示的端口数(纯展示，不影响协议)
    max_slot: int = 0                       # 脚本槽位上限（0..max_slot），按产品配置
    templates_dir: Path = Path("./templates")  # 预加载模板目录，load 时按产品根推导
    ble_enabled: bool = False                   # 该产品是否支持蓝牙通道
    ble_firmware: bool = False                  # 蓝牙是否支持固件更新(custom_frame=False)


# _to_bytes 只解释 YAML 双引号常用的受控转义（\r \n \t \\）。
# 不用 unicode_escape：它会把 \f/\x/\U 等 Python 转义误解释（如 "C:\fw\lib" 的 \f 变 form feed），
# 且 Python 3.12+ 对非法 \U 序列抛 UnicodeDecodeError，使 load_profiles 直接崩溃。
_ESCAPES = {"r": "\r", "n": "\n", "t": "\t", "\\": "\\"}


def _to_bytes(val) -> bytes:
    if isinstance(val, bytes):
        return val
    if isinstance(val, str):
        out: list[str] = []
        i, n = 0, len(val)
        while i < n:
            ch = val[i]
            if ch == "\\" and i + 1 < n and val[i + 1] in _ESCAPES:
                out.append(_ESCAPES[val[i + 1]])
                i += 2
                continue
            out.append(ch)
            i += 1
        return "".join(out).encode("utf-8")
    return b""


def _resolve(base: Path, p) -> Path:
    """相对路径基于 base 解析为绝对；绝对路径原样(经 resolve 规整)。"""
    p = Path(p)
    return p.resolve() if p.is_absolute() else (base / p).resolve()


def load_profiles(path: Path) -> dict[str, DeviceProfile]:
    path = Path(path).resolve()
    base = path.parent
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    compiler = _resolve(base, raw.get("compiler_path", "./tools/rust-msc-latest-win10.exe"))
    out: dict[str, DeviceProfile] = {}
    for name, cfg in raw.get("products", {}).items():
        firmware_dir = cfg.get("firmware_dir", ".")
        # templates_dir 优先取显式 yaml 键，缺省时回退至 firmware_dir 的父目录/templates（保持向后兼容）
        if "templates_dir" in cfg:
            templates_dir = _resolve(base, cfg["templates_dir"])
        else:
            templates_dir = _resolve(base, Path(firmware_dir).parent / "templates")
        ble_cfg = cfg.get("ble", {}) or {}
        ble_enabled = bool(ble_cfg.get("enabled", False))
        ble_firmware = bool(ble_cfg.get("firmware_over_ble", False))
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
            script_dirs={_resolve(base, k): _resolve(base, v) for k, v in cfg.get("script_dirs", {}).items()},
            firmware_dir=_resolve(base, firmware_dir),
            reopen_retries=cfg.get("reopen_retries", 5),
            reopen_delay=cfg.get("reopen_delay", 2.0),
            post_reopen_delay=cfg.get("post_reopen_delay", 5.0),
            disappear_timeout=cfg.get("disappear_timeout", 5.0),
            display_ports=cfg.get("display_ports", 0),
            max_slot=cfg.get("max_slot", 0),
            templates_dir=templates_dir,
            ble_enabled=ble_enabled,
            ble_firmware=ble_firmware,
        )
    return out


def save_profiles(raw: dict, path: Path) -> None:
    """把配置字典写回 YAML。注意 safe_dump 会丢失注释（本阶段接受）。"""
    path.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
