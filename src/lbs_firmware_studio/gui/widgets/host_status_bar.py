"""底部主机状态栏：按产品 status_fields(label + json 点路径) 显示。
取不到显示 '--'；mem 这类 dict 值组合成 yaw/pitch/roll。"""
from __future__ import annotations
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel
from .. import theme
from ..pages.monitor_profiles import get_by_path


class HostStatusBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 顶栏 48px BG_BAR 内不使用全局 QFrame#card（BG_SIDEBAR 色块+大圆角）样式，
        # 独立 objectName 走 QFrame#hostBar（透明背景/无边框），前景由 QLabel 令牌控制（M1）
        self.setObjectName("hostBar")
        self._fields: list[tuple[str, str]] = []
        self._value_labels: dict[str, QLabel] = {}
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(theme.SPACE_MD, theme.SPACE_SM, theme.SPACE_MD, theme.SPACE_SM)
        self._lay.setSpacing(theme.SPACE_LG)

    def set_fields(self, status_fields: list[tuple[str, str]]) -> None:
        # 清空旧字段
        while self._lay.count():
            item = self._lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._fields = list(status_fields)
        self._value_labels = {}
        for label, _path in self._fields:
            cap = QLabel(f"{label}:")
            cap.setStyleSheet(f"color:{theme.TEXT_SECONDARY}; background:transparent;")
            val = QLabel("--")
            # E5：值区等宽字体防数字抖动；颜色走令牌
            val.setStyleSheet(
                f"color:{theme.TEXT_PRIMARY}; background:transparent;"
                f" font-family:{theme.MONO_FONT};")
            self._lay.addWidget(cap)
            self._lay.addWidget(val)
            self._value_labels[label] = val
        self._lay.addStretch(1)

    def reset(self) -> None:
        """把所有字段值重置为占位 '--'（断开连接/复位时调用），字段挂载不变。"""
        for label in self._value_labels:
            self._value_labels[label].setText("--")

    def update_from(self, frame: dict) -> None:
        for label, path in self._fields:
            raw = get_by_path(frame, path)
            self._value_labels[label].setText(self._format(raw))

    @staticmethod
    def _format(raw) -> str:
        if raw is None:
            return "--"
        if isinstance(raw, dict):
            # 如 mem={yaw,pitch,roll} -> 组合
            return "/".join(str(v) for v in raw.values())
        return str(raw)

    # --- 测试访问器 ---
    def field_text(self, label: str) -> str:
        return self._value_labels[label].text() if label in self._value_labels else ""
