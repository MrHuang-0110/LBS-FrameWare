"""GUI 入口 + AppController（启动直入主窗，可单测）。"""
from __future__ import annotations
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from . import theme
from .main_window import MainWindow
from ..backend.profile import load_profiles
from ..paths import base_dir


class AppController:
    """启动即打开主窗（默认产品 NEW-AI）；不再有启动窗/占位页流转。"""

    def __init__(self, profiles: dict, raw_config: dict, config_path: Path):
        self._profiles = profiles
        self._raw = raw_config
        self._path = Path(config_path)
        self._main = None

    def launch(self, default_product: str = "NEW-AI") -> None:
        """直入主窗：以默认产品构造 MainWindow（传入全部产品供顶栏切换）并 show。"""
        self._main = MainWindow(self._profiles[default_product], self._raw, self._path,
                                profiles=self._profiles)
        self._main.show()

    def current_window_kind(self) -> str | None:
        """测试兼容访问器：主窗打开时返回 'main'，否则 None（无 startup 态）。"""
        return "main" if self._main is not None else None


def main(argv=None) -> int:
    app = QApplication.instance() or QApplication(sys.argv if argv is None else argv)
    app.setStyleSheet(theme.app_qss())
    config_path = base_dir() / "products.yaml"
    import yaml
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    profiles = load_profiles(config_path)
    ctl = AppController(profiles, raw, config_path)
    ctl.launch("NEW-AI")
    app._ctl = ctl  # 防止被 GC
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
