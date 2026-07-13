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
