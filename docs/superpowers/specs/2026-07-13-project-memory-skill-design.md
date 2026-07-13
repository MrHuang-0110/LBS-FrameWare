# project-memory Skill · 设计规格

> 状态：设计已批准，待写实施计划。日期：2026-07-13。

## 目标

做一个名为 **`project-memory`** 的全局 skill，把 MCP `@modelcontextprotocol/server-memory` 变成**每个项目独立、跟随 git 共享**的知识图谱记忆系统，取代当前 Claude Code 自带的文件式 `.md` 记忆。核心能力：

1. **依赖预检与自动安装** — 调用 MCP 前确保 Node/npx 与 memory 包就绪，缺则主动装。
2. **一次性初始化（幂等、可移植）** — 任意项目首次使用时自动配好项目级 `.mcp.json`、注入 `CLAUDE.md` 开场规则、建目录、配 `.gitattributes`。
3. **迁移旧记忆** — 把项目对应的文件式 `.md` 记忆迁进知识图谱，校验通过后删除旧文件。
4. **日常读写与整理** — 开场自动读；遇坑/重要决策/进度节点按规则写入；去重合并。

## 关键决策（已与用户确认）

| 议题 | 决策 |
|------|------|
| 记忆文件位置 | 项目目录下 `.memory/memory.jsonl` |
| 是否纳入 git | **纳入，团队共享** |
| 路径可移植方案 | **方案 A**：`.mcp.json` 用 `${CLAUDE_PROJECT_DIR}` 展开；实测不支持则回退方案 B（gitignore + 本机绝对路径 + 模板） |
| 写入触发方式 | **skill 规则驱动**（我在对话中判断语义后主动调 MCP） |
| 开场自动读 | **CLAUDE.md 注入开场规则**（每会话自动注入上下文，驱动我先 `read_graph`） |
| skill 职责范围 | **含一次性 setup + 日常读写** |
| 旧文件式记忆 | **迁移进知识图谱，校验通过后删除** |
| 依赖缺失 | **主动安装**；运行时调用失败且因缺失也自愈重装 |
| 可移植 | 放到任何项目都能自动完成预检→初始化→迁移 |

## 架构 · 三个部件

```
┌─ project-memory (skill, 全局安装于 ~/.claude/skills/) ─┐
│  SKILL.md          触发规则 + 工作流总纲                │
│  references/                                           │
│    setup.md        预检/初始化/迁移步骤                 │
│    schema.md       实体/关系/观察 命名规范              │
│    workflows.md    读/写/整理 操作细则                  │
└─────────────────────────────────────────────────────────┘
        │ setup 时生成 ↓                     │ 运行时调用 ↓
┌─ 项目内（跟 git 走）───────────────┐   ┌─ MCP server-memory ─┐
│  .mcp.json   项目级 memory 服务      │   │  mcp__memory__* 9 工具│
│    MEMORY_FILE_PATH=${CLAUDE_PROJECT │──▶└──────────────────────┘
│    _DIR}/.memory/memory.jsonl        │
│  .memory/memory.jsonl  记忆数据       │
│  .gitattributes  memory.jsonl merge=union │
│  CLAUDE.md   开场读取规则（标记块注入）│
└──────────────────────────────────────┘
```

**数据流**：
- **开场读**：新会话 → CLAUDE.md 规则驱动 → `mcp__memory__read_graph` → 记忆进上下文。
- **写入**：对话命中触发条件 → `create_entities` / `add_observations` / `create_relations`。
- **服务隔离**：每项目各自 `.mcp.json` 把 `MEMORY_FILE_PATH` 指向本项目 `.memory/memory.jsonl`，天然按项目隔离且路径可移植。

## Setup 流程（幂等，每步先查后写，可重复运行）

**Step 0 — 依赖预检与自动安装**
1. 查 `node`/`npx`：无则报告并给 Windows 安装指引；无法自动装系统级 Node 时明确告知用户手动装，不硬闯。
2. 查 `@modelcontextprotocol/server-memory` 是否在 npx 缓存就绪：没有则主动 `npx -y @modelcontextprotocol/server-memory`（`-y` 自动下载）或 `npm i -g` 拉取并确认成功。
3. 冒烟测试：调 `mcp__memory__read_graph`，能返回（哪怕空图谱）即通路正常；报错则停在此步并报告。

**Step 1 — 实测变量展开**：确认 `.mcp.json` 支持 `${CLAUDE_PROJECT_DIR}`；不支持回退方案 B 并告知。

**Step 2 — 写/合并项目级 `.mcp.json`**：加 `memory` 服务，`MEMORY_FILE_PATH=${CLAUDE_PROJECT_DIR}/.memory/memory.jsonl`；已有 `.mcp.json` 则合并、不覆盖其他服务。

**Step 3 — 建 `.memory/` 目录 + 空 `memory.jsonl`**。

**Step 4 — 迁移旧文件式记忆**：
- 探测 `~/.claude/projects/<编码名>/memory/` 下所有 `.md`（除 `MEMORY.md` 索引）。`<编码名>` = 项目绝对路径把 `:`/`\`/`/` 替换为 `-` 后的结果（如 `e:\LBS-FramWare` → `e--LBS-FramWare`）。
- 逐条解析为图谱：frontmatter `name`→实体名、`type`→实体类型、正文→observations、`[[link]]`→relation。
- 调 `create_entities`/`add_observations`/`create_relations` 写入。
- **校验**：`read_graph` 回读，逐条确认条数与内容对得上。
- **校验通过后删除**旧 `.md` 与 `MEMORY.md`；不通过则保留并报告差异，不删。
- 新项目无旧 `.md` 时本步自动跳过。

**Step 5 — 向项目 `CLAUDE.md` 注入开场规则**，带幂等标记块：
```
<!-- project-memory:start -->
会话开始时，先调用 mcp__memory__read_graph 读取本项目记忆再开始工作。
<!-- project-memory:end -->
```

**Step 6 — 配 `.gitattributes`**：`.memory/memory.jsonl merge=union`（JSONL 按行合并，缓解多人写入冲突）。

**Step 7 — 提示重启会话**：`.mcp.json` 变更需重启会话才生效。

## 数据模型（schema）

- **Entity 类型**：`pitfall`（坑）、`decision`（重要决策/数据）、`progress`（进度节点）、`component`（模块）、`convention`（约定）。
- **Observation**：挂实体上的具体事实，带日期前缀，如 `2026-07-13: xxx`。
- **Relation**：如 `pitfall`—出现于→`component`；`decision`—影响→`component`。

**三类触发写入场景**：
| 场景 | 信号 | 记成 |
|------|------|------|
| 坑 | 报错根因、"原来是因为…"、反直觉行为 | `pitfall` 实体 + observation |
| 重要数据/决策 | 选型拍板、关键参数、架构约定 | `decision`/`convention` 实体 |
| 项目进度 | 阶段完成、分支合并、里程碑 | `progress` 实体，更新而非堆叠 |

## 运行时规则（写进 SKILL.md）

- **开场读**：由 CLAUDE.md 注入规则驱动，会话开始先 `read_graph`。
- **写入**：命中三类触发场景即主动调 MCP 写入；进度类更新既有实体而非堆叠新条目。
- **自愈**：日常调用 `mcp__memory__*` 若因服务/包缺失失败，回到 Step 0 安装流程修复后重试，不直接放弃。
- **不自动 commit**：记忆数据文件的提交交给用户正常 git 流程。

## 边界与非目标（YAGNI）

- **单一记忆系统**：迁移后只用 MCP 知识图谱；旧文件式 `.md` 校验通过即删。
- 不做 UI、定时任务、跨项目全局记忆聚合。
- 删除有前置条件：仅 `read_graph` 回读校验通过后才删旧文件。

## 技术约束

- Windows；解释器命令用 `python`（非 python3）；`npx`/`npm` 用于安装 MCP 包。
- MCP memory 版本参考 `2026.7.4`：存储为 JSONL（每行一 entity/relation），全量读写。
- `MEMORY_FILE_PATH` 仅认绝对路径（源码中相对路径相对 npm 包目录），故靠 `${CLAUDE_PROJECT_DIR}` 展开取得项目绝对路径。
