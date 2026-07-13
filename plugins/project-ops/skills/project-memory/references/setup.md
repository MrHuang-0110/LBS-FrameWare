> Note: `<project-memory skill scripts dir>` = the `scripts/` folder next to this skill's SKILL.md.
> When invoking, use the actual path to this skill inside the installed plugin
> (e.g. `plugins/project-ops/skills/project-memory/scripts/` in the source repo, or the
> installed plugin cache path). Do not use the old `~/.claude/skills/project-memory/...` path.

# Setup：初始化项目记忆系统（幂等，先查后写）

分两阶段：**重启前 = 纯配置**（写文件，不调用任何 MCP），**重启后验证 = 通路冒烟 + 变量展开 + 迁移写入 + 校验 + 删旧**。
memory MCP 服务在 `.mcp.json` 写入并重启会话后才存在，故所有 `mcp__memory__*` 调用与 `${CLAUDE_PROJECT_DIR}` 实测都放到重启后阶段。

# ===== 重启前阶段（纯配置，不调 MCP）=====

## Step 0 — 依赖预检与自动安装
1. 查 node/npx：`node -v` 与 `npx -v`。任一失败 → 报告需要 Node.js(LTS)，给 Windows 安装指引；不硬闯，不自动装系统级 Node。
2. 查 memory 包缓存：探测 `~/AppData/Local/npm-cache/_npx/*/node_modules/@modelcontextprotocol/server-memory` 是否存在。
   - 存在 → 跳过。
   - 不存在 → 主动预热安装：`npx -y @modelcontextprotocol/server-memory --help` 或 `npm i -g @modelcontextprotocol/server-memory`，确认拉取成功。

## Step 1 — 写/合并项目级 .mcp.json
`MEMORY_FILE_PATH` 直接写**当前项目的绝对路径** `<项目绝对路径>/.memory/memory.jsonl`（用正斜杠）。
> 注：曾设计用 `${CLAUDE_PROJECT_DIR}` 变量以求可移植，但实测该变量在 MCP 启动环境**不展开**，server-memory 只认绝对路径，未展开变量会被拼到 npm 包目录导致读不到记忆。故一律写当前项目绝对路径；换机器/移动项目时由开场「路径自愈」（`scripts/check_memory_path.py`）自动纠正，无需手改。

目标片段（把 `<项目绝对路径>` 替换为实际路径，如 `e:/LBS-FramWare`）：
```json
{
  "mcpServers": {
    "memory": {
      "type": "stdio",
      "command": "cmd",
      "args": ["/c","npx","-y","@modelcontextprotocol/server-memory"],
      "env": { "MEMORY_FILE_PATH": "<项目绝对路径>/.memory/memory.jsonl" }
    }
  }
}
```
- 若已有 .mcp.json：读入 → 合并 mcpServers.memory（不动其他服务）→ 写回。
- 若无：直接创建。
- 团队共享可选项：若担心绝对路径写死影响他人 clone，可把 .mcp.json 加入 .gitignore；但**不必**——开场路径自愈会在每台机器上自动改成本机当前项目绝对路径。记忆数据 memory.jsonl 始终进 git 共享。

## Step 2 — 建 .memory/ 目录与空 memory.jsonl
mkdir -p .memory && 若无 memory.jsonl 则创建空文件。

## Step 3 — 向项目 CLAUDE.md 注入开场规则
在项目根 CLAUDE.md（无则创建）插入幂等标记块；已存在标记块则替换其内容：
<!-- project-memory:start -->
会话开始时，先调用 mcp__memory__read_graph 读取本项目记忆再开始工作。若因 MCP 服务/包缺失失败，按 project-memory skill 的 setup Step 0 自愈安装后重试。
<!-- project-memory:end -->

## Step 4 — 配 .gitattributes
确保含一行（无则追加）：`.memory/memory.jsonl merge=union`

## Step 5 — 提示重启
告知用户：.mcp.json 变更需重启 Claude Code 会话才生效。重启后再执行下方「重启后验证」阶段。记忆数据文件由用户自行 git 提交（skill 不自动 commit）。

# ===== 重启后验证阶段（会话重启后执行，此时 MCP 已就绪）=====

## Step 6 — 通路冒烟测试
调用 `mcp__memory__read_graph`。能返回（哪怕空图谱 `{entities:[],relations:[]}`）即通路正常；报错则停在此步并报告（提示确认已重启会话让 .mcp.json 生效、或回到 Step 0 自愈）。

## Step 7 — 路径自愈复核
用 `python <project-memory skill scripts dir>/check_memory_path.py "<项目绝对路径>"` 核对 `.mcp.json` 的 `MEMORY_FILE_PATH` 已是当前项目绝对路径：
- 输出 `OK` → 通过。
- 输出 `NEEDS-FIX` → 用 `check_memory_path.py "<项目绝对路径>" --fix "<.mcp.json 路径>"` 自动改写为当前项目绝对路径，再次重启会话并回到 Step 6 复验。
（server-memory 只认绝对路径；此步确保记忆文件确实落在项目 `.memory/` 下，而非 npm 包目录。）

## Step 8 — 迁移旧文件式记忆（写入 MCP + 校验 + 删旧）
1. 定位旧目录：`python <project-memory skill scripts dir>/encode_project_path.py "<项目绝对路径>"` → `<编码名>`；旧目录 = `~/.claude/projects/<编码名>/memory/`。
2. 若目录不存在或无 .md（除 MEMORY.md）→ 跳过本步（新项目情形）。
3. 读取每个 .md（排除 MEMORY.md），用 `scripts/migrate_md_to_graph.py` 的 parse_md_file + build_graph 得到 {entities, relations}。构造 build_graph 的入参时，为每个 file dict 带上 `filename`（原 .md 文件名），使空 name 能回退到文件名 stem。
   - **空名安全阀**：若某实体解析后 name 为空**且**无法从 filename 补全（build_graph 抛 `ValueError`），立即**中止迁移**、**不删除任何旧文件**，并向用户报告是哪个文件、需人工补 name 后重试。防止多个空名实体互相覆盖导致数据丢失。
4. 写入 MCP：create_entities → create_relations（对 relations 中 to 端不存在的实体，MCP 允许悬挂关系，保留）。逐实体 add_observations 若已存在同名实体。
   - **observation 前缀例外**：迁移的历史正文作为**单条 observation 整体导入，不加 `YYYY-MM-DD:` 日期前缀**（历史导入对 schema.md 逐条格式的例外；此后新增 observation 仍按 `YYYY-MM-DD:` 格式）。
5. 校验：调 read_graph 回读，确认迁移的每个实体名都在图中、observation 内容一致、relations 条数吻合。
6. 校验通过 → 删除旧 .md 与 MEMORY.md（及空的 memory 目录）。校验不通过 → 保留旧文件，报告缺失/差异明细，不删。

## Step 9 — 生成轻量索引 index.md
跑 `python <project-memory skill scripts dir>/build_index.py "<项目>/.memory/memory.jsonl" "<项目>/.memory/index.md"`，生成两层记忆的索引层。此后每次开场读它、写入/整理后重建它（见 references/workflows.md）。新项目（空图）也会生成含「（暂无记忆）」的占位索引。
