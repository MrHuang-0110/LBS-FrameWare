"""固件更新页：复用 FirmwareUpdateSection（固件源 + 开始按钮 + 进度条 + 单行当前进度）。

布局重构 v3 Task 2：固件更新区抽为 widgets/firmware_update_section.py 独立组件，
本页直接继承复用（接口/测试访问器与布局语义保持）。Task 3 若移除本页，固件更新
逻辑由浮窗内 FirmwareUpdateSection 承担。
"""
from __future__ import annotations

from .. import theme
from ..widgets.firmware_update_section import FirmwareUpdateSection


class FirmwarePage(FirmwareUpdateSection):
    """固件更新页：页面级 margins + 底部留白，其余全部继承固件更新区组件。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = self.layout()
        lay.setContentsMargins(theme.SPACE_LG, theme.SPACE_LG,
                               theme.SPACE_LG, theme.SPACE_LG)
        lay.setSpacing(theme.SPACE_MD)
        lay.addStretch(1)
