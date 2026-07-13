# project-memory Skill 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个全局安装于 `~/.claude/skills/project-memory/` 的 skill，把 MCP `@modelcontextprotocol/server-memory` 变成每项目独立、跟随 git 共享的知识图谱记忆系统，并能自动完成依赖预检→初始化→迁移旧文件式记忆。

**Architecture:** 产出物是一组 markdown 指令文件（`SKILL.md` + `references/*.md`）加两个可复用的辅助脚本（路径编码、旧 `.md`→图谱解析）。skill 本体不含运行时服务；运行时靠 MCP `mcp__memory__*` 工具 + 项目内 `.mcp.json`/`CLAUDE.md`/`.memory/` 生成物协作。可脚本化的部分（依赖探测、路径编码、迁移解析）用真实 python/bash 做 TDD；纯行为指令用可操作的验收检查（文件存在 + 关键内容 grep）验证。

**Tech Stack:** Markdown（skill 指令）、Python 3.13（辅助脚本与其 pytest 测试，解释器用 `python`）、Node/npx（MCP 包，实测 node v22.19.0 / npx 11.6.0 已就绪）、MCP `@modelcontextprotocol/server-memory` v2026.7.4（JSONL 存储）。

## Global Constraints

- 平台 Windows；Python 解释器命令用 `python`（非 python3）；运行测试用 `python -m pytest`。
- skill 安装路径：`~/.claude/skills/project-memory/`（全局，对所有项目可用）。即 `C:\Users\24160\.claude\skills\project-memory\`。
- SKILL.md frontmatter 只含 `name` 与 `description` 两字段（对齐现有 skill 惯例）；`name: project-memory`。
- 记忆文件位置：项目内 `.memory/memory.jsonl`；纳入 git、团队共享。
- 路径可移植：`.mcp.json` 用 `${CLAUDE_PROJECT_DIR}/.memory/memory.jsonl`；实测不支持展开则回退方案 B（gitignore + 本机绝对路径 + `.mcp.json.template`）。
- `MEMORY_FILE_PATH` 只认绝对路径（源码中相对路径相对 npm 包目录）。
- 旧文件式记忆位置：`~/.claude/projects/<编码名>/memory/`，`<编码名>` = 项目绝对路径把 `:`/`\`/`/` 替换为 `-`（如 `e:\LBS-FramWare` → `e--LBS-FramWare`）。
- 迁移仅在 `read_graph` 回读校验通过后才删除旧 `.md` 与 `MEMORY.md`；不通过则保留并报告。
- 实体类型：`pitfall`/`decision`/`progress`/`component`/`convention`；observation 带日期前缀 `YYYY-MM-DD: ...`。
- 不自动 commit 记忆数据；不做 UI/定时任务/跨项目聚合。
- CLAUDE.md 注入用幂等标记块 `<!-- project-memory:start -->` … `<!-- project-memory:end -->`。
- 所有 setup 步骤幂等：先查后写，可重复运行。
- 辅助脚本放 `~/.claude/skills/project-memory/scripts/`，其测试放同目录 `scripts/tests/`。

---

## File Structure

```
~/.claude/skills/project-memory/
  SKILL.md                    触发规则 + 工作流总纲（入口）
  references/
    setup.md                  Step 0–7 初始化/预检/迁移完整步骤
    schema.md                 实体/关系/观察 命名规范 + 三类触发场景
    workflows.md              日常读/写/整理 + 运行时自愈规则
  scripts/
    encode_project_path.py    项目绝对路径 → <编码名>（迁移定位用）
    migrate_md_to_graph.py    旧 .md 记忆 → 知识图谱 JSON（供迁移调用）
    tests/
      test_encode_project_path.py
      test_migrate_md_to_graph.py
```

各文件职责：
- **SKILL.md** — skill 入口，含 frontmatter、总纲、何时触发、指向 references 的路由。薄，不放细节。
- **references/setup.md** — 一次性初始化的完整可执行步骤（Step 0–7）。
- **references/schema.md** — 数据模型与写入判定规则。
- **references/workflows.md** — 开场读、写入、整理、运行时自愈。
- **scripts/encode_project_path.py** — 纯函数，路径编码，可测。
- **scripts/migrate_md_to_graph.py** — 纯函数，解析 `.md` 目录为 `{entities, relations}`，可测。

---

## Task 1: 路径编码脚本（TDD）

**Files:**
- Create: `~/.claude/skills/project-memory/scripts/encode_project_path.py`
- Test: `~/.claude/skills/project-memory/scripts/tests/test_encode_project_path.py`

**Interfaces:**
- Consumes: 无。
- Produces: `encode_project_path(abs_path: str) -> str` — 把项目绝对路径的 `:`、`\`、`/` 各替换为单个 `-`，返回编码名（用于定位 `~/.claude/projects/<编码名>/memory/`）。

- [ ] **Step 1: 写失败测试**

创建 `scripts/tests/test_encode_project_path.py`：
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from encode_project_path import encode_project_path


def test_windows_drive_path():
    assert encode_project_path(r"e:\LBS-FramWare") == "e--LBS-FramWare"


def test_windows_nested_path():
    assert encode_project_path(r"C:\Users\24160\proj") == "C--Users-24160-proj"


def test_posix_path():
    assert encode_project_path("/home/x/proj") == "-home-x-proj"


def test_mixed_separators():
    assert encode_project_path("e:/LBS-FramWare") == "e--LBS-FramWare"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd ~/.claude/skills/project-memory && python -m pytest scripts/tests/test_encode_project_path.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'encode_project_path'`

- [ ] **Step 3: 写最小实现**

创建 `scripts/encode_project_path.py`：
```python
"""把项目绝对路径编码为 ~/.claude/projects 下的目录名。"""


def encode_project_path(abs_path: str) -> str:
    result = []
    for ch in abs_path:
        result.append("-" if ch in (":", "\\", "/") else ch)
    return "".join(result)


if __name__ == "__main__":
    import sys
    print(encode_project_path(sys.argv[1]))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd ~/.claude/skills/project-memory && python -m pytest scripts/tests/test_encode_project_path.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
git add ~/.claude/skills/project-memory/scripts/encode_project_path.py ~/.claude/skills/project-memory/scripts/tests/test_encode_project_path.py
git commit -m "feat(project-memory): path encoder for locating legacy memory dir"
```

---

## Task 2: 旧记忆解析脚本（TDD）

**Files:**
- Create: `~/.claude/skills/project-memory/scripts/migrate_md_to_graph.py`
- Test: `~/.claude/skills/project-memory/scripts/tests/test_migrate_md_to_graph.py`

**Interfaces:**
- Consumes: 无（仅标准库；解析 frontmatter 用手写 minimal parser，不依赖 PyYAML）。
- Produces:
  - `parse_md_file(text: str) -> dict` — 输入单个 `.md` 文件全文，返回 `{"name": str, "type": str, "body": str, "links": [str]}`。`name`/`type` 取自 frontmatter（`type` 缺省 `"decision"`）；`links` 为正文中所有 `[[slug]]` 的 slug 列表。
  - `build_graph(files: list[dict]) -> dict` — 输入 `parse_md_file` 结果列表，返回 `{"entities": [...], "relations": [...]}`。每个实体 `{"name","entityType","observations":[body]}`；每个 `[[link]]` 生成一条 `{"from": name, "to": link, "relationType": "relates_to"}`。

- [ ] **Step 1: 写失败测试**

创建 `scripts/tests/test_migrate_md_to_graph.py`：
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from migrate_md_to_graph import parse_md_file, build_graph

SAMPLE = """---
name: dev-team-agents
description: 三角色开发团队
metadata:
  type: project
---

LBS 建了开发团队，见 [[subagent-driven-development]] 流水线。
"""


def test_parse_extracts_name_and_type():
    r = parse_md_file(SAMPLE)
    assert r["name"] == "dev-team-agents"
    assert r["type"] == "project"


def test_parse_extracts_links():
    r = parse_md_file(SAMPLE)
    assert r["links"] == ["subagent-driven-development"]


def test_parse_body_excludes_frontmatter():
    r = parse_md_file(SAMPLE)
    assert "name: dev-team-agents" not in r["body"]
    assert "LBS 建了开发团队" in r["body"]


def test_parse_type_defaults_to_decision():
    txt = "---\nname: foo\ndescription: bar\n---\n\nbody text"
    assert parse_md_file(txt)["type"] == "decision"


def test_build_graph_entities_and_relations():
    files = [parse_md_file(SAMPLE)]
    g = build_graph(files)
    assert g["entities"][0]["name"] == "dev-team-agents"
    assert g["entities"][0]["entityType"] == "project"
    assert g["entities"][0]["observations"] == [files[0]["body"]]
    assert {"from": "dev-team-agents", "to": "subagent-driven-development",
            "relationType": "relates_to"} in g["relations"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd ~/.claude/skills/project-memory && python -m pytest scripts/tests/test_migrate_md_to_graph.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'migrate_md_to_graph'`

- [ ] **Step 3: 写最小实现**

创建 `scripts/migrate_md_to_graph.py`：
```python
"""把旧文件式 .md 记忆解析为知识图谱 {entities, relations}。仅用标准库。"""
import re


def parse_md_file(text: str) -> dict:
    name, mtype, body = "", "decision", text
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.DOTALL)
    if m:
        front, body = m.group(1), m.group(2)
        nm = re.search(r"^\s*name:\s*(.+?)\s*$", front, re.MULTILINE)
        if nm:
            name = nm.group(1).strip()
        tm = re.search(r"^\s*type:\s*(.+?)\s*$", front, re.MULTILINE)
        if tm:
            mtype = tm.group(1).strip()
    links = re.findall(r"\[\[([^\]]+)\]\]", body)
    return {"name": name, "type": mtype, "body": body.strip(), "links": links}


def build_graph(files: list) -> dict:
    entities, relations = [], []
    for f in files:
        entities.append({
            "name": f["name"],
            "entityType": f["type"],
            "observations": [f["body"]],
        })
        for link in f["links"]:
            relations.append({
                "from": f["name"],
                "to": link,
                "relationType": "relates_to",
            })
    return {"entities": entities, "relations": relations}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd ~/.claude/skills/project-memory && python -m pytest scripts/tests/test_migrate_md_to_graph.py -v`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
git add ~/.claude/skills/project-memory/scripts/migrate_md_to_graph.py ~/.claude/skills/project-memory/scripts/tests/test_migrate_md_to_graph.py
git commit -m "feat(project-memory): parse legacy .md memory into knowledge graph"
```

---

## Task 3: references/setup.md（初始化/预检/迁移步骤）

**Files:**
- Create: `~/.claude/skills/project-memory/references/setup.md`

**Interfaces:**
- Consumes: `scripts/encode_project_path.py`、`scripts/migrate_md_to_graph.py`（Task 1、2）；MCP 工具 `mcp__memory__read_graph`、`create_entities`、`create_relations`、`add_observations`。
- Produces: 供 SKILL.md 引用的完整 setup 指令（Step 0–7）。

- [ ] **Step 1: 写 setup.md 全文**

创建 `references/setup.md`，内容必须逐条覆盖以下 8 步（每步写清「怎么查、怎么写、幂等如何保证」）：

```markdown
# Setup：初始化项目记忆系统（幂等，先查后写）

## Step 0 — 依赖预检与自动安装
1. 查 node/npx：`node -v` 与 `npx -v`。任一失败 → 报告需要 Node.js(LTS)，给 Windows 安装指引；不硬闯，不自动装系统级 Node。
2. 查 memory 包缓存：探测 `~/AppData/Local/npm-cache/_npx/*/node_modules/@modelcontextprotocol/server-memory` 是否存在。
   - 存在 → 跳过。
   - 不存在 → 主动预热安装：`npx -y @modelcontextprotocol/server-memory --help` 或 `npm i -g @modelcontextprotocol/server-memory`，确认拉取成功。
3. 冒烟测试：调用 `mcp__memory__read_graph`。能返回（哪怕空图谱 `{entities:[],relations:[]}`）即通路正常；报错则停在此步并报告（提示可能需重启会话让 .mcp.json 生效）。

## Step 1 — 实测 ${CLAUDE_PROJECT_DIR} 展开
在临时 .mcp.json 用 `${CLAUDE_PROJECT_DIR}` 写 MEMORY_FILE_PATH，重启会话后调 read_graph 验证记忆文件是否落在项目 .memory/ 下。
- 支持 → 方案 A（下 Step 2 用变量）。
- 不支持 → 方案 B：把 .mcp.json 加入 .gitignore，改用本机绝对路径，另提交 .mcp.json.template（占位 __PROJECT_DIR__），并告知用户「本文件每人本地生成一次」。

## Step 2 — 写/合并项目级 .mcp.json
目标片段（方案 A）：
{
  "mcpServers": {
    "memory": {
      "type": "stdio",
      "command": "cmd",
      "args": ["/c","npx","-y","@modelcontextprotocol/server-memory"],
      "env": { "MEMORY_FILE_PATH": "${CLAUDE_PROJECT_DIR}/.memory/memory.jsonl" }
    }
  }
}
- 若已有 .mcp.json：读入 → 合并 mcpServers.memory（不动其他服务）→ 写回。
- 若无：直接创建。

## Step 3 — 建 .memory/ 目录与空 memory.jsonl
mkdir -p .memory && 若无 memory.jsonl 则创建空文件。

## Step 4 — 迁移旧文件式记忆
1. 定位旧目录：`python ~/.claude/skills/project-memory/scripts/encode_project_path.py "<项目绝对路径>"` → `<编码名>`；旧目录 = `~/.claude/projects/<编码名>/memory/`。
2. 若目录不存在或无 .md（除 MEMORY.md）→ 跳过本步（新项目情形）。
3. 读取每个 .md（排除 MEMORY.md），用 `scripts/migrate_md_to_graph.py` 的 parse_md_file + build_graph 得到 {entities, relations}。
4. 写入 MCP：create_entities → create_relations（对 relations 中 to 端不存在的实体，MCP 允许悬挂关系，保留）。逐实体 add_observations 若已存在同名实体。
5. 校验：调 read_graph 回读，确认迁移的每个实体名都在图中、observation 内容一致、relations 条数吻合。
6. 校验通过 → 删除旧 .md 与 MEMORY.md（及空的 memory 目录）。校验不通过 → 保留旧文件，报告缺失/差异明细，不删。

## Step 5 — 向项目 CLAUDE.md 注入开场规则
在项目根 CLAUDE.md（无则创建）插入幂等标记块；已存在标记块则替换其内容：
<!-- project-memory:start -->
会话开始时，先调用 mcp__memory__read_graph 读取本项目记忆再开始工作。若因 MCP 服务/包缺失失败，按 project-memory skill 的 setup Step 0 自愈安装后重试。
<!-- project-memory:end -->

## Step 6 — 配 .gitattributes
确保含一行（无则追加）：`.memory/memory.jsonl merge=union`

## Step 7 — 提示重启
告知用户：.mcp.json 变更需重启 Claude Code 会话才生效。记忆数据文件由用户自行 git 提交（skill 不自动 commit）。
```

- [ ] **Step 2: 验收检查 — 文件存在且覆盖 8 步**

Run:
```bash
test -f ~/.claude/skills/project-memory/references/setup.md && \
grep -c -E "^## Step [0-7]" ~/.claude/skills/project-memory/references/setup.md
```
Expected: 输出 `8`（Step 0–7 共 8 个二级标题）

- [ ] **Step 3: 验收检查 — 关键约束存在**

Run:
```bash
grep -q 'merge=union' ~/.claude/skills/project-memory/references/setup.md && \
grep -q 'project-memory:start' ~/.claude/skills/project-memory/references/setup.md && \
grep -q 'CLAUDE_PROJECT_DIR' ~/.claude/skills/project-memory/references/setup.md && \
grep -q '校验通过' ~/.claude/skills/project-memory/references/setup.md && echo OK
```
Expected: 输出 `OK`

- [ ] **Step 4: 提交**

```bash
git add ~/.claude/skills/project-memory/references/setup.md
git commit -m "docs(project-memory): setup reference (precheck/init/migrate)"
```

---

## Task 4: references/schema.md（数据模型 + 触发判定）

**Files:**
- Create: `~/.claude/skills/project-memory/references/schema.md`

**Interfaces:**
- Consumes: 无。
- Produces: 供 SKILL.md 与 workflows.md 引用的实体/关系/观察规范与三类写入触发场景。

- [ ] **Step 1: 写 schema.md 全文**

创建 `references/schema.md`：
```markdown
# 记忆数据模型（知识图谱）

## 实体类型（entityType）
- pitfall — 踩过的坑：报错根因、反直觉行为、陷阱。
- decision — 重要决策/关键数据：选型拍板、关键参数。
- progress — 项目进度节点：阶段完成、分支合并、里程碑。
- operation — 重要操作：git 回退/revert/reset、删除或重命名关键文件、改配置、迁移、危险命令。
- component — 项目模块/子系统。
- convention — 项目约定：命名、流程、平台约束。

## Observation（挂在实体上的事实）
- 每条一句，带日期前缀：`YYYY-MM-DD: 具体事实`。
- 事实性、可复用；不写一次性对话细节。

## Relation（有向）
- pitfall —occurs_in→ component
- decision —affects→ component
- operation —acts_on→ component
- 迁移生成的历史关联统一用 relates_to。

## 四类写入触发场景
| 场景 | 信号 | 记成 |
| 坑 | 报错根因、"原来是因为…"、反直觉行为 | pitfall 实体 + observation |
| 重要数据/决策 | 选型拍板、关键参数、架构约定 | decision / convention 实体 |
| 项目进度 | 阶段完成、分支合并、里程碑 | progress 实体，更新既有而非堆叠 |
| 重要操作 | git 回退/revert/reset、删改关键文件、改配置、迁移、危险命令 | operation 实体 + observation：记改了什么、为什么、影响、如何复原 |

## git 回退专项（必记）
一旦执行或用户提到 git revert/reset/回退，必须写一条 operation observation，含：
- 回退了哪些 commit（短 SHA + 主题）
- 回退原因
- 丢弃 / 恢复了什么改动
- 当前 HEAD 位置

## 命名规范
- 实体 name 用 kebab-case，全项目唯一。
- 进度类：优先 add_observations 到既有 progress 实体，不为同一里程碑反复建新实体。
- 操作类：git 历史操作统一记到 name 为 `git-operations` 的 operation 实体，按日期追加 observation，不逐次建新实体。
```

- [ ] **Step 2: 验收检查 — 6 类实体齐全 + git 回退专项**

Run:
```bash
for t in pitfall decision progress operation component convention; do \
grep -q "^- $t " ~/.claude/skills/project-memory/references/schema.md || echo "MISSING $t"; done; \
grep -q 'git 回退专项' ~/.claude/skills/project-memory/references/schema.md || echo "MISSING git-revert"; echo done
```
Expected: 仅输出 `done`（无 MISSING）

- [ ] **Step 3: 提交**

```bash
git add ~/.claude/skills/project-memory/references/schema.md
git commit -m "docs(project-memory): memory schema and write triggers"
```

---

## Task 5: references/workflows.md（读/写/整理 + 自愈）

**Files:**
- Create: `~/.claude/skills/project-memory/references/workflows.md`

**Interfaces:**
- Consumes: `schema.md`（触发场景与实体类型）；MCP 工具全套。
- Produces: 供 SKILL.md 引用的运行时操作细则。

- [ ] **Step 1: 写 workflows.md 全文**

创建 `references/workflows.md`：
```markdown
# 运行时工作流

## 开场读取
- 会话开始（由项目 CLAUDE.md 规则驱动）先调 `mcp__memory__read_graph`。
- 图谱非空 → 简述已加载哪些 progress/pitfall/convention，再开始工作。
- 调用失败且因 MCP 服务/包缺失 → 触发 setup.md Step 0 自愈，装好后重试；仍失败则告知用户并降级继续（不阻塞工作）。

## 写入（命中 schema.md 三类触发场景时主动执行）
1. 先 `search_nodes` 查是否已有相关实体，避免重复建实体。
2. 新主题 → `create_entities`（按 schema 选 entityType，name 用 kebab-case）。
3. 已有实体新增事实 → `add_observations`（带 YYYY-MM-DD 前缀）。
4. 有跨实体关系 → `create_relations`。
5. 进度类：更新既有 progress 实体，不堆叠新实体。
6. 重要操作（尤其 git 回退/revert/reset）：追加到 `git-operations`（或对应 operation）实体，记改了什么、为什么、影响、如何复原、当前 HEAD。见 schema.md「git 回退专项」。
7. 不自动 git commit 记忆文件。

## 整理（用户要求或图谱明显冗余时）
- `read_graph` 通览 → 找重复/过时实体与 observation。
- 用 `delete_observations` 删过时事实、`delete_entities` 删废弃实体（连带其关系）。
- 合并同义实体：把 observation 迁到保留实体后删除多余实体。

## 运行时自愈（任何 mcp__memory__* 调用失败）
- 若错误提示服务未连/包缺失 → 执行 setup.md Step 0（预检+安装）→ 重试一次。
- 若因 .mcp.json 刚变更未生效 → 提示用户重启会话。
```

- [ ] **Step 2: 验收检查 — 四大块齐全**

Run:
```bash
for h in "开场读取" "写入" "整理" "运行时自愈"; do \
grep -q "## $h" ~/.claude/skills/project-memory/references/workflows.md || echo "MISSING $h"; done; echo done
```
Expected: 仅输出 `done`

- [ ] **Step 3: 提交**

```bash
git add ~/.claude/skills/project-memory/references/workflows.md
git commit -m "docs(project-memory): runtime read/write/tidy/self-heal workflows"
```

---

## Task 6: SKILL.md（入口，串起全部）

**Files:**
- Create: `~/.claude/skills/project-memory/SKILL.md`

**Interfaces:**
- Consumes: `references/setup.md`、`references/schema.md`、`references/workflows.md`、`scripts/*`。
- Produces: skill 入口，供 Claude Code 装载与触发。

- [ ] **Step 1: 写 SKILL.md 全文**

创建 `SKILL.md`：
```markdown
---
name: project-memory
description: Use when starting a session in a project, or when hitting a pitfall / making a key decision / reaching a progress milestone — manages per-project knowledge-graph memory via MCP server-memory
---

# Project Memory

用 MCP `@modelcontextprotocol/server-memory` 管理**每项目独立、跟随 git 共享**的知识图谱记忆。记忆存于项目内 `.memory/memory.jsonl`。

## 何时触发
- **会话开始**：读取本项目记忆（见 references/workflows.md 开场读取）。
- **命中写入场景**：踩坑 / 重要决策或数据 / 进度节点（见 references/schema.md 三类触发）。
- **首次在某项目使用 / 记忆系统未初始化**：跑一次性 setup（见 references/setup.md）。
- **用户要求整理记忆**：见 references/workflows.md 整理。

## 首次使用判定
项目根**无** `.mcp.json` 的 memory 服务，或**无** `.memory/memory.jsonl` → 视为未初始化，执行 references/setup.md 的 Step 0–7（含依赖预检自动安装、旧 .md 记忆迁移并删除、CLAUDE.md 开场规则注入）。setup 幂等，可安全重跑。

## 运行时铁律
- 开场先 `mcp__memory__read_graph`；命中触发场景主动写入；调用失败按 workflows.md 自愈。
- 写入前先 `search_nodes` 去重；进度类更新既有实体不堆叠。
- 实体类型/命名/observation 格式严格按 references/schema.md。
- 不自动 git commit 记忆文件。

## 参考
- 初始化/预检/迁移：references/setup.md
- 数据模型/触发判定：references/schema.md
- 读写整理/自愈：references/workflows.md
- 辅助脚本：scripts/encode_project_path.py、scripts/migrate_md_to_graph.py
```

- [ ] **Step 2: 验收检查 — frontmatter 与路由完整**

Run:
```bash
head -4 ~/.claude/skills/project-memory/SKILL.md | grep -q 'name: project-memory' && \
grep -q 'references/setup.md' ~/.claude/skills/project-memory/SKILL.md && \
grep -q 'references/schema.md' ~/.claude/skills/project-memory/SKILL.md && \
grep -q 'references/workflows.md' ~/.claude/skills/project-memory/SKILL.md && echo OK
```
Expected: 输出 `OK`

- [ ] **Step 3: 提交**

```bash
git add ~/.claude/skills/project-memory/SKILL.md
git commit -m "feat(project-memory): SKILL.md entry point"
```

---

## Task 7: 端到端验证（在本项目实跑一次 setup）

**Files:**
- 只读验证，无新增源文件；产出物为本项目的 `.mcp.json`、`.memory/memory.jsonl`、`.gitattributes`、`CLAUDE.md` 更新。

**Interfaces:**
- Consumes: 完整 skill（Task 1–6）。
- Produces: 本项目记忆系统就绪 + 旧 `.md` 记忆迁移完成的证据。

- [ ] **Step 1: 脚本冒烟 — 路径编码对本项目正确**

Run: `python ~/.claude/skills/project-memory/scripts/encode_project_path.py "e:\LBS-FramWare"`
Expected: 输出 `e--LBS-FramWare`

- [ ] **Step 2: 脚本冒烟 — 解析现有旧记忆**

Run:
```bash
python -c "import sys; sys.path.insert(0, r'C:/Users/24160/.claude/skills/project-memory/scripts'); \
from migrate_md_to_graph import parse_md_file, build_graph; \
import glob, io; \
d=r'C:/Users/24160/.claude/projects/e--LBS-FramWare/memory'; \
fs=[parse_md_file(open(f,encoding='utf-8').read()) for f in glob.glob(d+'/*.md') if not f.endswith('MEMORY.md')]; \
g=build_graph(fs); print('entities:', [e['name'] for e in g['entities']]); print('relations:', len(g['relations']))"
```
Expected: 打印出至少 `dev-team-agents` 与 `project-progress` 两个实体名，relations 数 ≥ 1（dev-team-agents 内有 `[[subagent-driven-development]]`）。

- [ ] **Step 3: 按 setup.md 执行初始化（人工按步骤跑）**

依 references/setup.md 逐步执行 Step 0–7（在本项目 `e:\LBS-FramWare`）。关键产出物验收：
```bash
cd "e:/LBS-FramWare" && \
grep -q 'server-memory' .mcp.json && \
grep -q 'MEMORY_FILE_PATH' .mcp.json && \
test -f .memory/memory.jsonl && \
grep -q 'merge=union' .gitattributes && \
grep -q 'project-memory:start' CLAUDE.md && echo "SETUP-OK"
```
Expected: 输出 `SETUP-OK`

- [ ] **Step 4: 迁移校验 — 图谱含旧记忆且旧文件已删**

Run（重启会话使 .mcp.json 生效后）：调用 `mcp__memory__read_graph` 确认含 `dev-team-agents`、`project-progress` 实体；再检查旧文件已删除：
```bash
ls "C:/Users/24160/.claude/projects/e--LBS-FramWare/memory/"*.md 2>/dev/null && echo "STILL-EXISTS(应为空)" || echo "MIGRATED-AND-REMOVED"
```
Expected: `read_graph` 含上述实体；bash 输出 `MIGRATED-AND-REMOVED`。（若校验未过则旧文件保留，属预期兜底。）

- [ ] **Step 5: 提交端到端验证产物**

```bash
cd "e:/LBS-FramWare" && git add .mcp.json .memory/ .gitattributes CLAUDE.md
git commit -m "chore(project-memory): initialize project memory + migrate legacy notes"
```

---

## Self-Review

**Spec coverage：**
- 依赖预检自动安装 → Task 3 Step 0 + Task 5 自愈 ✅
- 一次性初始化（幂等可移植）→ Task 3 Step 1–3、6、7 ✅
- `${CLAUDE_PROJECT_DIR}` 方案 A + 回退 B → Task 3 Step 1–2 ✅
- 迁移旧 .md 并校验后删除 → Task 2（解析）+ Task 3 Step 4 + Task 7 Step 4 ✅
- CLAUDE.md 开场规则注入 → Task 3 Step 5 ✅
- 数据模型/五类实体/三类触发 → Task 4 ✅
- 开场读/写入/整理/自愈 → Task 5 ✅
- skill 入口与触发判定 → Task 6 ✅
- 端到端可移植验证 → Task 7 ✅

**Placeholder scan：** 无 TBD/TODO；脚本与 markdown 均给全文；验收命令均可执行。

**Type consistency：** `encode_project_path`（Task1/7）、`parse_md_file`/`build_graph`（Task2/7）签名一致；`<编码名>` 编码规则（Global Constraints / Task1 / Task7）一致；实体类型集合（schema.md / SKILL.md）一致；`project-memory:start/end` 标记（setup.md / workflows 引用 / Task7 验收）一致。
