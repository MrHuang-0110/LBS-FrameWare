"""PyInstaller 打包入口垫片：以绝对导入调用包内 main()。
不能直接把 gui/app.py 当顶层脚本打包——它用相对导入(from . / from ..)，
冻结后作为 __main__ 运行没有父包，会抛 'attempted relative import with no known parent package'。
这里作为顶层脚本、绝对导入包，令 app.py 作为包成员被导入，相对导入成立。"""
from __future__ import annotations
import sys

from lbs_firmware_studio.gui.app import main

if __name__ == "__main__":
    sys.exit(main())
