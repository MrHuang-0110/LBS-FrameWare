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
