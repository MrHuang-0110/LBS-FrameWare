"""列出所有串口的完整信息，用于设计「按设备名自动识别」。只读，无副作用。

用法：
  python scripts/list_ports.py

三款设备（NEW-AI/SPARK-AI/NEXT-AI）能插几个插几个，跑一次即可。
把输出整段贴回来，我据此确定「LBS Serial」出现在哪个字段。
"""
from __future__ import annotations
import serial.tools.list_ports


def main() -> int:
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("未发现任何串口。请确认设备已插入。")
        return 0
    print(f"发现 {len(ports)} 个串口：\n")
    for i, p in enumerate(ports, 1):
        print(f"--- 端口 {i} ---")
        print(f"  device       (COM号)     : {p.device}")
        print(f"  name                     : {p.name}")
        print(f"  description  (描述)       : {p.description}")
        print(f"  hwid         (硬件ID)     : {p.hwid}")
        print(f"  manufacturer (厂商)       : {p.manufacturer}")
        print(f"  product      (产品)       : {p.product}")
        print(f"  vid:pid                  : {p.vid}:{p.pid}"
              if p.vid is not None else "  vid:pid                  : None")
        print(f"  serial_number            : {p.serial_number}")
        print(f"  interface                : {p.interface}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
