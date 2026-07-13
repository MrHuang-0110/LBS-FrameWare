# project-ops Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a distributable `project-ops` Claude Code plugin bundling two cooperating skills — `project-memory` (migrated) and `github-workspace` (new) — that provides manual init, an always-on memory base, workspace-branch git management, task-level commit/push, semantic memory sync, manual-gated PRs, and git-optional degradation.

**Architecture:** Thin-orchestration plugin. `github-workspace` wraps git commands and delegates memory writes to `project-memory`; GitHub MCP handles platform-side PR/issue only. Two Python helper scripts (`init_workspace.py`, `diff_summary.py`) carry the testable logic; everything else is skill instructions (SKILL.md + references). Core commit/push runs on local `git` so it never depends on MCP connectivity.

**Tech Stack:** Claude Code plugin format (`.claude-plugin/plugin.json` + `skills/`), Python 3 (stdlib only) for scripts, pytest for tests, git CLI, GitHub MCP (`github` server), memory MCP (`@modelcontextprotocol/server-memory`).

## Global Constraints

- Plugin source root: `plugins/project-ops/` inside this repo (developed + tested here; distributable via marketplace).
- Plugin manifest lives at `plugins/project-ops/.claude-plugin/plugin.json`; skills under `plugins/project-ops/skills/<skill-name>/`.
- Python scripts: **stdlib only**, no third-party deps; invoked as `python <script>` (Windows — `python`, not `python3`).
- Skill scripts must locate sibling scripts/references **relative to their own file** (`Path(__file__)`), NOT hardcoded `~/.claude/skills/...` paths — the plugin can be installed anywhere.
- Tests: pytest, hermetic (real temp dirs / temp git repos, `tmp_path` fixture), never touch real GitHub or real user `.memory/`.
- Five ironclad rules from the spec, enforced in skill text: (1) manual init only, (2) memory always-on base, (3) main protected — auto only to workspace, PR/merge require explicit user command, (4) semantic sync — write memory only after push succeeds, with real commit SHA, (5) never touch/print PAT.
- Default workspace branch name: `workspace`.
- All commits in this plan end with the `Co-Authored-By: Claude <noreply@anthropic.com>` trailer.

---

### Task 1: Plugin scaffold + manifest

**Files:**
- Create: `plugins/project-ops/.claude-plugin/plugin.json`
- Create: `plugins/project-ops/.claude-plugin/marketplace.json`
- Create: `plugins/project-ops/README.md`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: plugin root `plugins/project-ops/` with a valid manifest that Claude Code can load; `skills/` subdir will be populated by later tasks.

- [ ] **Step 1: Create the plugin manifest**

Create `plugins/project-ops/.claude-plugin/plugin.json`:

```json
{
  "name": "project-ops",
  "version": "0.1.0",
  "description": "Manual-init project operations: always-on knowledge-graph memory plus git workspace-branch management with semantic memory sync and manual-gated PRs",
  "author": {
    "name": "LBS Dev"
  }
}
```

- [ ] **Step 2: Create a local marketplace descriptor**

Create `plugins/project-ops/.claude-plugin/marketplace.json` (lets the plugin be installed from this repo path):

```json
{
  "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
  "name": "project-ops-local",
  "description": "Local marketplace for the project-ops plugin",
  "owner": {
    "name": "LBS Dev"
  },
  "plugins": [
    {
      "name": "project-ops",
      "description": "Always-on project memory + git workspace management with semantic sync",
      "author": { "name": "LBS Dev" },
      "category": "productivity",
      "source": {
        "source": "local",
        "path": "."
      }
    }
  ]
}
```

- [ ] **Step 3: Create README with install instructions**

Create `plugins/project-ops/README.md`:

```markdown
# project-ops

Claude Code plugin bundling two cooperating skills:

- **project-memory** — per-project knowledge-graph memory (MCP server-memory). Always-on base.
- **github-workspace** — git workspace-branch management: task-level commit/push, semantic
  memory sync (write memory only after push succeeds), manual-gated PRs, git-optional degradation.

## Install (local, during development)

From the repo root:

    /plugin marketplace add plugins/project-ops
    /plugin install project-ops@project-ops-local

Restart the session if prompted (MCP/skill changes take effect on restart).

## Usage

Initialization is **manual** — trigger the github-workspace skill's init flow explicitly.
See `skills/github-workspace/SKILL.md` for the full flow and the five ironclad rules.
```

- [ ] **Step 4: Verify the manifest is valid JSON**

Run: `python -c "import json,pathlib; [json.loads(pathlib.Path(p).read_text(encoding='utf-8')) for p in ['plugins/project-ops/.claude-plugin/plugin.json','plugins/project-ops/.claude-plugin/marketplace.json']]; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add plugins/project-ops/.claude-plugin/ plugins/project-ops/README.md
git commit -m "feat(project-ops): plugin scaffold + manifest

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Migrate project-memory skill into the plugin

**Files:**
- Create: `plugins/project-ops/skills/project-memory/SKILL.md` (copied from `C:/Users/24160/.claude/skills/project-memory/SKILL.md`)
- Create: `plugins/project-ops/skills/project-memory/references/{schema,setup,workflows}.md` (copied)
- Create: `plugins/project-ops/skills/project-memory/scripts/{build_index,check_memory_path,encode_project_path,migrate_md_to_graph}.py` (copied)
- Create: `plugins/project-ops/skills/project-memory/scripts/tests/test_*.py` (copied)

**Interfaces:**
- Consumes: Task 1 plugin root.
- Produces: `skills/project-memory/` inside the plugin, with references that no longer hardcode `~/.claude/skills/project-memory/...`. `github-workspace` (Task 6-8) will point users at this skill for memory writes.

- [ ] **Step 1: Copy the skill tree into the plugin**

Run (Git Bash):
```bash
mkdir -p plugins/project-ops/skills/project-memory
cp -r "C:/Users/24160/.claude/skills/project-memory/SKILL.md" plugins/project-ops/skills/project-memory/
cp -r "C:/Users/24160/.claude/skills/project-memory/references" plugins/project-ops/skills/project-memory/
cp -r "C:/Users/24160/.claude/skills/project-memory/scripts" plugins/project-ops/skills/project-memory/
```

- [ ] **Step 2: Remove copied caches**

Run:
```bash
find plugins/project-ops/skills/project-memory -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; \
find plugins/project-ops/skills/project-memory -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null; \
echo done
```
Expected: `done`

- [ ] **Step 3: Rewrite hardcoded skill paths in references**

The copied `references/setup.md` and `references/workflows.md` reference `python ~/.claude/skills/project-memory/scripts/<x>.py`. Inside a plugin the skill is no longer at that path. Replace every occurrence of the literal prefix

`~/.claude/skills/project-memory/scripts/`

with

`<project-memory skill scripts dir>/`

and add, at the top of both files under a `> Note:` line, this clarification:

```markdown
> Note: `<project-memory skill scripts dir>` = the `scripts/` folder next to this skill's SKILL.md.
> When invoking, use the actual path to this skill inside the installed plugin
> (e.g. `plugins/project-ops/skills/project-memory/scripts/` in the source repo, or the
> installed plugin cache path). Do not use the old `~/.claude/skills/project-memory/...` path.
```

Use search-and-replace across `plugins/project-ops/skills/project-memory/references/setup.md` and `.../workflows.md`. Verify none remain:

Run: `grep -rn "~/.claude/skills/project-memory" plugins/project-ops/skills/project-memory/ || echo "NONE REMAIN"`
Expected: `NONE REMAIN`

- [ ] **Step 4: Run the migrated skill's own script tests**

Run: `cd plugins/project-ops/skills/project-memory && python -m pytest scripts/tests/ -q; cd -`
Expected: all tests PASS (these are the skill's existing, self-contained tests — copying must not break them).

- [ ] **Step 5: Commit**

```bash
git add plugins/project-ops/skills/project-memory/
git commit -m "feat(project-ops): migrate project-memory skill into plugin

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: `diff_summary.py` — change-summary generator

**Files:**
- Create: `plugins/project-ops/skills/github-workspace/scripts/diff_summary.py`
- Test: `plugins/project-ops/skills/github-workspace/scripts/tests/test_diff_summary.py`

**Interfaces:**
- Consumes: nothing external (pure parsing + optional git call in `main`).
- Produces:
  - `parse_numstat(text: str) -> dict` returning `{"files": int, "insertions": int, "deletions": int, "paths": list[str]}`. Binary files show as `-`/`-` in numstat; count them as files with 0 insertions/deletions.
  - `top_modules(paths: list[str], limit: int = 3) -> list[str]` — top-level path segment of each path (or `"(root)"` for root files), deduped, most-frequent first, capped at `limit`.
  - `format_summary(stat: dict, modules: list[str]) -> str` — one-line summary, e.g. `"3 files, +42/-7 (backend, gui)"`.
  - `main()` — runs `git diff --cached --numstat`, prints `format_summary(...)`.

- [ ] **Step 1: Write the failing tests**

Create `plugins/project-ops/skills/github-workspace/scripts/tests/test_diff_summary.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import diff_summary as ds


def test_parse_numstat_counts_files_and_lines():
    text = "10\t2\tsrc/a.py\n5\t0\tsrc/b.py\n"
    stat = ds.parse_numstat(text)
    assert stat["files"] == 2
    assert stat["insertions"] == 15
    assert stat["deletions"] == 2
    assert stat["paths"] == ["src/a.py", "src/b.py"]


def test_parse_numstat_handles_binary_dashes():
    text = "-\t-\tassets/logo.png\n3\t1\tREADME.md\n"
    stat = ds.parse_numstat(text)
    assert stat["files"] == 2
    assert stat["insertions"] == 3
    assert stat["deletions"] == 1


def test_parse_numstat_empty():
    stat = ds.parse_numstat("")
    assert stat == {"files": 0, "insertions": 0, "deletions": 0, "paths": []}


def test_top_modules_dedupes_and_ranks():
    paths = ["src/gui/a.py", "src/gui/b.py", "src/backend/c.py", "README.md"]
    mods = ds.top_modules(paths, limit=3)
    assert mods[0] == "src"  # most frequent top-level segment
    assert "(root)" in mods


def test_format_summary_shape():
    stat = {"files": 3, "insertions": 42, "deletions": 7, "paths": []}
    out = ds.format_summary(stat, ["backend", "gui"])
    assert out == "3 files, +42/-7 (backend, gui)"


def test_format_summary_no_modules():
    stat = {"files": 1, "insertions": 1, "deletions": 0, "paths": []}
    out = ds.format_summary(stat, [])
    assert out == "1 file, +1/-0"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd plugins/project-ops/skills/github-workspace/scripts && python -m pytest tests/test_diff_summary.py -q; cd -`
Expected: FAIL — `ModuleNotFoundError: No module named 'diff_summary'`

- [ ] **Step 3: Write the implementation**

Create `plugins/project-ops/skills/github-workspace/scripts/diff_summary.py`:

```python
"""Generate a one-line summary of staged git changes.

Used by github-workspace to build commit messages and memory-write summaries.
Parsing is separated from git invocation so it is unit-testable.
"""
import subprocess
import sys
from collections import Counter


def parse_numstat(text):
    """Parse `git diff --numstat` output into a stat dict.

    Binary files appear as '-\t-\tpath' and count as a changed file with 0/0.
    """
    files = 0
    insertions = 0
    deletions = 0
    paths = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        add, delete, path = parts[0], parts[1], parts[2]
        files += 1
        if add != "-":
            insertions += int(add)
        if delete != "-":
            deletions += int(delete)
        paths.append(path)
    return {"files": files, "insertions": insertions, "deletions": deletions, "paths": paths}


def top_modules(paths, limit=3):
    """Top-level path segment per file (root files -> '(root)'), ranked by frequency."""
    segments = []
    for p in paths:
        norm = p.replace("\\", "/")
        head = norm.split("/", 1)
        segments.append(head[0] if len(head) > 1 else "(root)")
    ranked = [seg for seg, _ in Counter(segments).most_common()]
    return ranked[:limit]


def format_summary(stat, modules):
    """One-line summary, e.g. '3 files, +42/-7 (backend, gui)'."""
    noun = "file" if stat["files"] == 1 else "files"
    base = "{n} {noun}, +{ins}/-{dels}".format(
        n=stat["files"], noun=noun, ins=stat["insertions"], dels=stat["deletions"]
    )
    if modules:
        base += " (" + ", ".join(modules) + ")"
    return base


def main():
    proc = subprocess.run(
        ["git", "diff", "--cached", "--numstat"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        return 1
    stat = parse_numstat(proc.stdout)
    print(format_summary(stat, top_modules(stat["paths"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd plugins/project-ops/skills/github-workspace/scripts && python -m pytest tests/test_diff_summary.py -q; cd -`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add plugins/project-ops/skills/github-workspace/scripts/diff_summary.py plugins/project-ops/skills/github-workspace/scripts/tests/test_diff_summary.py
git commit -m "feat(github-workspace): diff_summary.py change-summary generator

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: `init_workspace.py` — idempotent workspace-branch init

**Files:**
- Create: `plugins/project-ops/skills/github-workspace/scripts/init_workspace.py`
- Test: `plugins/project-ops/skills/github-workspace/scripts/tests/test_init_workspace.py`

**Interfaces:**
- Consumes: nothing external (wraps git via subprocess against a caller-supplied `cwd`).
- Produces:
  - `run_git(args: list[str], cwd) -> subprocess.CompletedProcess` — thin wrapper, `capture_output=True, text=True`.
  - `worktree_clean(cwd) -> bool` — True iff `git status --porcelain` is empty.
  - `local_branch_exists(name, cwd) -> bool`
  - `remote_branch_exists(name, remote, cwd) -> bool` — checks `git ls-remote --heads <remote> <name>`; returns False if no remote.
  - `init_workspace(branch="workspace", main="main", remote="origin", cwd=None) -> dict` returning `{"action": "created"|"reused-local"|"reused-remote", "branch": name, "pushed": bool}`. Raises `RuntimeError("dirty worktree")` if worktree is dirty. Pushes with `-u` when a remote named `remote` exists; sets `pushed` accordingly.

- [ ] **Step 1: Write the failing tests**

Create `plugins/project-ops/skills/github-workspace/scripts/tests/test_init_workspace.py`:

```python
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import init_workspace as iw


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    """A git repo on 'main' with one commit and a bare 'origin' remote."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(origin)], check=True, capture_output=True)
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init")
    _git(work, "checkout", "-b", "main")
    _git(work, "config", "user.email", "t@t.t")
    _git(work, "config", "user.name", "t")
    (work / "f.txt").write_text("hi", encoding="utf-8")
    _git(work, "add", ".")
    _git(work, "commit", "-m", "init")
    _git(work, "remote", "add", "origin", str(origin))
    _git(work, "push", "-u", "origin", "main")
    return work


def test_creates_workspace_from_main(repo):
    result = iw.init_workspace(cwd=repo)
    assert result["action"] == "created"
    assert result["branch"] == "workspace"
    assert result["pushed"] is True
    assert iw.local_branch_exists("workspace", repo)
    assert iw.remote_branch_exists("workspace", "origin", repo)


def test_reuses_existing_local_branch(repo):
    _git(repo, "branch", "workspace")
    result = iw.init_workspace(cwd=repo)
    assert result["action"] == "reused-local"


def test_reuses_existing_remote_branch(repo):
    # create + push workspace, then delete it locally so only remote has it
    _git(repo, "checkout", "-b", "workspace")
    _git(repo, "push", "-u", "origin", "workspace")
    _git(repo, "checkout", "main")
    _git(repo, "branch", "-D", "workspace")
    result = iw.init_workspace(cwd=repo)
    assert result["action"] == "reused-remote"
    assert iw.local_branch_exists("workspace", repo)


def test_rejects_dirty_worktree(repo):
    (repo / "dirty.txt").write_text("x", encoding="utf-8")
    with pytest.raises(RuntimeError, match="dirty"):
        iw.init_workspace(cwd=repo)


def test_worktree_clean_detects_state(repo):
    assert iw.worktree_clean(repo) is True
    (repo / "dirty.txt").write_text("x", encoding="utf-8")
    assert iw.worktree_clean(repo) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd plugins/project-ops/skills/github-workspace/scripts && python -m pytest tests/test_init_workspace.py -q; cd -`
Expected: FAIL — `ModuleNotFoundError: No module named 'init_workspace'`

- [ ] **Step 3: Write the implementation**

Create `plugins/project-ops/skills/github-workspace/scripts/init_workspace.py`:

```python
"""Idempotently create or reuse the workspace branch and push it with upstream.

Pure git-CLI wrapper; all functions take an explicit cwd so they are testable
against a temp repo. No GitHub MCP dependency — core git only.
"""
import argparse
import subprocess
import sys


def run_git(args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def worktree_clean(cwd=None):
    proc = run_git(["status", "--porcelain"], cwd=cwd)
    return proc.returncode == 0 and proc.stdout.strip() == ""


def local_branch_exists(name, cwd=None):
    proc = run_git(["rev-parse", "--verify", "--quiet", "refs/heads/" + name], cwd=cwd)
    return proc.returncode == 0


def remote_branch_exists(name, remote="origin", cwd=None):
    if not _remote_exists(remote, cwd=cwd):
        return False
    proc = run_git(["ls-remote", "--heads", remote, name], cwd=cwd)
    return proc.returncode == 0 and proc.stdout.strip() != ""


def _remote_exists(remote, cwd=None):
    proc = run_git(["remote"], cwd=cwd)
    remotes = proc.stdout.split()
    return remote in remotes


def init_workspace(branch="workspace", main="main", remote="origin", cwd=None):
    if not worktree_clean(cwd=cwd):
        raise RuntimeError("dirty worktree: commit or stash changes before init")

    has_remote = _remote_exists(remote, cwd=cwd)

    if local_branch_exists(branch, cwd=cwd):
        run_git(["checkout", branch], cwd=cwd)
        action = "reused-local"
    elif remote_branch_exists(branch, remote, cwd=cwd):
        run_git(["checkout", "-b", branch, remote + "/" + branch], cwd=cwd)
        action = "reused-remote"
    else:
        run_git(["checkout", "-b", branch, main], cwd=cwd)
        action = "created"

    pushed = False
    if has_remote:
        proc = run_git(["push", "-u", remote, branch], cwd=cwd)
        pushed = proc.returncode == 0

    return {"action": action, "branch": branch, "pushed": pushed}


def main():
    parser = argparse.ArgumentParser(description="Init/reuse the workspace branch.")
    parser.add_argument("--branch", default="workspace")
    parser.add_argument("--main", default="main")
    parser.add_argument("--remote", default="origin")
    args = parser.parse_args()
    try:
        result = init_workspace(branch=args.branch, main=args.main, remote=args.remote)
    except RuntimeError as e:
        sys.stderr.write(str(e) + "\n")
        return 1
    print("{action}: {branch} (pushed={pushed})".format(**result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd plugins/project-ops/skills/github-workspace/scripts && python -m pytest tests/test_init_workspace.py -q; cd -`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add plugins/project-ops/skills/github-workspace/scripts/init_workspace.py plugins/project-ops/skills/github-workspace/scripts/tests/test_init_workspace.py
git commit -m "feat(github-workspace): init_workspace.py idempotent branch init

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: github-workspace SKILL.md

**Files:**
- Create: `plugins/project-ops/skills/github-workspace/SKILL.md`

**Interfaces:**
- Consumes: `scripts/init_workspace.py` (Task 4), `scripts/diff_summary.py` (Task 3); sibling skill `project-memory` (Task 2) for memory writes.
- Produces: the skill entry point — trigger conditions, the five ironclad rules, flow overview, and pointers to `references/{init,sync,pr}.md` (Tasks 6-8).

- [ ] **Step 1: Write SKILL.md**

Create `plugins/project-ops/skills/github-workspace/SKILL.md`:

```markdown
---
name: github-workspace
description: Use when manually initializing project ops in a repo, or after completing a task that changed project files — manages a workspace git branch with task-level commit/push, writes a change summary to project-memory only after push succeeds, and opens PRs to main only on explicit user command. Degrades to memory-only when git/GitHub is not used.
---

# github-workspace

薄编排层 skill：管理 workspace 分支的任务级 commit/push，push 成功后调用 **project-memory** 写改动摘要，手动门控开 PR。核心 git 走命令行，不依赖 GitHub MCP 连接状态；PR/平台操作走 GitHub MCP。

## 何时触发
- **手动初始化**：用户显式要求「初始化项目管理 / init project-ops」时 → 走 references/init.md。
- **任务完成后**：一个有意义的任务/修改完成 → 走 references/sync.md（commit→push→写记忆）。
- **开 PR / 合并 main**：仅当用户显式说「开 PR」「合并到 main」→ 走 references/pr.md。

## 五条铁律（严格遵守）
1. **手动初始化**：绝不自动初始化,等用户显式触发。
2. **记忆底座**：项目记忆系统总是启用,与 git 有无无关。初始化必定先建记忆。
3. **main 保护**：自动流程只提交/推送到 workspace 分支；开 PR 与合并 main 必须用户显式发话,skill 不主动发起、不自动合并、不自动 `--force`。
4. **语义同步**：git 模式下**只有 push 成功后**才写记忆,且把真实 commit SHA 写进去；push 失败绝不写记忆。
5. **凭证安全**：不读取、不打印 PAT 或任何凭证。

## 脚本（相对本 skill 定位,勿硬编码全局路径）
- 初始化 workspace 分支：`python <本 skill>/scripts/init_workspace.py [--branch workspace] [--main main] [--remote origin]`
- 生成改动摘要：`python <本 skill>/scripts/diff_summary.py`（读已暂存改动,输出一行摘要）

## 与 project-memory 的协作
本 skill 不自己写知识图谱。需要写记忆时,按 **project-memory skill** 的 references/workflows.md「写入」流程执行（progress 类更新既有实体、写入后重建 index.md）。

## 参考
- 初始化 + git 分流：references/init.md
- 任务同步事务（commit→push→写记忆）：references/sync.md
- 开 PR 到 main（GitHub MCP + 降级）：references/pr.md
```

- [ ] **Step 2: Verify frontmatter parses**

Run: `python -c "import pathlib,re; t=pathlib.Path('plugins/project-ops/skills/github-workspace/SKILL.md').read_text(encoding='utf-8'); assert t.startswith('---'); assert 'name: github-workspace' in t; assert t.count('---')>=2; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add plugins/project-ops/skills/github-workspace/SKILL.md
git commit -m "feat(github-workspace): SKILL.md entry point + five rules

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: references/init.md — init + git-optional degradation

**Files:**
- Create: `plugins/project-ops/skills/github-workspace/references/init.md`

**Interfaces:**
- Consumes: `init_workspace.py`; project-memory setup flow.
- Produces: the manual-init procedure with the git-detection branch (has git / no git → ask / memory-only).

- [ ] **Step 1: Write init.md**

Create `plugins/project-ops/skills/github-workspace/references/init.md`:

```markdown
# 初始化流程（手动触发）

铁律：不自动初始化。记忆总是先建（底座）。git 是可选增强层。

## 步骤

### 1. 总是初始化项目记忆系统
按 **project-memory skill** 的 references/setup.md 执行 Step 0–9（依赖预检、写 .mcp.json、建 .memory/、注入 CLAUDE.md 开场规则、重启后验证、迁移旧记忆、生成 index.md）。此步与 git 无关,必做。

### 2. 检测 git 仓库
跑 `git rev-parse --is-inside-work-tree`（在项目根）。
- 输出 `true` → **有 git**,进入步骤 3a。
- 非零/报错 → **无 git**,进入步骤 3b。

### 3a. 有 git → 建/复用 workspace 分支
1. 先确认工作区干净：`git status --porcelain` 为空。脏 → 提示用户先 commit/stash,**不擅自处理**,停在此步。
2. 跑 `python <本 skill>/scripts/init_workspace.py`。
   - 输出 `created:` / `reused-local:` / `reused-remote:` 之一,并带 `pushed=True/False`。
3. 若脚本报 `dirty worktree` → 回到 1 提示用户。
4. 若无远程(`pushed=False`)→ 告知用户「本地 workspace 已就绪,尚未推送到远程；配好 origin 后首次 sync 会推送」。
5. 若 workspace 落后 main 较多（可选检查 `git rev-list --count workspace..main`,>0 即落后）→ 提示用户是否先同步,**合并方向决策归用户**,不自动 rebase。

### 3b. 无 git → 询问是否推送 GitHub
问用户：「当前目录不是 git 仓库,要把它推送到 GitHub 吗？」
- **要** → `git init` → `git checkout -b main` → 首次 add+commit → 引导用户在 GitHub 建远程仓并 `git remote add origin <url>` → 跑 init_workspace.py 建 workspace 分支并推送。（建远程仓可用 GitHub MCP,见 references/pr.md 的 MCP 说明；MCP 不可用则让用户手动建仓贴 URL。）
- **不要** → 进入**仅记忆模式**：跳过所有 git 步骤,只保留步骤 1 建好的记忆系统。之后每任务完成只写记忆(见 references/sync.md 的仅记忆模式)。

### 4. 汇报
明确告知用户当前处于哪种模式：**git 模式**（workspace=<分支名>, 远程=<有/无>）或**仅记忆模式**。
```

- [ ] **Step 2: Commit**

```bash
git add plugins/project-ops/skills/github-workspace/references/init.md
git commit -m "docs(github-workspace): init.md + git-optional degradation flow

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: references/sync.md — task sync transaction (commit→push→memory)

**Files:**
- Create: `plugins/project-ops/skills/github-workspace/references/sync.md`

**Interfaces:**
- Consumes: `diff_summary.py`; project-memory write flow.
- Produces: the strict-order transaction enforcing the semantic-sync rule.

- [ ] **Step 1: Write sync.md**

Create `plugins/project-ops/skills/github-workspace/references/sync.md`:

```markdown
# 任务同步事务（每个任务完成后）

铁律 · 语义同步：**push 成功才写记忆,带真实 commit SHA；push 失败不写。**

## git 模式（严格按序）

### 1. 检查有无改动
`git status --porcelain`。为空 → 无改动,**不做空 commit**,告知用户后结束。

### 2. 暂存 + 生成摘要
1. `git add -A`（记忆文件 .memory/ 已被 .gitignore 排除,不会误入；若某项目未排除,按 project-memory 约定不主动提交记忆文件）。
2. 跑 `python <本 skill>/scripts/diff_summary.py` 得到一行摘要,如 `3 files, +42/-7 (backend, gui)`。

### 3. commit
用摘要 + 任务描述做 message：
`git commit -m "<type>(<scope>): <任务简述>"`（正文可附 diff_summary 摘要行）。

### 4. push（关键闸门）
`git push`（首次或无 upstream 时用 `git push -u origin <workspace 分支>`）。
- **非 fast-forward 被拒** → 提示用户先 `git pull --rebase`；**绝不自动 `--force`**。停下等用户。
- **网络/认证失败** → 原样呈现 git 报错,停下。

### 5. 判定 push 结果
- **push 成功** → 记下新 commit SHA：`git rev-parse HEAD`,进入步骤 6。
- **push 失败** → **不写记忆**,结束(已在步骤 4 报错)。

### 6. 写记忆（仅 push 成功后）
按 **project-memory skill** references/workflows.md「写入」流程,更新 progress 类实体（**更新既有,不堆叠新实体**）：
- observation 带 `YYYY-MM-DD:` 前缀,内容含：任务简述、分支、**commit SHA**、diff_summary 摘要。
- 写入后**重建 index.md**（跑 project-memory 的 build_index.py）。

### 7. 记忆写入失败处理
此时 push 已成功、代码安全。按 project-memory 运行时自愈重试一次；仍失败 → 明确告知用户「代码已 push(<SHA>),但记忆未写入」,不假装成功。

## 仅记忆模式（无 git）
每任务完成 → 直接按步骤 6 写记忆(去掉分支/SHA,记任务简述与改了什么)。无任何 git 步骤。
```

- [ ] **Step 2: Commit**

```bash
git add plugins/project-ops/skills/github-workspace/references/sync.md
git commit -m "docs(github-workspace): sync.md semantic-sync transaction

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8: references/pr.md — open PR to main (GitHub MCP + degradation)

**Files:**
- Create: `plugins/project-ops/skills/github-workspace/references/pr.md`

**Interfaces:**
- Consumes: GitHub MCP (`github` server); workspace branch state.
- Produces: the manual-gated PR procedure with MCP-unavailable fallback.

- [ ] **Step 1: Write pr.md**

Create `plugins/project-ops/skills/github-workspace/references/pr.md`:

```markdown
# 开 PR 到 main（手动门控）

铁律 · main 保护：仅当用户**显式**要求「开 PR」「合并到 main」时执行。skill 不主动发起、不自动合并。

## 前置
- 确认当前 workspace 分支已 push 到远程（`git rev-parse --abbrev-ref HEAD` 得分支名；`git ls-remote --heads origin <分支>` 非空）。未推送 → 先按 sync.md 推送。
- 确定仓库 owner/repo：从 `git remote get-url origin` 解析。

## 开 PR（GitHub MCP 优先）
1. 用 GitHub MCP（`github` 服务）创建 PR：base=`main`, head=`<workspace 分支>`, title/body 由用户意图 + 最近改动摘要生成。
   - 通过 ToolSearch 找到 GitHub MCP 的 create-PR 工具再调用。
2. 返回 PR 链接给用户。

## MCP 不可用降级
若 `github` MCP 未连接/调用失败：
- **不卡死**。给出网页建 PR 链接供用户点击：
  `https://github.com/<owner>/<repo>/compare/main...<workspace 分支>?expand=1`
- 告知用户「GitHub MCP 未连接,已改用网页链接建 PR」。

## 合并
合并到 main **同样等用户显式确认**。用户确认后可经 GitHub MCP 合并,或提示用户在网页合并。skill 不自动合并、不自动删分支。

## 凭证
全程不读取、不打印 PAT。
```

- [ ] **Step 2: Commit**

```bash
git add plugins/project-ops/skills/github-workspace/references/pr.md
git commit -m "docs(github-workspace): pr.md manual-gated PR + MCP fallback

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 9: Full-plugin verification + top-level docs

**Files:**
- Create: `plugins/project-ops/skills/github-workspace/scripts/tests/__init__.py` (empty, ensures pytest discovery)
- Modify: `docs/superpowers/specs/2026-07-13-project-ops-plugin-design.md:...` (append an "Implemented" note referencing the plan) — optional, only if the spec has a status field to update.

**Interfaces:**
- Consumes: all prior tasks.
- Produces: a green full-plugin test run and a documented, loadable plugin.

- [ ] **Step 1: Ensure test discovery file exists**

Create empty `plugins/project-ops/skills/github-workspace/scripts/tests/__init__.py` (touch).

Run: `python -c "import pathlib; pathlib.Path('plugins/project-ops/skills/github-workspace/scripts/tests/__init__.py').touch(); print('OK')"`
Expected: `OK`

- [ ] **Step 2: Run the whole plugin's script tests**

Run: `python -m pytest plugins/project-ops/skills/github-workspace/scripts/tests/ plugins/project-ops/skills/project-memory/scripts/tests/ -q`
Expected: all PASS (github-workspace: 11 tests; project-memory: its existing suite).

- [ ] **Step 3: Verify no stale global-path references remain anywhere in the plugin**

Run: `grep -rn "~/.claude/skills" plugins/project-ops/ || echo "NONE REMAIN"`
Expected: `NONE REMAIN`

- [ ] **Step 4: Verify plugin structure completeness**

Run:
```bash
python -c "
import pathlib
root = pathlib.Path('plugins/project-ops')
required = [
    '.claude-plugin/plugin.json',
    '.claude-plugin/marketplace.json',
    'skills/project-memory/SKILL.md',
    'skills/github-workspace/SKILL.md',
    'skills/github-workspace/references/init.md',
    'skills/github-workspace/references/sync.md',
    'skills/github-workspace/references/pr.md',
    'skills/github-workspace/scripts/init_workspace.py',
    'skills/github-workspace/scripts/diff_summary.py',
]
missing = [r for r in required if not (root / r).exists()]
print('MISSING:', missing) if missing else print('ALL PRESENT')
"
```
Expected: `ALL PRESENT`

- [ ] **Step 5: Commit**

```bash
git add plugins/project-ops/
git commit -m "test(project-ops): full-plugin verification + test discovery

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage** (checked against `2026-07-13-project-ops-plugin-design.md`):
- §1/§2 定位、记忆底座 → Task 6 (init always builds memory first), rule 2 in Task 5.
- §3 方案 A 薄编排 → Tasks 3-8 (scripts + delegation to project-memory).
- §4 交付结构 (plugin + two skills) → Tasks 1, 2, 5-8.
- §5.1 初始化 + git 分流 → Task 6.
- §5.2 同步事务 (语义同步) → Task 7.
- §5.3 开 PR 手动门控 → Task 8.
- §6 五条铁律 → Task 5 SKILL.md + reinforced in Tasks 6-8.
- §7 错误处理 (push 失败/MCP 断连/落后/记忆失败/脏区/凭证) → Tasks 6 (dirty, behind), 7 (push fail, memory fail), 8 (MCP fallback, PAT).
- §8 测试策略 → Tasks 3, 4 (unit tests), Task 9 (full run); checklist items live in the reference docs as procedural guards.
- All covered.

**2. Placeholder scan:** No TBD/TODO/"handle edge cases" left; every code step has full code; every reference doc is written out in full.

**3. Type consistency:** `parse_numstat` returns `{files, insertions, deletions, paths}` — used identically in `top_modules(stat["paths"])`, `format_summary(stat, ...)`, and tests. `init_workspace(...)` returns `{action, branch, pushed}` with actions `created|reused-local|reused-remote` — matches tests exactly. Script invocation paths consistently use `<本 skill>/scripts/...` relative form per Global Constraints.

One spec note deferred to execution (documented in spec §9, not a gap): exact plugin.json schema fields — Task 1 uses the verified `code-simplifier` plugin.json shape (name/version/description/author).
