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
