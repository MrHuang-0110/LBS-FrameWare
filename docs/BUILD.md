# 构建与分发

## 构建 onedir 可分发文件夹

1. 安装构建依赖：`pip install -e .[build]`
2. 运行：`python scripts/build.py`
3. 产物在 `dist/LBS-Firmware-Studio/`：
   - `LBS-Firmware-Studio.exe`（双击运行）
   - `_internal/`（依赖，勿删）
   - `products.yaml`、`tools/`、`products/<产品>/templates|write`
   - **不含 fwlib 固件库**——由用户自选目录

整个 `dist/LBS-Firmware-Studio/` 文件夹即可压缩分发。

## 首次使用：设置固件目录

分发包不带固件库。用户首次要用「固件更新」前：

1. 启动后进入 **设置** 页。
2. 在「固件目录（每产品）」区，为对应产品点 **浏览…** 选择本地 fwlib 目录。
3. 点 **保存**（写回 products.yaml），提示「已保存，重启后生效」。
4. 重启程序，固件目录生效。

脚本编辑/数据监控功能无需固件目录即可使用。
