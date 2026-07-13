# Design: `project-ops` plugin

- 日期: 2026-07-13
- 状态: 已批准,待写实施计划
- 相关: [[project-memory skill]](2026-07-13-project-memory-skill-design.md)

## 1. 目标与定位

一个可分发到**任何项目**的 plugin,内含两个协作 skill,提供「手动初始化 → 之后自动按流程管理」的项目运维闭环。

核心理念:**记忆是底座(总是启用),git / GitHub 是可选增强层。**

- 手动启动初始化;初始化后按既定流程管理项目。
- 记忆系统永远初始化并启用,与 git 有无无关。
- 有 git 则启用 workspace 分支 + 任务级 commit/push;无 git 则询问是否推送 GitHub,不用则仅更新记忆。
- 每个任务完成后:git 模式下 commit→push→(成功后)写记忆;仅记忆模式下只写记忆。
- 开 PR / 合并到 main 属于手动门控,必须用户显式发话。

## 2. 需求快照

| 维度 | 决定 |
|------|------|
| 分发形态 | 新建 plugin,内含 project-memory(迁入) + github-workspace(新建) 两个 skill |
| 适用范围 | 任何项目(通用),非仅本项目 |
| 初始化 | 手动触发;记忆总是初始化;git 有无检测后分流 |
| 分支模型 | 专用 workspace 分支 |
| workspace 初始化 | 有则复用、无则从 main 新建,并立即推送到远程(设 upstream) |
| push 时机 | 每个任务完成后 commit+push |
| 记忆同步 | push 成功后把改动摘要写入 project-memory 知识图谱(语义同步) |
| 写记忆职责 | github-workspace 调用 project-memory 完成,不重复造轮子 |
| git vs MCP | 本地 git 命令主导核心流程;GitHub MCP 负责平台侧(PR / issue / 远程状态) |
| git 缺失 | 询问是否推送 GitHub;要→建仓+分支+推送,不要→仅记忆模式 |
| 记忆开关 | 总是启用(底座) |
| 第一版范围 | 核心链路 + 开 PR 到 main 的能力(合并手动门控) |

## 3. 架构(方案 A:薄编排层,复用现有体系)

github-workspace 只做「流程编排 + git 命令封装」:
- 记忆写入委托 project-memory skill(复用其 schema / 去重 / index 重建)。
- PR / 平台操作走 GitHub MCP。
- 核心 git(建分支 / commit / push)用命令行,快且不依赖 MCP 连接状态。

被否掉的方案:
- 方案 B(github-workspace 自己直接调 memory MCP 写实体):重复 project-memory 逻辑,两边易漂移。
- 方案 C(合并进 project-memory 成一个大 skill):违背单一职责。

## 4. 交付结构

```
project-ops/                          # plugin 根
├── plugin 清单 / marketplace 元数据    # 插件清单(plugin.json 等)
├── skills/
│   ├── project-memory/               # 迁入现有,尽量少改
│   │   └── SKILL.md, references/, scripts/
│   └── github-workspace/             # 新建
│       ├── SKILL.md                  # 触发时机、铁律、流程总览
│       ├── references/
│       │   ├── init.md               # 初始化 + git 分流流程
│       │   ├── sync.md               # 任务完成→commit→push→写记忆 事务流程
│       │   └── pr.md                 # 开 PR 到 main(GitHub MCP + 降级)
│       └── scripts/
│           ├── init_workspace.py     # 幂等建/复用 workspace 分支并推送设 upstream
│           └── diff_summary.py       # 生成改动摘要(文件数 / ±行数 / 涉及模块)
```

## 5. 流程设计

### 5.1 初始化(手动启动)

```
用户手动触发初始化
  │
  ├─ 1. 总是初始化项目记忆系统(.memory + .mcp.json,走 project-memory setup)
  │
  └─ 2. 检测 git 仓库?
        ├─ 有 git → 走 workspace 流程(建/复用 workspace 分支 + 推送设 upstream)
        └─ 无 git → 询问「要不要推送到 GitHub?」
              ├─ 要   → git init + 建仓 + workspace 分支 + 推送
              └─ 不要 → 跳过 git,仅保留记忆系统(仅记忆模式)
```

workspace 分支初始化(`init_workspace.py`,幂等):
1. 确认在 git 仓库、工作区干净(脏则提示先 commit/stash,不擅自处理)。
2. 查本地/远程有无 workspace 分支 → 有则 checkout 复用,无则从最新 main 新建。
3. 立即 `git push -u origin workspace` 建立远程跟踪。
4. 若发现 workspace 落后 main 较多,提示用户是否先同步(不自动 rebase)。

### 5.2 任务完成后的同步事务(核心链路,严格按序)

**git 模式:**
```
1. git add + commit        (message 用 diff_summary.py 生成的摘要)
2. git push                ← 关键闸门
3. push 成功?
   ├─ 是 → 调用 project-memory 写入本次 progress(含分支 / commit 号 / diff 摘要)
   └─ 否 → 不写记忆,原样呈现 git 报错并停下等用户处理
```

**仅记忆模式:**
```
1. 每任务完成 → 只写记忆(无 git 步骤)
```

无改动时不做空 commit,跳过并告知。

### 5.3 开 PR / 合并到 main(手动门控)

- 仅当用户显式说「开 PR」/「合并到 main」时执行。
- 走 GitHub MCP 创建 workspace → main 的 PR。
- 合并同样等用户确认,skill 不自动合并。

## 6. 铁律

1. **手动初始化**:不自动初始化,等用户显式触发。
2. **记忆底座**:记忆系统总是启用,与 git 无关。
3. **main 保护**:自动只到 workspace;开 PR / 合并 main 必须用户显式发话,skill 不主动发起、不自动合并。
4. **语义同步**:git 模式下 push 成功才写记忆(带真实 commit 号);push 失败不写,杜绝「记忆说 push 了但远程没有」的漂移。
5. **凭证安全**:不碰、不打印 PAT。

## 7. 错误处理与边界

| 场景 | 处理 |
|------|------|
| push 失败(网络/冲突/认证) | 不写记忆,原样呈现 git 报错,停下等处理 |
| non-fast-forward 被拒 | 提示先 `git pull --rebase`,`--force` 永不自动执行 |
| GitHub MCP 断连 | 只影响开 PR;降级为给出网页 compare 链接 `https://github.com/<repo>/compare/main...workspace`,不卡死 |
| workspace 落后 main | 同步前不强制 rebase;初始化时若落后较多则提示,合并方向决策归用户 |
| 记忆写入失败 | 此时 push 已成功(代码安全);按 project-memory 自愈重试,仍失败则明确告知「代码已 push,但记忆未写入」 |
| 工作区脏 / 无改动 | 无改动不空 commit;初始化时脏则提示先 commit/stash,不擅自处理未提交改动 |
| 凭证 | 不碰不打印 PAT |

## 8. 测试策略

### 8.1 脚本单元测试(pytest)

- `init_workspace.py`:临时 git 仓 + mock remote,测四种情况——无 workspace 分支(新建)、已有本地分支(复用)、已有远程分支(复用)、工作区脏(拒绝并提示)。不碰真实 GitHub。
- `diff_summary.py`:构造已知 diff,断言摘要输出(文件数 / ±行数 / 涉及模块)正确。

### 8.2 流程逻辑验证(检查清单,写进 references)

- 语义同步:模拟 push 失败 → 断言「不写记忆」。
- git 分流:无 git 仓 → 触发询问;仅记忆模式 → 不执行 git 步骤。
- main 保护:自动流程永不触碰 main / 不自动合并。
- MCP 断连降级:开 PR 时 MCP 不可用 → 给出网页 compare 链接。

### 8.3 不测

真实 GitHub API 往返、真实 PAT(YAGNI + 安全);靠 MCP 自身保证。

## 9. 未决 / 后续

- plugin 清单的确切格式(plugin.json 字段)在实施计划阶段依据 Claude Code plugin 规范确定。
- workspace 分支名是否可配置(默认 `workspace`)留待实施时定默认值。
- 迁入 project-memory 时是否需要调整其内部对 skill 路径的引用,实施阶段核对。
