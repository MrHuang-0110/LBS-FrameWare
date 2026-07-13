# claude-marketplace Plugin Repo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a standalone local git repo that serves as a Claude Code marketplace, migrate the `project-ops` plugin into it, rewire all skill script references to the `${CLAUDE_PLUGIN_ROOT}` runtime variable, and verify install works — establishing a single source of truth to end version drift.

**Architecture:** A new repo `e:/claude-marketplace` mirrors the official marketplace layout (`.claude-plugin/marketplace.json` at root + `plugins/<name>/` subdirs). `project-ops` is copied in from `e:/LBS-FramWare/plugins/`, then every hardcoded/placeholder script path in both bundled skills is replaced with `${CLAUDE_PLUGIN_ROOT}/skills/<skill>/scripts/...`. Old copies (business-repo `plugins/`, global `github-workspace`) are removed; global `project-memory` is kept until smoke-verified.

**Tech Stack:** Claude Code plugin/marketplace format (JSON manifests), git, Python 3 (stdlib, pytest) for the migrated skill scripts, `${CLAUDE_PLUGIN_ROOT}` runtime path variable.

## Global Constraints

- New repo root: `e:/claude-marketplace` (standalone git repo, local only, no remote yet).
- Marketplace manifest: `e:/claude-marketplace/.claude-plugin/marketplace.json`; market `name`: `local-marketplace`.
- Plugin layout: `e:/claude-marketplace/plugins/project-ops/` containing `.claude-plugin/plugin.json`, `README.md`, `skills/{project-memory,github-workspace}/`.
- In-repo plugin `source` in marketplace.json is a **relative string**: `"./plugins/project-ops"` (verified against official marketplace format).
- Path variable: all skill script invocations use `${CLAUDE_PLUGIN_ROOT}/skills/<skill>/scripts/<script>.py` — NEVER `<本 skill>/`, NEVER `<project-memory skill scripts dir>/`, NEVER `~/.claude/skills/...`.
- Not-substituted degradation: if a literal `${CLAUDE_PLUGIN_ROOT}` reaches a shell command unexpanded, the skill must report "plugin root variable not expanded" and NOT run the mangled path (borrowed from official code-modernization).
- Consumer-project CLAUDE.md opening rule must NOT hardcode any script path — it references the skill by name only. (The existing injected block at setup.md already does this; the plan confirms it.)
- Python: stdlib only; Windows uses `python` (not `python3`); Bash tool is Git Bash.
- All 38 migrated skill script tests (github-workspace: 11, project-memory: 27) must pass after migration + rewiring.
- Commit messages end with the `Co-Authored-By: Claude <noreply@anthropic.com>` trailer. Commits inside `e:/claude-marketplace` are made in that repo; cleanup commits to the business repo are made in `e:/LBS-FramWare`.
- The plan operates on the **plugin copy** as the source of truth for `project-ops` (the version in `e:/LBS-FramWare/plugins/`), NOT the hand-installed global `~/.claude/skills/` copies.

---

### Task 1: Scaffold the standalone marketplace repo

**Files:**
- Create: `e:/claude-marketplace/.claude-plugin/marketplace.json`
- Create: `e:/claude-marketplace/README.md`
- Create: `e:/claude-marketplace/.gitignore`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: an initialized git repo at `e:/claude-marketplace` with a valid marketplace manifest referencing `./plugins/project-ops` (the plugin dir is populated in Task 2). Market `name` = `local-marketplace`.

- [ ] **Step 1: Initialize the repo**

Run (Git Bash):
```bash
mkdir -p e:/claude-marketplace/.claude-plugin
cd e:/claude-marketplace && git init && git config user.name "LBS Dev" && git config user.email "lbs@local"
```
Expected: `Initialized empty Git repository in .../claude-marketplace/.git/`

- [ ] **Step 2: Write the marketplace manifest**

Create `e:/claude-marketplace/.claude-plugin/marketplace.json`:

```json
{
  "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
  "name": "local-marketplace",
  "description": "Personal Claude Code plugin marketplace — single source of truth for project-ops and future plugins",
  "owner": {
    "name": "LBS Dev"
  },
  "plugins": [
    {
      "name": "project-ops",
      "description": "Always-on project memory + git workspace management with semantic sync",
      "author": { "name": "LBS Dev" },
      "category": "productivity",
      "source": "./plugins/project-ops"
    }
  ]
}
```

- [ ] **Step 3: Write the repo README**

Create `e:/claude-marketplace/README.md`:

```markdown
# local-marketplace

Personal Claude Code plugin marketplace. Single source of truth for plugins — install
from here so there is only ever one version.

## Plugins

- **project-ops** — always-on knowledge-graph project memory + git workspace-branch
  management (task-level commit/push, semantic memory sync, manual-gated PRs, git-optional).

## Use (per machine)

    /plugin marketplace add e:/claude-marketplace
    /plugin install project-ops@local-marketplace

Restart the session when prompted. To pull updates after this repo changes:

    /plugin marketplace update local-marketplace

## Adding a plugin

1. Create `plugins/<name>/` with a `.claude-plugin/plugin.json` and its `skills/`.
2. Append an entry to `.claude-plugin/marketplace.json` `plugins[]` with `"source": "./plugins/<name>"`.
3. Skill scripts must reference themselves via `${CLAUDE_PLUGIN_ROOT}/skills/<skill>/scripts/...`.
```

- [ ] **Step 4: Write .gitignore**

Create `e:/claude-marketplace/.gitignore`:

```
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 5: Validate JSON and commit**

Run:
```bash
cd e:/claude-marketplace && python -c "import json,pathlib; json.loads(pathlib.Path('.claude-plugin/marketplace.json').read_text(encoding='utf-8')); print('OK')"
```
Expected: `OK`

```bash
cd e:/claude-marketplace && git add -A && git commit -m "feat: scaffold local-marketplace repo + manifest

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Migrate project-ops into the marketplace repo

**Files:**
- Create: `e:/claude-marketplace/plugins/project-ops/` (entire tree copied from `e:/LBS-FramWare/plugins/project-ops/`)

**Interfaces:**
- Consumes: Task 1 repo root; the source plugin tree at `e:/LBS-FramWare/plugins/project-ops/`.
- Produces: `plugins/project-ops/` inside the marketplace repo with `.claude-plugin/plugin.json`, `README.md`, and `skills/{project-memory,github-workspace}/` — path references NOT yet rewired (that is Task 3).

- [ ] **Step 1: Copy the plugin tree**

Run:
```bash
mkdir -p e:/claude-marketplace/plugins
cp -r e:/LBS-FramWare/plugins/project-ops e:/claude-marketplace/plugins/project-ops
```

- [ ] **Step 2: Remove any copied caches**

Run:
```bash
find e:/claude-marketplace/plugins/project-ops -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; \
find e:/claude-marketplace/plugins/project-ops -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null; \
echo done
```
Expected: `done`

- [ ] **Step 3: Verify the tree structure is complete**

Run:
```bash
cd e:/claude-marketplace && python -c "
import pathlib
root = pathlib.Path('plugins/project-ops')
required = [
    '.claude-plugin/plugin.json',
    'README.md',
    'skills/project-memory/SKILL.md',
    'skills/github-workspace/SKILL.md',
    'skills/github-workspace/references/init.md',
    'skills/github-workspace/references/sync.md',
    'skills/github-workspace/references/pr.md',
    'skills/github-workspace/scripts/init_workspace.py',
    'skills/github-workspace/scripts/diff_summary.py',
    'skills/project-memory/references/setup.md',
    'skills/project-memory/references/workflows.md',
    'skills/project-memory/scripts/build_index.py',
    'skills/project-memory/scripts/check_memory_path.py',
    'skills/project-memory/scripts/encode_project_path.py',
    'skills/project-memory/scripts/migrate_md_to_graph.py',
]
missing = [r for r in required if not (root / r).exists()]
print('MISSING:', missing) if missing else print('ALL PRESENT')
"
```
Expected: `ALL PRESENT`

- [ ] **Step 4: Run the migrated tests (baseline — still pre-rewiring)**

Run:
```bash
cd e:/claude-marketplace && python -m pytest plugins/project-ops/skills/github-workspace/scripts/tests/ plugins/project-ops/skills/project-memory/scripts/tests/ -q
```
Expected: `38 passed`

- [ ] **Step 5: Commit**

```bash
cd e:/claude-marketplace && git add -A && git commit -m "feat: migrate project-ops plugin into marketplace

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Rewire github-workspace script paths to ${CLAUDE_PLUGIN_ROOT}

**Files:**
- Modify: `e:/claude-marketplace/plugins/project-ops/skills/github-workspace/SKILL.md` (lines 22-24)
- Modify: `e:/claude-marketplace/plugins/project-ops/skills/github-workspace/references/init.md` (line 17)
- Modify: `e:/claude-marketplace/plugins/project-ops/skills/github-workspace/references/sync.md` (line 12)

**Interfaces:**
- Consumes: Task 2's migrated plugin tree.
- Produces: github-workspace skill whose every script invocation uses `${CLAUDE_PLUGIN_ROOT}/skills/github-workspace/scripts/...`, plus a not-substituted degradation rule in SKILL.md.

- [ ] **Step 1: Rewrite SKILL.md script section (lines 22-24)**

In `.../github-workspace/SKILL.md`, replace the exact block:

```markdown
## 脚本（相对本 skill 定位,勿硬编码全局路径）
- 初始化 workspace 分支：`python <本 skill>/scripts/init_workspace.py [--branch workspace] [--main main] [--remote origin]`
- 生成改动摘要：`python <本 skill>/scripts/diff_summary.py`（读已暂存改动,输出一行摘要）
```

with:

```markdown
## 脚本（用插件根变量定位,勿硬编码路径）
- 初始化 workspace 分支：`python ${CLAUDE_PLUGIN_ROOT}/skills/github-workspace/scripts/init_workspace.py [--branch workspace] [--main main] [--remote origin]`
- 生成改动摘要：`python ${CLAUDE_PLUGIN_ROOT}/skills/github-workspace/scripts/diff_summary.py`（读已暂存改动,输出一行摘要）
- **路径变量降级**：若执行时命令里出现字面量 `${CLAUDE_PLUGIN_ROOT}`（未被展开）→ 不运行拼错的路径,报告「插件根变量未展开,请确认本插件经 marketplace 正确安装」并停下。
```

- [ ] **Step 2: Rewrite init.md line 17**

In `.../github-workspace/references/init.md`, replace:

```markdown
2. 跑 `python <本 skill>/scripts/init_workspace.py`。
```

with:

```markdown
2. 跑 `python ${CLAUDE_PLUGIN_ROOT}/skills/github-workspace/scripts/init_workspace.py`。
```

- [ ] **Step 3: Rewrite sync.md line 12**

In `.../github-workspace/references/sync.md`, replace:

```markdown
2. 跑 `python <本 skill>/scripts/diff_summary.py` 得到一行摘要,如 `3 files, +42/-7 (backend, gui)`。
```

with:

```markdown
2. 跑 `python ${CLAUDE_PLUGIN_ROOT}/skills/github-workspace/scripts/diff_summary.py` 得到一行摘要,如 `3 files, +42/-7 (backend, gui)`。
```

- [ ] **Step 4: Verify no old-form path references remain in github-workspace**

Run:
```bash
cd e:/claude-marketplace && grep -rn "<本 skill>\|~/.claude/skills/github-workspace" plugins/project-ops/skills/github-workspace/ || echo "NONE REMAIN"
```
Expected: `NONE REMAIN`

(Note: the prose line "本 skill 不自己写知识图谱" in SKILL.md is NOT a path — it is fine and must stay. The grep pattern `<本 skill>` with angle brackets will not match it.)

- [ ] **Step 5: Verify the CLAUDE_PLUGIN_ROOT references are present and well-formed**

Run:
```bash
cd e:/claude-marketplace && grep -rn "CLAUDE_PLUGIN_ROOT" plugins/project-ops/skills/github-workspace/
```
Expected: 4 lines — 2 in SKILL.md (init_workspace + diff_summary invocations), 1 in init.md, 1 in sync.md — plus the degradation line in SKILL.md mentioning the literal (5 matches total).

- [ ] **Step 6: Commit**

```bash
cd e:/claude-marketplace && git add -A && git commit -m "refactor(github-workspace): use \${CLAUDE_PLUGIN_ROOT} for script paths

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Rewire project-memory script paths to ${CLAUDE_PLUGIN_ROOT}

**Files:**
- Modify: `e:/claude-marketplace/plugins/project-ops/skills/project-memory/references/setup.md` (Note line 1; invocation lines 61, 67, 77)
- Modify: `e:/claude-marketplace/plugins/project-ops/skills/project-memory/references/workflows.md` (Note line 1; invocation lines 10, 14)

**Interfaces:**
- Consumes: Task 2's migrated plugin tree.
- Produces: project-memory skill whose script invocations use `${CLAUDE_PLUGIN_ROOT}/skills/project-memory/scripts/...`; the `<project-memory skill scripts dir>` placeholder and its Note block are removed. The injected consumer CLAUDE.md opening rule (setup.md, `project-memory:start`/`end` block) is confirmed to reference the skill by name with no hardcoded path — no change needed there.

- [ ] **Step 1: Rewrite the Note block + invocations in setup.md**

In `.../project-memory/references/setup.md`:

(a) Delete the Note line at the top (line 1):
```markdown
> Note: `<project-memory skill scripts dir>` = the `scripts/` folder next to this skill's SKILL.md.
```
(and any continuation lines of that same `> ...` Note block — remove the whole leading Note block that defines `<project-memory skill scripts dir>`).

(b) Replace line 61:
```markdown
用 `python <project-memory skill scripts dir>/check_memory_path.py "<项目绝对路径>"` 核对 `.mcp.json` 的 `MEMORY_FILE_PATH` 已是当前项目绝对路径：
```
with:
```markdown
用 `python ${CLAUDE_PLUGIN_ROOT}/skills/project-memory/scripts/check_memory_path.py "<项目绝对路径>"` 核对 `.mcp.json` 的 `MEMORY_FILE_PATH` 已是当前项目绝对路径：
```

(c) Replace line 67:
```markdown
1. 定位旧目录：`python <project-memory skill scripts dir>/encode_project_path.py "<项目绝对路径>"` → `<编码名>`；旧目录 = `~/.claude/projects/<编码名>/memory/`。
```
with:
```markdown
1. 定位旧目录：`python ${CLAUDE_PLUGIN_ROOT}/skills/project-memory/scripts/encode_project_path.py "<项目绝对路径>"` → `<编码名>`；旧目录 = `~/.claude/projects/<编码名>/memory/`。
```

(d) Replace line 77:
```markdown
跑 `python <project-memory skill scripts dir>/build_index.py "<项目>/.memory/memory.jsonl" "<项目>/.memory/index.md"`，生成两层记忆的索引层。此后每次开场读它、写入/整理后重建它（见 references/workflows.md）。新项目（空图）也会生成含「（暂无记忆）」的占位索引。
```
with:
```markdown
跑 `python ${CLAUDE_PLUGIN_ROOT}/skills/project-memory/scripts/build_index.py "<项目>/.memory/memory.jsonl" "<项目>/.memory/index.md"`，生成两层记忆的索引层。此后每次开场读它、写入/整理后重建它（见 references/workflows.md）。新项目（空图）也会生成含「（暂无记忆）」的占位索引。
```

Note: setup.md line 69's `scripts/migrate_md_to_graph.py` is a bare relative reference inside a prose sentence describing which script's functions to use; leave it as-is (it does not invoke via a path prefix). Only the three `python <...>/` invocation lines change.

- [ ] **Step 2: Rewrite the Note block + invocations in workflows.md**

In `.../project-memory/references/workflows.md`:

(a) Delete the Note line at the top (line 1):
```markdown
> Note: `<project-memory skill scripts dir>` = the `scripts/` folder next to this skill's SKILL.md.
```
(remove the whole leading Note block that defines the placeholder).

(b) Replace line 10:
```markdown
  - 检查方法：跑 `python <project-memory skill scripts dir>/check_memory_path.py <当前项目绝对路径>`。
```
with:
```markdown
  - 检查方法：跑 `python ${CLAUDE_PLUGIN_ROOT}/skills/project-memory/scripts/check_memory_path.py <当前项目绝对路径>`。
```

(c) Replace line 14:
```markdown
  1. 重建索引保证新鲜：`python <project-memory skill scripts dir>/build_index.py "<项目>/.memory/memory.jsonl" "<项目>/.memory/index.md"`。
```
with:
```markdown
  1. 重建索引保证新鲜：`python ${CLAUDE_PLUGIN_ROOT}/skills/project-memory/scripts/build_index.py "<项目>/.memory/memory.jsonl" "<项目>/.memory/index.md"`。
```

- [ ] **Step 3: Confirm the consumer CLAUDE.md opening rule needs no path change**

Run:
```bash
cd e:/claude-marketplace && sed -n '/project-memory:start/,/project-memory:end/p' plugins/project-ops/skills/project-memory/references/setup.md
```
Expected output (the injected block references the skill by name, no hardcoded script path — CONFIRM it contains no `python .../scripts/` invocation):
```
<!-- project-memory:start -->
会话开始时，先调用 mcp__memory__read_graph 读取本项目记忆再开始工作。若因 MCP 服务/包缺失失败，按 project-memory skill 的 setup Step 0 自愈安装后重试。
<!-- project-memory:end -->
```
If it contains any `${CLAUDE_PLUGIN_ROOT}` or hardcoded script path, remove that path and keep only the skill-name reference. (Per the spec §5.3, the consumer CLAUDE.md must not depend on a path variable.)

- [ ] **Step 4: Verify no placeholder/hardcoded path references remain**

Run:
```bash
cd e:/claude-marketplace && grep -rn "project-memory skill scripts dir\|~/.claude/skills/project-memory/scripts" plugins/project-ops/skills/project-memory/ || echo "NONE REMAIN"
```
Expected: `NONE REMAIN`

- [ ] **Step 5: Verify the CLAUDE_PLUGIN_ROOT references are present**

Run:
```bash
cd e:/claude-marketplace && grep -rn "CLAUDE_PLUGIN_ROOT" plugins/project-ops/skills/project-memory/references/
```
Expected: 5 lines — setup.md (check_memory_path, encode_project_path, build_index = 3) and workflows.md (check_memory_path, build_index = 2).

- [ ] **Step 6: Commit**

```bash
cd e:/claude-marketplace && git add -A && git commit -m "refactor(project-memory): use \${CLAUDE_PLUGIN_ROOT} for script paths

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: Post-rewiring verification + plugin README refresh

**Files:**
- Modify: `e:/claude-marketplace/plugins/project-ops/README.md` (install instructions → marketplace-based)

**Interfaces:**
- Consumes: Tasks 3-4 rewired skills.
- Produces: a fully self-consistent plugin whose tests pass and whose README documents marketplace install. This is the last task before old-copy cleanup.

- [ ] **Step 1: Re-run the full test suite (confirm rewiring broke nothing)**

Run:
```bash
cd e:/claude-marketplace && python -m pytest plugins/project-ops/skills/github-workspace/scripts/tests/ plugins/project-ops/skills/project-memory/scripts/tests/ -q
```
Expected: `38 passed`

(The scripts themselves were not edited — only doc invocation strings — so tests must still pass. If any fail, a script file was touched by mistake; investigate before continuing.)

- [ ] **Step 2: Global check — no stale path forms anywhere in the plugin**

Run:
```bash
cd e:/claude-marketplace && grep -rn "<本 skill>\|<project-memory skill scripts dir>" plugins/project-ops/ || echo "NONE REMAIN"
```
Expected: `NONE REMAIN`

- [ ] **Step 3: Update the plugin README install section**

In `.../plugins/project-ops/README.md`, replace the `## Install (local, during development)` section (the block containing `/plugin marketplace add plugins/project-ops` and `/plugin install project-ops@project-ops-local`) with:

```markdown
## Install

From any machine that has this marketplace repo:

    /plugin marketplace add e:/claude-marketplace
    /plugin install project-ops@local-marketplace

Restart the session if prompted (MCP/skill changes take effect on restart).
Pull updates later with: `/plugin marketplace update local-marketplace`.
```

- [ ] **Step 4: Commit**

```bash
cd e:/claude-marketplace && git add -A && git commit -m "docs(project-ops): marketplace-based install instructions

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: Smoke-test marketplace install

**Files:**
- None (verification task; may write a scratch note only if a step fails).

**Interfaces:**
- Consumes: the committed marketplace repo.
- Produces: confirmation that Claude Code can add the marketplace, install project-ops, and that `${CLAUDE_PLUGIN_ROOT}` expands at runtime. This gate must pass before Task 7 deletes old copies.

- [ ] **Step 1: Add the marketplace**

In the Claude Code session, run:
```
/plugin marketplace add e:/claude-marketplace
```
Expected: marketplace `local-marketplace` added, listing 1 plugin (`project-ops`). If it errors, fix the manifest before proceeding.

- [ ] **Step 2: Install the plugin**

Run:
```
/plugin install project-ops@local-marketplace
```
Expected: install succeeds; a restart may be prompted (MCP/skill changes take effect on restart).

- [ ] **Step 3: Verify install landed in the versioned cache**

Run (Git Bash):
```bash
find "C:/Users/24160/.claude/plugins/cache" -ipath "*project-ops*" -name "plugin.json" 2>/dev/null
```
Expected: a path like `.../cache/local-marketplace/project-ops/<version>/.claude-plugin/plugin.json` exists (confirms the plugin is installed from the marketplace, not the source repo).

- [ ] **Step 4: Verify ${CLAUDE_PLUGIN_ROOT} resolves to a runnable script**

After the install cache path is known (call it `<CACHE>`), confirm the scripts are present and runnable at the installed location:
```bash
find "C:/Users/24160/.claude/plugins/cache" -ipath "*project-ops*" -name "init_workspace.py" 2>/dev/null | head -1
```
Expected: prints the installed path to `skills/github-workspace/scripts/init_workspace.py`. This is the path `${CLAUDE_PLUGIN_ROOT}/skills/github-workspace/scripts/init_workspace.py` expands to. (Full runtime-expansion is exercised when the skill is actually invoked; presence at the cache path confirms the layout is correct.)

- [ ] **Step 5: Record smoke result**

State in the task report: marketplace added ✅, plugin installed ✅, cache path confirmed ✅, scripts present at installed location ✅. No commit (verification only). If any step failed, STOP and report — do not proceed to Task 7 (cleanup) until smoke passes.

---

### Task 7: Clean up old plugin copies (drift sources)

**Files:**
- Delete: `e:/LBS-FramWare/plugins/` (business-repo incubation copy) — committed in the LBS-FramWare repo.
- Delete: `C:/Users/24160/.claude/skills/github-workspace/` (hand-installed global copy).
- Keep: `C:/Users/24160/.claude/skills/project-memory/` (still used by the current session; removal deferred per spec §6.2 / §8).

**Interfaces:**
- Consumes: Task 6's passing smoke test (this task must NOT run if smoke failed).
- Produces: a single source of truth (the marketplace repo + its installed cache). Business repo no longer carries the plugin; global `github-workspace` duplicate removed.

- [ ] **Step 1: Confirm smoke test passed (guard)**

Confirm Task 6 reported all ✅. If not, STOP — do not delete anything.

- [ ] **Step 2: Remove the business-repo plugin copy and commit**

Run:
```bash
cd e:/LBS-FramWare && git rm -r plugins/project-ops && git commit -m "chore: remove project-ops copy (migrated to local-marketplace repo)

Co-Authored-By: Claude <noreply@anthropic.com>"
```
Expected: commit succeeds; `e:/LBS-FramWare/plugins/` is gone (or empty). If `plugins/` held only project-ops, the directory disappears.

- [ ] **Step 3: Remove the hand-installed global github-workspace copy**

Run:
```bash
rm -rf "C:/Users/24160/.claude/skills/github-workspace" && echo "removed global github-workspace"
```
Expected: `removed global github-workspace`

- [ ] **Step 4: Confirm global project-memory is intentionally kept**

Run:
```bash
ls -d "C:/Users/24160/.claude/skills/project-memory" && echo "KEPT (intentional — current session depends on it; remove only after user confirms marketplace version works)"
```
Expected: the directory still exists + the KEPT message. (No deletion — this is the spec-mandated deferral.)

- [ ] **Step 5: Final state report**

Report: business-repo copy removed (LBS-FramWare commit SHA), global github-workspace removed, global project-memory kept pending user decision. Single source of truth = `e:/claude-marketplace` + installed cache. No commit in the marketplace repo for this task (cleanup is external to it).

---

## Self-Review

**1. Spec coverage** (checked against `2026-07-13-claude-marketplace-design.md`):
- §1/§2 standalone repo, official layout, local-only → Task 1.
- §3 install-cache fact / `${CLAUDE_PLUGIN_ROOT}` → Tasks 3, 4, 6.
- §4 repo structure → Tasks 1-2.
- §5.1 unified variable → Tasks 3 (github-workspace), 4 (project-memory).
- §5.2 not-substituted degradation → Task 3 Step 1 (SKILL.md degradation rule).
- §5.3 consumer CLAUDE.md opening rule references skill name, no path → Task 4 Step 3 (confirm; already satisfied by injected block).
- §6.1 migration → Task 2.
- §6.2 cleanup (business plugins/ + global github-workspace deleted, global project-memory kept) → Task 7.
- §6.3 consumer flow → documented in Task 1/5 READMEs; exercised in Task 6.
- §7 tests (38) + smoke → Tasks 2/5 (pytest), Task 6 (smoke).
- §8 unresolved (repo/market name, source format, old-pm fate, GitHub remote) → names fixed in Global Constraints (local-marketplace, ./plugins/project-ops); old-pm fate deferred in Task 7; GitHub remote out of scope (YAGNI per §7).
- All covered.

**2. Placeholder scan:** No TBD/TODO. Every edit step shows exact before/after text. Verification steps have concrete expected output. No "handle errors" hand-waving.

**3. Type/string consistency:** Market name `local-marketplace` used consistently (manifest, install commands, README, cleanup report). Plugin source `./plugins/project-ops` matches the verified official string format. The variable form `${CLAUDE_PLUGIN_ROOT}/skills/<skill>/scripts/<script>.py` is identical across Tasks 3-4 and matches the grep expectations in their verify steps. The grep in Task 3 Step 4 uses `<本 skill>` (angle-bracketed) so it cannot false-match the prose "本 skill 不自己写知识图谱" — noted inline. Test count 38 (11+27) consistent across Tasks 2, 5.

One item deferred by design (spec §8, not a gap): the final deletion of global `~/.claude/skills/project-memory/` awaits user confirmation after smoke — Task 7 Step 4 explicitly keeps it.
