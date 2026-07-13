# Design: claude-marketplace 插件管理仓

- 日期: 2026-07-13
- 状态: 已批准,待写实施计划
- 相关: [[project-ops plugin]](2026-07-13-project-ops-plugin-design.md)

## 1. 目标与定位

新建一个**独立的 git 仓库**作为 Claude Code marketplace(插件市场仓),把 `project-ops` 等插件集中托管。其它项目/机器通过 `/plugin marketplace add` 挂载、`/plugin install` 安装、`/plugin marketplace update` 拉更新,实现**单一来源、版本自动同步**,消灭当前"业务仓副本 + 全局手动副本 + 未来副本"的多版本漂移。

核心技术点:解决插件经 marketplace 安装后落在**版本化缓存路径**(`~/.claude/plugins/cache/<市场>/<插件>/<版本>/`)时,skill 脚本的路径解析——统一改用官方运行时变量 `${CLAUDE_PLUGIN_ROOT}`。

## 2. 需求快照

| 维度 | 决定 |
|------|------|
| 仓库性质 | 新建独立 git 仓,与业务仓 LBS-FramWare 解耦 |
| 布局 | 对齐官方:仓根 `.claude-plugin/marketplace.json` + `plugins/<插件名>/` 子目录 |
| 位置/远程 | 本地新建(如 `e:/claude-marketplace`),暂不推远程;以后可推 GitHub |
| 迁移 | `project-ops` 从 LBS-FramWare `plugins/` 迁入新仓 |
| 路径解析 | 两 skill 脚本引用统一 `${CLAUDE_PLUGIN_ROOT}/skills/<skill>/scripts/...`,含"未替换即报错"降级 |
| CLAUDE.md 开场规则 | 不写死脚本路径,改为指向 skill 名(避免消费项目 CLAUDE.md 依赖路径变量) |
| 旧全局副本 | project-memory 先保留(当前会话依赖),marketplace 版验证后再定去留 |
| 消费方式 | `/plugin marketplace add <仓>` → `install` → `marketplace update` |

## 3. 关键事实(实测)

- **安装落盘**:marketplace 装的插件位于 `~/.claude/plugins/cache/<市场名>/<插件>/<版本>/`(如 `code-simplifier/1.0.0/`),版本化、非固定位置 → 任何写死路径都会失效。
- **官方路径变量**:`${CLAUDE_PLUGIN_ROOT}` 是官方运行时变量,指向插件安装根目录。验证来源:discord 插件 `.mcp.json` 用 `--cwd ${CLAUDE_PLUGIN_ROOT}`;code-modernization 的 command 用 `scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/xxx.js"`,并含"变量未替换则报错"的降级。
- **marketplace.json**:仓根 `.claude-plugin/marketplace.json`,含 `name` / `owner` / `plugins[]`;每条插件带 `source`(本仓内插件用相对路径/local 源)。

## 4. 仓库结构

```
claude-marketplace/                        # 独立 git 仓
├── .claude-plugin/
│   └── marketplace.json                   # 市场清单,列出所有插件
├── plugins/
│   └── project-ops/                        # 从 LBS-FramWare 迁入
│       ├── .claude-plugin/plugin.json
│       ├── README.md
│       └── skills/
│           ├── project-memory/
│           └── github-workspace/
└── README.md                               # 仓说明 + 安装指引
```

`marketplace.json` 里 project-ops 的 source 用本仓相对路径(`./plugins/project-ops`)。加新插件 = 在 `plugins/` 下加目录 + 在 `marketplace.json` 追加一条。

## 5. 路径解析改造(技术核心)

### 5.1 统一变量
两个 skill 里所有脚本调用改为:
```
python ${CLAUDE_PLUGIN_ROOT}/skills/github-workspace/scripts/init_workspace.py
python ${CLAUDE_PLUGIN_ROOT}/skills/github-workspace/scripts/diff_summary.py
python ${CLAUDE_PLUGIN_ROOT}/skills/project-memory/scripts/build_index.py
python ${CLAUDE_PLUGIN_ROOT}/skills/project-memory/scripts/check_memory_path.py
python ${CLAUDE_PLUGIN_ROOT}/skills/project-memory/scripts/encode_project_path.py
python ${CLAUDE_PLUGIN_ROOT}/skills/project-memory/scripts/migrate_md_to_graph.py
```

涉及文件:
- `github-workspace/SKILL.md`、`references/init.md`、`references/sync.md`(约 4 处)
- `project-memory/references/setup.md`、`references/workflows.md`(把 `<project-memory skill scripts dir>` 占位/旧硬编码统一)

### 5.2 未替换降级(借鉴官方 modernize-map.md)
两个 SKILL.md 加一条运行时铁律:若执行命令里出现字面量 `${CLAUDE_PLUGIN_ROOT}`(未被展开,可能非插件方式运行或环境不支持)→ **不静默拼错路径**,报告"插件根变量未展开",提示确认插件是否经 marketplace 正确安装。

### 5.3 CLAUDE.md 开场规则(消费项目侧)
project-memory setup 注入到**每个消费项目** CLAUDE.md 的开场规则,原来引用脚本路径。因 `${CLAUDE_PLUGIN_ROOT}` 只在插件自身 skill/command 上下文保证展开,写进任意项目 CLAUDE.md 后能否展开存疑 → 开场规则**不写死脚本路径**,改为"调用 project-memory skill 的路径自愈/开场读取流程"这种**指向 skill 名**的表述;skill 被调用时自己用 `${CLAUDE_PLUGIN_ROOT}` 定位脚本。消费项目 CLAUDE.md 由此不依赖任何路径变量。

## 6. 迁移、清理与消费流程

### 6.1 迁移
1. 新建本地仓 `claude-marketplace`,`git init`。
2. 复制 `e:/LBS-FramWare/plugins/project-ops/` → 新仓 `plugins/project-ops/`。
3. 写仓根 `.claude-plugin/marketplace.json`(列出 project-ops)+ 仓 README。
4. 应用 §5 路径改造;跑两个 skill 的脚本测试(38 个)确认仍绿。
5. 新仓首次 commit。

### 6.2 清理旧副本(消灭漂移源)
迁移验证通过后:
- 删 `e:/LBS-FramWare/plugins/`(业务仓临时孕育副本)→ 业务仓单独 commit。
- 删全局手动装的 `~/.claude/skills/github-workspace/`。
- 全局 `~/.claude/skills/project-memory/`:**先保留**(当前会话记忆系统依赖它,CLAUDE.md 开场即用)。待 marketplace 版验证可用后再定去留。

### 6.3 消费流程(其它项目)
```
# 一次性挂载(每台机器)
/plugin marketplace add e:/claude-marketplace
/plugin install project-ops@<market-name>
# 重启会话

# 拉更新
/plugin marketplace update <market-name>
```
之后项目内显式触发初始化,流程同 project-ops(记忆先建 → git 分流 → workspace)。

## 7. 测试策略

- **脚本单测**:迁移后在新仓内跑两个 skill 的 pytest(38 个),确认 §5 路径改造未破坏逻辑。
- **冒烟验证**:实际 `marketplace add` 本地仓 + `install`,重启后确认插件被加载、skill 可见、`${CLAUDE_PLUGIN_ROOT}` 被正确展开(脚本路径能跑)。
- **不测**:跨机器 GitHub 拉取(暂不推远程,YAGNI)。

## 8. 未决 / 后续

- 新仓与 market 的确切命名(`claude-marketplace` / market `name` 字段)在实施阶段定。
- marketplace.json 里 project-ops 的 source 相对路径写法,依 Claude Code marketplace schema 在实施时核对。
- 全局旧 project-memory 的最终去留,待冒烟验证后由用户拍板。
- 推 GitHub 远程(跨机器共享)作为后续增量。
