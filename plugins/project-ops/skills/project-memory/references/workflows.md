> Note: `<project-memory skill scripts dir>` = the `scripts/` folder next to this skill's SKILL.md.
> When invoking, use the actual path to this skill inside the installed plugin
> (e.g. `plugins/project-ops/skills/project-memory/scripts/` in the source repo, or the
> installed plugin cache path). Do not use the old `~/.claude/skills/project-memory/...` path.

# 运行时工作流

## 开场读取（两层：先读索引，正文按需）
- **第 0 步 · 路径自愈**：核对 `.mcp.json` 里 memory 服务的 `MEMORY_FILE_PATH` 是否指向**当前项目**的 `.memory/memory.jsonl`。
  - 检查方法：跑 `python <project-memory skill scripts dir>/check_memory_path.py <当前项目绝对路径>`。
  - 若不一致（换机器 / 项目被移动 / `${CLAUDE_PROJECT_DIR}` 等未展开变量 / 相对路径）→ 用 `--fix <.mcp.json 路径>` 自动改写为当前项目绝对路径，并提示用户「路径已自愈，需重启会话生效」。
  - **为何必须绝对路径**：server-memory 只认绝对路径，相对/未展开变量会被拼到 npm 包目录，导致读不到项目记忆。
- **第 1 步 · 重建并读索引（不读全量正文）**：
  1. 重建索引保证新鲜：`python <project-memory skill scripts dir>/build_index.py "<项目>/.memory/memory.jsonl" "<项目>/.memory/index.md"`。
  2. 读 `.memory/index.md`（轻量：每条一行 `名字 (类型) — 一句话`）。由此掌握「本项目有哪些记忆、各属什么类、大概讲啥」。
  3. **不再开场 `read_graph` 全量**——避免长正文占满上下文。
  - index.md 为空 / 缺失（新项目或空图）→ 无记忆，正常开始。
- 调用失败且因 MCP 服务/包缺失 → 触发 setup.md Step 0 自愈，装好后重试；仍失败则告知用户并降级继续（不阻塞工作）。

## 按需读正文（对话中触发）
索引让我知道「有什么」，正文在真正需要时才读，只进相关的那几条：
- 用户问进度 → `open_nodes(["project-progress"])`（或索引里 progress 类的名字）读该条正文。
- 遇到/排查坑 → `search_nodes("<关键词>")` 或 `open_nodes` 取对应 pitfall/operation 正文。
- 需要某决策/约定 → 按索引中的 name `open_nodes` 精确取。
- 只有确需通览时才 `read_graph` 全量（如「整理」）。
- **原则**：先看索引判断相关性，再按名字/关键词取正文；索引里没有的就不去读。

## 写入（命中 schema.md 四类触发场景时主动执行）
1. 先 `search_nodes` 查是否已有相关实体，避免重复建实体。
2. 新主题 → `create_entities`（按 schema 选 entityType，name 用 kebab-case）。
3. 已有实体新增事实 → `add_observations`（带 YYYY-MM-DD 前缀）。
4. 有跨实体关系 → `create_relations`。
5. 进度类：更新既有 progress 实体，不堆叠新实体。
6. 重要操作（尤其 git 回退/revert/reset）：追加到 `git-operations`（或对应 operation）实体，记改了什么、为什么、影响、如何复原、当前 HEAD。见 schema.md「git 回退专项」。
7. **写入后重建索引**：跑 `build_index.py` 重新生成 `.memory/index.md`，保证索引与正文同步。
8. 不自动 git commit 记忆文件。

## 整理（用户要求或图谱明显冗余时）
- `read_graph` 通览 → 找重复/过时实体与 observation。
- 用 `delete_observations` 删过时事实、`delete_entities` 删废弃实体（连带其关系）。
- 合并同义实体：把 observation 迁到保留实体后删除多余实体。
- **整理后重建索引**：跑 `build_index.py` 更新 `.memory/index.md`。

## 运行时自愈（任何 mcp__memory__* 调用失败）
- 若错误提示服务未连/包缺失 → 执行 setup.md Step 0（预检+安装）→ 重试一次。
- 若因 .mcp.json 刚变更未生效 → 提示用户重启会话。
