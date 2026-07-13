# embedded-dev into claude-marketplace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge the existing `embedded-dev` plugin into the `claude-marketplace` repo as a second plugin, rename the marketplace to `hyw-claude-plugin`, and switch all docs to GitHub-source install — yielding one repo hosting two independently-installable plugins.

**Architecture:** Copy `E:/cmd/embedded-dev` into `e:/claude-marketplace/plugins/embedded-dev/`, delete its self-contained marketplace.json (root has the authoritative one), append an `embedded-dev` entry to the root manifest, rename the market `local-marketplace` → `hyw-claude-plugin` across the repo, and rewrite install docs to use the GitHub source `MrHuang-0110/claude-plugin`. No script or `.mcp.json` changes (no internal path deps).

**Tech Stack:** Claude Code plugin/marketplace format (JSON manifests), git, Markdown docs. No Python tests (embedded-dev is agents/commands/skills).

## Global Constraints

- Work repo: `e:/claude-marketplace` (existing local git repo; all commits go there via `git -C e:/claude-marketplace`).
- Source of embedded-dev: `E:/cmd/embedded-dev` (non-git; copy from here, exclude any `.git`/caches).
- Target: `e:/claude-marketplace/plugins/embedded-dev/`.
- Root manifest `e:/claude-marketplace/.claude-plugin/marketplace.json` must end with exactly TWO plugins: `project-ops` (source `./plugins/project-ops`) and `embedded-dev` (source `./plugins/embedded-dev`).
- Market `name` field: rename `local-marketplace` → `hyw-claude-plugin` (this is the `@name` in install commands).
- The embedded-dev plugin dir's `.claude-plugin/` must contain ONLY `plugin.json` (delete its `marketplace.json`).
- Install docs use GitHub source: `/plugin marketplace add MrHuang-0110/claude-plugin`; repo URL `https://github.com/MrHuang-0110/claude-plugin.git`.
- Install commands become `project-ops@hyw-claude-plugin` and `embedded-dev@hyw-claude-plugin`.
- Do NOT modify embedded-dev's `.mcp.json`, `scripts/check-deps.ps1`, `scripts/check-deps.sh`, agents, commands, or skills content (no internal path deps — verified).
- After completion, no file may reference the old market names `local-marketplace` or `embedded-dev-marketplace` (as a market name).
- Commit messages end with `Co-Authored-By: Claude <noreply@anthropic.com>`.
- Windows: `python`, Git Bash for the Bash tool, forward-slash paths.

---

### Task 1: Migrate embedded-dev into the repo + strip its marketplace.json

**Files:**
- Create: `e:/claude-marketplace/plugins/embedded-dev/` (copied tree from `E:/cmd/embedded-dev`)
- Delete: `e:/claude-marketplace/plugins/embedded-dev/.claude-plugin/marketplace.json` (stray, after copy)

**Interfaces:**
- Consumes: the source tree at `E:/cmd/embedded-dev`.
- Produces: `plugins/embedded-dev/` containing `.claude-plugin/plugin.json` (kept), `agents/` (4), `commands/` (6), `skills/` (2 dirs), `scripts/` (2), `.mcp.json`, `INSTALL.md`, `README.md` — and NO nested `marketplace.json`. Docs still contain old strings (fixed in Task 3).

- [ ] **Step 1: Copy the plugin tree (exclude .git)**

Run (Git Bash):
```bash
mkdir -p e:/claude-marketplace/plugins/embedded-dev
cp -r "E:/cmd/embedded-dev/." e:/claude-marketplace/plugins/embedded-dev/
rm -rf e:/claude-marketplace/plugins/embedded-dev/.git 2>/dev/null; echo copied
```
Expected: `copied`

- [ ] **Step 2: Delete the stray nested marketplace.json**

Run:
```bash
rm -f e:/claude-marketplace/plugins/embedded-dev/.claude-plugin/marketplace.json
ls e:/claude-marketplace/plugins/embedded-dev/.claude-plugin/
```
Expected: only `plugin.json` listed.

- [ ] **Step 3: Verify structure completeness**

Run:
```bash
cd e:/claude-marketplace && python -c "
import pathlib
root = pathlib.Path('plugins/embedded-dev')
required = [
    '.claude-plugin/plugin.json',
    '.mcp.json', 'INSTALL.md', 'README.md',
    'agents/embedded-architect.md', 'agents/embedded-reviewer.md',
    'agents/firmware-analyst.md', 'agents/serial-log-diagnostician.md',
    'commands/arch.md', 'commands/bug-hunt.md', 'commands/fetch-datasheet.md',
    'commands/plan.md', 'commands/req-analyze.md', 'commands/review.md',
    'scripts/check-deps.ps1', 'scripts/check-deps.sh',
    'skills/embedded-domain/SKILL.md', 'skills/web-device-inspect/SKILL.md',
]
missing = [r for r in required if not (root / r).exists()]
stray = (root / '.claude-plugin/marketplace.json').exists()
print('MISSING:', missing) if missing else print('ALL PRESENT')
print('STRAY marketplace.json still present!' if stray else 'STRAY REMOVED')
"
```
Expected: `ALL PRESENT` and `STRAY REMOVED`

- [ ] **Step 4: Commit**

```bash
git -C e:/claude-marketplace add -A && git -C e:/claude-marketplace commit -m "feat: migrate embedded-dev plugin into marketplace (strip nested manifest)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Rename market + append embedded-dev to root manifest

**Files:**
- Modify: `e:/claude-marketplace/.claude-plugin/marketplace.json`

**Interfaces:**
- Consumes: Task 1's migrated plugin dir; the metadata from embedded-dev's (now-deleted) marketplace.json, preserved below.
- Produces: a root manifest named `hyw-claude-plugin` with exactly 2 plugin entries (project-ops + embedded-dev), both with correct relative `source` paths.

- [ ] **Step 1: Rewrite the root manifest**

Replace the ENTIRE contents of `e:/claude-marketplace/.claude-plugin/marketplace.json` with:

```json
{
  "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
  "name": "hyw-claude-plugin",
  "description": "Personal Claude Code plugin marketplace — single source of truth for project-ops and embedded-dev",
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
    },
    {
      "name": "embedded-dev",
      "description": "嵌入式软件工程师开发套件：需求分析、系统架构、项目规划、代码审查、BUG 定位、芯片文档/设备 Web 数据抓取。面向 PikaPython/MicroPython、C/C++ 裸机/RTOS、串口/协议调试。",
      "author": { "name": "embedded-dev" },
      "category": "development",
      "keywords": ["embedded", "firmware", "pikapython", "micropython", "rtos", "uart", "debugging"],
      "source": "./plugins/embedded-dev"
    }
  ]
}
```

- [ ] **Step 2: Validate JSON + assert 2 plugins + correct name**

Run:
```bash
cd e:/claude-marketplace && python -c "
import json, pathlib
d = json.loads(pathlib.Path('.claude-plugin/marketplace.json').read_text(encoding='utf-8'))
assert d['name'] == 'hyw-claude-plugin', d['name']
names = [p['name'] for p in d['plugins']]
srcs = {p['name']: p['source'] for p in d['plugins']}
assert names == ['project-ops', 'embedded-dev'], names
assert srcs['project-ops'] == './plugins/project-ops', srcs
assert srcs['embedded-dev'] == './plugins/embedded-dev', srcs
print('OK: name=hyw-claude-plugin, plugins=', names)
"
```
Expected: `OK: name=hyw-claude-plugin, plugins= ['project-ops', 'embedded-dev']`

- [ ] **Step 3: Commit**

```bash
git -C e:/claude-marketplace add .claude-plugin/marketplace.json && git -C e:/claude-marketplace commit -m "feat: rename market to hyw-claude-plugin + add embedded-dev entry

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Rewrite all install docs (GitHub source + new market name)

**Files:**
- Modify: `e:/claude-marketplace/README.md`
- Modify: `e:/claude-marketplace/plugins/project-ops/README.md`
- Modify: `e:/claude-marketplace/plugins/embedded-dev/README.md`
- Modify: `e:/claude-marketplace/plugins/embedded-dev/INSTALL.md`

**Interfaces:**
- Consumes: Task 2's new market name `hyw-claude-plugin`.
- Produces: all docs referencing the GitHub source `MrHuang-0110/claude-plugin` and market `hyw-claude-plugin`; no doc references old market names `local-marketplace` or `embedded-dev-marketplace`.

- [ ] **Step 1: Rewrite the repo root README**

Replace the ENTIRE contents of `e:/claude-marketplace/README.md` with:

```markdown
# hyw-claude-plugin

Personal Claude Code plugin marketplace. Single source of truth for my plugins — install
from here so there is only ever one version.

## Plugins

- **project-ops** — always-on knowledge-graph project memory + git workspace-branch
  management (task-level commit/push, semantic memory sync, manual-gated PRs, git-optional).
- **embedded-dev** — embedded-software engineering kit: requirements analysis, architecture,
  planning, code review, bug hunting, datasheet/device-web fetching. For PikaPython/MicroPython,
  C/C++ bare-metal/RTOS, UART/protocol debugging.

## Use (per machine)

    /plugin marketplace add MrHuang-0110/claude-plugin

Then install whichever plugins you want (they are independent):

    /plugin install project-ops@hyw-claude-plugin
    /plugin install embedded-dev@hyw-claude-plugin

Restart the session when prompted. To pull updates later:

    /plugin marketplace update hyw-claude-plugin

Repo: https://github.com/MrHuang-0110/claude-plugin.git

## Adding a plugin

1. Create `plugins/<name>/` with a `.claude-plugin/plugin.json` and its content (skills/commands/agents).
2. Append an entry to `.claude-plugin/marketplace.json` `plugins[]` with `"source": "./plugins/<name>"`.
3. If a plugin has skills that invoke scripts, reference them via `${CLAUDE_PLUGIN_ROOT}/skills/<skill>/scripts/...`.
```

- [ ] **Step 2: Fix project-ops README install lines**

In `e:/claude-marketplace/plugins/project-ops/README.md`, replace these two lines:

```
    /plugin install project-ops@local-marketplace
```
→
```
    /plugin install project-ops@hyw-claude-plugin
```

and

```
Pull updates later with: `/plugin marketplace update local-marketplace`.
```
→
```
Pull updates later with: `/plugin marketplace update hyw-claude-plugin`.
```

Also, if the README's `marketplace add` line uses a local path (`e:/claude-marketplace`), replace it with `/plugin marketplace add MrHuang-0110/claude-plugin`. (Read the file first; update the add line to the GitHub source if present.)

- [ ] **Step 3: Rewrite embedded-dev README install section**

In `e:/claude-marketplace/plugins/embedded-dev/README.md`, replace the install block (currently referencing `E:\cmd\embedded-dev` at line ~31 and the "本地目录安装" section around lines 26-37) with:

```markdown
本插件通过 marketplace 安装（与 project-ops 同一个 marketplace，可各自独立安装）：

```
# 1. 添加 marketplace（GitHub 源，一次即可）
> /plugin marketplace add MrHuang-0110/claude-plugin

# 2. 安装本插件（提示选范围时选 user = 全局）
> /plugin install embedded-dev@hyw-claude-plugin
```

更新：`/plugin marketplace update hyw-claude-plugin`。仓库：https://github.com/MrHuang-0110/claude-plugin.git
```

(Read the file first to match the exact block; replace the old local-path install instructions with the above. Preserve the rest of the README's content about features/agents.)

- [ ] **Step 4: Rewrite embedded-dev INSTALL.md install + update lines**

In `e:/claude-marketplace/plugins/embedded-dev/INSTALL.md`:

(a) Replace the install block (lines ~11-14, the ```` ``` ```` fenced block containing `/plugin marketplace add E:\cmd\embedded-dev` and `/plugin install embedded-dev`) with:

```
claude
> /plugin marketplace add MrHuang-0110/claude-plugin   # 添加 marketplace（GitHub 源）
> /plugin install embedded-dev@hyw-claude-plugin        # 安装；提示选范围时选 user（用户级）
```

(b) Replace line ~19's uninstall/update line:
```
- 卸载 / 更新：`/plugin uninstall embedded-dev`、`/plugin marketplace update embedded-dev-marketplace`。
```
→
```
- 卸载 / 更新：`/plugin uninstall embedded-dev`、`/plugin marketplace update hyw-claude-plugin`。
```

(c) If any remaining line mentions copying `E:\cmd\embedded-dev` to another machine, replace that guidance with: "换机器：在新机器执行 `/plugin marketplace add MrHuang-0110/claude-plugin` 即可从 GitHub 拉取，无需拷目录。" (Read the file; update the machine-transfer note accordingly.)

- [ ] **Step 5: Verify no stale market names remain anywhere**

Run:
```bash
cd e:/claude-marketplace && grep -rn "local-marketplace\|embedded-dev-marketplace" . --include=*.json --include=*.md 2>/dev/null || echo "NONE REMAIN"
```
Expected: `NONE REMAIN`

- [ ] **Step 6: Verify no stale local paths remain in embedded-dev docs**

Run:
```bash
cd e:/claude-marketplace && grep -rn "E:\\\\cmd\\\\embedded-dev\|E:/cmd/embedded-dev" plugins/embedded-dev/ 2>/dev/null || echo "NONE REMAIN"
```
Expected: `NONE REMAIN`

- [ ] **Step 7: Commit**

```bash
git -C e:/claude-marketplace add -A && git -C e:/claude-marketplace commit -m "docs: GitHub-source install + hyw-claude-plugin market name across all READMEs

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Final verification + interactive smoke gate

**Files:**
- None (verification task).

**Interfaces:**
- Consumes: all prior tasks.
- Produces: confirmation the repo is internally consistent and both plugins install independently. This task's smoke sub-steps are run by the USER (interactive `/plugin` commands); the controller runs the static checks.

- [ ] **Step 1: Full static verification (controller-runnable)**

Run:
```bash
cd e:/claude-marketplace && python -c "
import json, pathlib
d = json.loads(pathlib.Path('.claude-plugin/marketplace.json').read_text(encoding='utf-8'))
assert d['name'] == 'hyw-claude-plugin'
assert [p['name'] for p in d['plugins']] == ['project-ops','embedded-dev']
for p in d['plugins']:
    src = pathlib.Path(p['source'])
    assert (src / '.claude-plugin/plugin.json').exists(), f'missing plugin.json for {p[\"name\"]}'
print('MANIFEST OK: 2 plugins, both plugin.json present')
"
grep -rn "local-marketplace\|embedded-dev-marketplace" . --include=*.json --include=*.md 2>/dev/null || echo "NO STALE MARKET NAMES"
test ! -f plugins/embedded-dev/.claude-plugin/marketplace.json && echo "NO STRAY EMBEDDED MANIFEST"
```
Expected: `MANIFEST OK: 2 plugins, both plugin.json present`, then `NO STALE MARKET NAMES`, then `NO STRAY EMBEDDED MANIFEST`.

- [ ] **Step 2: Confirm embedded-dev's untouched files are unchanged vs source**

Run:
```bash
diff -r "E:/cmd/embedded-dev/.mcp.json" "e:/claude-marketplace/plugins/embedded-dev/.mcp.json" && echo ".mcp.json IDENTICAL"
diff -r "E:/cmd/embedded-dev/scripts" "e:/claude-marketplace/plugins/embedded-dev/scripts" && echo "scripts IDENTICAL"
diff -r "E:/cmd/embedded-dev/agents" "e:/claude-marketplace/plugins/embedded-dev/agents" && echo "agents IDENTICAL"
diff -r "E:/cmd/embedded-dev/commands" "e:/claude-marketplace/plugins/embedded-dev/commands" && echo "commands IDENTICAL"
diff -r "E:/cmd/embedded-dev/skills" "e:/claude-marketplace/plugins/embedded-dev/skills" && echo "skills IDENTICAL"
```
Expected: five `... IDENTICAL` lines (these are the do-not-modify assets; confirms only manifest + docs changed).

- [ ] **Step 3: INTERACTIVE smoke (USER runs — controller cannot run /plugin)**

The user runs these in a Claude Code session (after the repo is pushed to GitHub, or against the local repo path for a pre-push check). Document expected results:

```
/plugin marketplace update hyw-claude-plugin      # if already added under old name, re-add: /plugin marketplace add MrHuang-0110/claude-plugin
/plugin install embedded-dev@hyw-claude-plugin
```
Expected: the marketplace lists TWO plugins (project-ops, embedded-dev); `embedded-dev` installs independently.

NOTE (record for the user): because the market name changed from `local-marketplace` → `hyw-claude-plugin`, any previously installed `project-ops@local-marketplace` references the OLD market name and must be re-added/reinstalled under the new name:
```
/plugin marketplace add MrHuang-0110/claude-plugin
/plugin install project-ops@hyw-claude-plugin
```

- [ ] **Step 4: Record smoke result**

State: static verification ✅ (manifest, no stale names, no stray, assets identical). Interactive smoke is user-run; record its outcome when the user reports it. No commit (verification only).

---

## Self-Review

**1. Spec coverage** (against `2026-07-13-embedded-dev-into-marketplace-design.md` + the rename/GitHub additions):
- §4/§5.1 migrate + strip nested marketplace.json → Task 1.
- §5.2 append embedded-dev to root manifest → Task 2 (+ rename, per added requirement).
- §5.3 update embedded-dev docs → Task 3 (+ GitHub source + market rename across ALL docs).
- §5.4 verification (JSON, 2 plugins, structure, no stale names, smoke) → Task 4 (+ Task 1 structure, Task 2/3 inline greps).
- §5.5 don't modify .mcp.json/scripts/agents/commands/skills → Global Constraints + Task 4 Step 2 `diff -r` proof.
- Added: market rename local-marketplace → hyw-claude-plugin → Tasks 2, 3; GitHub-source install → Task 3; re-add note for already-installed project-ops → Task 4 Step 3 note.
- All covered.

**2. Placeholder scan:** No TBD/TODO. Exact JSON/markdown content given for full-file rewrites; for in-place doc edits (project-ops README, embedded-dev README/INSTALL) the steps give exact old→new strings and instruct reading the file first to match surrounding context (these files have prose that must be preserved). Verification steps have concrete expected output.

**3. Consistency:** Market name `hyw-claude-plugin` used identically in manifest (Task 2), all install/update commands (Task 3), and verification asserts (Tasks 2, 4). Source paths `./plugins/project-ops` and `./plugins/embedded-dev` consistent. GitHub source `MrHuang-0110/claude-plugin` consistent across all docs. Plugin count (2) asserted in Tasks 2 and 4.

One item is user-gated by nature (spec §5.4 smoke): Task 4 Step 3 is interactive `/plugin` — the controller runs all static checks (Steps 1-2) and the user runs the smoke. Not a gap; it's the correct division for commands the controller can't execute.
