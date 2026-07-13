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
- **要** → `git init` → `git checkout -b main` → 首次 add+commit → 引导用户在 GitHub 建远程仓并 `git remote add origin <url>` → **先 `git push -u origin main`（确保远程有 main,否则后续 pr.md 以 main 为 base 开 PR 会失败）** → 再跑 init_workspace.py 建 workspace 分支并推送。（建远程仓可用 GitHub MCP,见 references/pr.md 的 MCP 说明；MCP 不可用则让用户手动建仓贴 URL。）
- **不要** → 进入**仅记忆模式**：跳过所有 git 步骤,只保留步骤 1 建好的记忆系统。之后每任务完成只写记忆(见 references/sync.md 的仅记忆模式)。

### 4. 汇报
明确告知用户当前处于哪种模式：**git 模式**（workspace=<分支名>, 远程=<有/无>）或**仅记忆模式**。
