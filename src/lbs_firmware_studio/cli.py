"""无头 CLI：阶段 1a 的可运行交付物，证明后端可脱离 GUI 工作。"""
from __future__ import annotations
import sys, argparse
from pathlib import Path
from .backend.profile import load_profiles
from .backend.deployer import DeviceDeployer
from .backend.serial_transport import SerialTransport


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lbs-firmware")
    parser.add_argument("--config", default="products.yaml")
    parser.add_argument("--list", action="store_true", help="列出已配置产品")
    parser.add_argument("--product", help="产品名")
    parser.add_argument("--port", help="串口号")
    parser.add_argument("--firmware", action="store_true", help="固件更新")
    parser.add_argument("--scripts", metavar="DIR", help="脚本下发，指定 .py 文件夹")
    args = parser.parse_args(argv)

    profiles = load_profiles(Path(args.config))

    if args.list:
        for name, p in profiles.items():
            print(f"{name}: {p.protocol}, folders={p.folders}")
        return 0

    if not args.product:
        parser.error("--product 必填（或用 --list 查看）")
    profile = profiles[args.product]

    if not (args.firmware or args.scripts):
        parser.error("需指定 --firmware 或 --scripts DIR")

    import serial  # 真机模式才需要
    t = SerialTransport(serial.Serial(args.port, profile.baud, timeout=0.1))
    t.start_rx()
    dep = DeviceDeployer(t)
    dep.log.connect(lambda s: print(s))
    dep.progress.connect(lambda d, n: print(f"\r{d}/{n}", end="", flush=True))
    dep.state_changed.connect(lambda s: print(f"\n[{s}]"))
    try:
        if args.firmware:
            dep.update_firmware(profile, args.port)
        else:
            dep.deploy_scripts(profile, args.port, Path(args.scripts))
        print("\n完成")
        return 0
    except Exception as e:
        print(f"\n失败: {e}", file=sys.stderr)
        return 1
    finally:
        t.close()


if __name__ == "__main__":
    sys.exit(main())
