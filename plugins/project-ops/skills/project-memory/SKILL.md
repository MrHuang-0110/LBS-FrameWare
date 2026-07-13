---
name: project-memory
description: Use when starting a session in a project, or when hitting a pitfall / making a key decision / reaching a progress milestone — manages per-project knowledge-graph memory via MCP server-memory
---

# Project Memory

用 MCP `@modelcontextprotocol/server-memory` 管理**每项目独立、跟随 git 共享**的知识图谱记忆。记忆存于项目内 `.memory/memory.jsonl`。

## 何时触发
- **会话开始**：读取本项目记忆（见 references/workflows.md 开场读取）。
- **命中写入场景**：踩坑 / 重要决策或数据 / 进度节点 / 重要操作（git 回退等）（见 references/schema.md 四类触发）。
- **首次在某项目使用 / 记忆系统未初始化**：跑一次性 setup（见 references/setup.md）。
- **用户要求整理记忆**：见 references/workflows.md 整理。

## 首次使用判定
项目根**无** `.mcp.json` 的 memory 服务，或**无** `.memory/memory.jsonl` → 视为未初始化，执行 references/setup.md 的 Step 0–7（含依赖预检自动安装、旧 .md 记忆迁移并删除、CLAUDE.md 开场规则注入）。setup 幂等，可安全重跑。

## 运行时铁律
- **开场先做路径自愈**：核对 `.mcp.json` 的 `MEMORY_FILE_PATH` 指向当前项目绝对路径（用 `scripts/check_memory_path.py`，不一致则 `--fix` 自动改写并提示重启）。
- **两层读取**：开场先跑 `scripts/build_index.py` 重建并读 `.memory/index.md`（轻量索引：名字/类型/摘要），**不开场 read_graph 全量**；正文在需要时按名字/关键词用 `open_nodes`/`search_nodes` 取。见 references/workflows.md。
- 命中触发场景主动写入；**写入/整理后重建 index.md**；调用失败按 workflows.md 自愈。
- 写入前先 `search_nodes` 去重；进度类更新既有实体不堆叠。
- 实体类型/命名/observation 格式严格按 references/schema.md。
- 不自动 git commit 记忆文件。

## 参考
- 初始化/预检/迁移：references/setup.md
- 数据模型/触发判定：references/schema.md
- 读写整理/自愈：references/workflows.md
- 辅助脚本：scripts/encode_project_path.py、scripts/migrate_md_to_graph.py、scripts/check_memory_path.py、scripts/build_index.py
- 辅助脚本：scripts/encode_project_path.py、scripts/migrate_md_to_graph.py、scripts/check_memory_path.py
