"""GUI 入口 + AppController（启动窗 ↔ 主窗切换，可单测）。"""
from __future__ import annotations
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from . import theme
from .startup_window import StartupWindow
from .main_window import MainWindow
from ..backend.profile import load_profiles
from ..paths import base_dir


class AppController:
    def __init__(self, profiles: dict, raw_config: dict, config_path: Path):
        self._profiles = profiles
        self._raw = raw_config
        self._path = Path(config_path)
        self._startup = None
        self._main = None
        self._kind = None

    def show_startup(self) -> None:
        if self._main is not None:
            self._main.close()
            self._main = None
        self._startup = StartupWindow(self._profiles)
        self._startup.product_selected.connect(self.on_product_selected)
        self._startup.show()
        self._kind = "startup"

    def on_product_selected(self, name: str) -> None:
        if self._startup is not None:
            self._startup.close()
            self._startup = None
        self._main = MainWindow(self._profiles[name], self._raw, self._path)
        self._main.switch_product_requested.connect(self.on_switch_product)
        self._main.show()
        self._kind = "main"

    def on_switch_product(self) -> None:
        self.show_startup()

    def current_window_kind(self) -> str:
        return self._kind


def main(argv=None) -> int:
    app = QApplication.instance() or QApplication(sys.argv if argv is None else argv)
    app.setStyleSheet(theme.app_qss())
    config_path = base_dir() / "products.yaml"
    import yaml
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    profiles = load_profiles(config_path)
    ctl = AppController(profiles, raw, config_path)
    ctl.show_startup()
    app._ctl = ctl  # 防止被 GC
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
