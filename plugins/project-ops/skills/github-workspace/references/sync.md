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
