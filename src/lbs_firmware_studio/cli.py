"""无头 CLI：阶段 1a 的可运行交付物，证明后端可脱离 GUI 工作。"""
from __future__ import annotations
import sys, argparse
from pathlib import Path
from .backend.profile import load_profiles
from .backend.deployer import DeviceDeployer
from .backend.serial_transport import SerialTransport
from .paths import base_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lbs-firmware")
    parser.add_argument("--config", default=None)
    parser.add_argument("--list", action="store_true", help="列出已配置产品")
    parser.add_argument("--product", help="产品名")
    parser.add_argument("--port", help="串口号")
    parser.add_argument("--firmware", action="store_true", help="固件更新")
    parser.add_argument("--script", metavar="FILE", help="脚本下发，指定单个 .py 文件")
    parser.add_argument("--slot", type=int, default=0, help="目标槽位（默认 0；NEW-AI 0-19，其余 0-9）")
    args = parser.parse_args(argv)

    config = Path(args.config) if args.config else base_dir() / "products.yaml"
    profiles = load_profiles(config)

    if args.list:
        for name, p in profiles.items():
            print(f"{name}: {p.protocol}, folders={p.folders}")
        return 0

    if not args.product:
        parser.error("--product 必填（或用 --list 查看）")
    if args.product not in profiles:
        parser.error(f"unknown product '{args.product}'; choose from {list(profiles)}")
    profile = profiles[args.product]

    if not (args.firmware or args.script):
        parser.error("需指定 --firmware 或 --script FILE")

    t = SerialTransport()
    dep = DeviceDeployer(t)
    dep.log.connect(lambda s: print(s))
    dep.progress.connect(lambda d, n: print(f"\r{d}/{n}", end="", flush=True))
    dep.state_changed.connect(lambda s: print(f"\n[{s}]"))
    try:
        t.open(args.port, profile.baud)  # open() 内构造真实 serial 并拉低 DTR/RTS
        t.start_rx()
        if args.firmware:
            dep.update_firmware(profile, args.port)
        else:
            dep.deploy_script(profile, args.port, Path(args.script), slot=args.slot)
        print("\n完成")
        return 0
    except Exception as e:
        print(f"\n失败: {e}", file=sys.stderr)
        return 1
    finally:
        t.close()


if __name__ == "__main__":
    sys.exit(main())
