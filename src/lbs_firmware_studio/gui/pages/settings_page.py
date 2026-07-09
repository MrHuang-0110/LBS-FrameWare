"""设置页：编辑编译器路径等，保存写回 products.yaml。"""
from __future__ import annotations
from pathlib import Path
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QFileDialog)
from ...backend.profile import save_profiles


class SettingsPage(QWidget):
    def __init__(self, raw_config: dict, config_path: Path, parent=None):
        super().__init__(parent)
        self._raw = raw_config
        self._path = Path(config_path)
        self._compiler = QLineEdit(str(raw_config.get("compiler_path", "")))
        browse = QPushButton("浏览"); browse.clicked.connect(self._browse)
        self._status = QLabel("")
        save_btn = QPushButton("保存"); save_btn.setObjectName("primary")
        save_btn.clicked.connect(self.save)

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("设置"))
        row = QHBoxLayout(); row.addWidget(QLabel("编译器路径:"))
        row.addWidget(self._compiler, 1); row.addWidget(browse)
        lay.addLayout(row)
        lay.addWidget(save_btn)
        lay.addWidget(self._status)
        lay.addStretch()

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择编译器", "", "可执行文件 (*.exe);;所有文件 (*)")
        if path:
            self._compiler.setText(path)

    def set_compiler_path(self, path: str) -> None:
        self._compiler.setText(path)

    def compiler_path_text(self) -> str:
        return self._compiler.text()

    def save(self) -> None:
        self._raw["compiler_path"] = self._compiler.text()
        save_profiles(self._raw, self._path)
        self._status.setText("已保存，重启后生效")
