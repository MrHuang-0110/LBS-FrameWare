"""设置页：编辑编译器路径 + 每产品固件目录，保存写回 products.yaml。"""
from __future__ import annotations
from pathlib import Path
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QFileDialog, QGroupBox)
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

        # 每产品固件目录行
        self._fw_edits: dict[str, QLineEdit] = {}
        fw_group = QGroupBox("固件目录（每产品）")
        fw_lay = QVBoxLayout(fw_group)
        for name, cfg in raw_config.get("products", {}).items():
            edit = QLineEdit(str(cfg.get("firmware_dir", "")))
            edit.setReadOnly(True)
            btn = QPushButton("浏览…")
            btn.clicked.connect(lambda _=False, n=name: self._browse_firmware(n))
            row = QHBoxLayout()
            row.addWidget(QLabel(name)); row.addWidget(edit, 1); row.addWidget(btn)
            fw_lay.addLayout(row)
            self._fw_edits[name] = edit

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("设置"))
        row = QHBoxLayout(); row.addWidget(QLabel("编译器路径:"))
        row.addWidget(self._compiler, 1); row.addWidget(browse)
        lay.addLayout(row)
        lay.addWidget(fw_group)
        lay.addWidget(save_btn)
        lay.addWidget(self._status)
        lay.addStretch()

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择编译器", "", "可执行文件 (*.exe);;所有文件 (*)")
        if path:
            self._compiler.setText(path)

    def _browse_firmware(self, name: str) -> None:
        path = QFileDialog.getExistingDirectory(self, f"选择 {name} 固件目录", "")
        if path:
            self._fw_edits[name].setText(path)

    def set_compiler_path(self, path: str) -> None:
        self._compiler.setText(path)

    def compiler_path_text(self) -> str:
        return self._compiler.text()

    # --- 固件目录访问器 ---
    def product_rows(self) -> list[str]:
        return list(self._fw_edits.keys())

    def firmware_dir_text(self, name: str) -> str:
        return self._fw_edits[name].text()

    def set_firmware_dir(self, name: str, path: str) -> None:
        self._fw_edits[name].setText(path)

    def save(self) -> None:
        self._raw["compiler_path"] = self._compiler.text()
        for name, edit in self._fw_edits.items():
            self._raw["products"][name]["firmware_dir"] = edit.text()
        save_profiles(self._raw, self._path)
        self._status.setText("已保存，重启后生效")
