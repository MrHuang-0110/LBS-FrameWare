# Design: embedded-dev 并入 claude-marketplace

- 日期: 2026-07-13
- 状态: 已批准,待写实施计划
- 相关: [[claude-marketplace 插件管理仓]](2026-07-13-claude-marketplace-design.md)

## 1. 目标与定位

把已有的 `embedded-dev` 插件(现位于 `E:/cmd/embedded-dev`,非 git 仓,自带一个 `embedded-dev-marketplace`)并入现有的 `claude-marketplace` 插件管理仓,成为其 `plugins/` 下的**第二个**插件(第一个是 project-ops)。目标是继续贯彻"单一插件管理仓"原则,避免多 marketplace 漂移。

并入后 `claude-marketplace` 成为真正的多插件市场:一次 `marketplace add`,两个插件**各自独立、按需 install**(选择性安装天然支持)。

## 2. 需求快照

| 维度 | 决定 |
|------|------|
| 归置 | embedded-dev 迁入 `claude-marketplace/plugins/embedded-dev/` |
| 改造范围 | 最小必要:搬目录 + 改两个 manifest + 更新文档 |
| scripts / .mcp.json | **不动** |
| 选择性安装 | 天然支持:`plugins[]` 列两条,各自 install,可只装其一 |
| 验证 | JSON + 结构 + 无残留市场名 + 交互冒烟(两插件独立可装) |
| 测试 | embedded-dev 无 Python 单测(agents/commands/skills 构成),不涉及 pytest |

## 3. 关键事实(核实)

- **`.mcp.json` 无本地路径**:4 个 MCP(playwright / fetch-1 / context7 / sequential-thinking)全是 `npx` / `uvx` 命令,无需 `${CLAUDE_PLUGIN_ROOT}` 改造。
- **scripts 非运行时调用**:`check-deps.ps1` / `check-deps.sh` 仅被 INSTALL.md 文档提及(用户手动跑的依赖自检),commands / skills 均未以路径方式调用 → 无需路径变量改造。
- **写死路径只在文档**:INSTALL.md / README.md 里有 `E:\cmd\embedded-dev` 与自带市场名 `embedded-dev-marketplace`,并入后需更新。
- **embedded-dev 组成**:6 commands、4 agents、2 skills(embedded-domain、web-device-inspect)、2 scripts、1 .mcp.json、自带 marketplace.json(待删)+ plugin.json(保留)。
- 因此原始担心的"scripts / .mcp.json 路径改造"基本不需要;本次主要是搬目录 + 改 manifest + 更新文档。

## 4. 目标结构

```
claude-marketplace/
├── .claude-plugin/
│   └── marketplace.json          # plugins[] 含 project-ops + embedded-dev 两条
└── plugins/
    ├── project-ops/              # 已有,不动
    └── embedded-dev/             # 从 E:/cmd/embedded-dev 迁入
        ├── .claude-plugin/plugin.json   # 保留
        ├── agents/  commands/  skills/  scripts/
        ├── .mcp.json             # 保留不动
        ├── INSTALL.md  README.md # 更新安装指引
        └── (自带 marketplace.json → 删除)
```

## 5. 迁移、清理与验证流程

### 5.1 迁移
1. 复制 `E:/cmd/embedded-dev/` 整个目录 → `e:/claude-marketplace/plugins/embedded-dev/`(排除任何 `.git` / 缓存)。
2. 删除迁入副本自带的 `plugins/embedded-dev/.claude-plugin/marketplace.json`(仓根已有权威 manifest);保留 `plugin.json`。

### 5.2 改仓根 manifest
在 `e:/claude-marketplace/.claude-plugin/marketplace.json` 的 `plugins[]` 追加一条 embedded-dev:name / description / author / category / keywords 从其自带 marketplace.json 迁移,`source: "./plugins/embedded-dev"`。project-ops 条目不动。

### 5.3 更新 embedded-dev 文档
- INSTALL.md / README.md:`E:\cmd\embedded-dev` → `e:/claude-marketplace`;市场名 `embedded-dev-marketplace` → `local-marketplace`;install 命令 → `embedded-dev@local-marketplace`。
- 明确选择性安装:两个插件可各自独立 install。

### 5.4 验证
1. **JSON 校验**:仓根 marketplace.json 解析通过,`plugins[]` 恰为 2 条(project-ops、embedded-dev)。
2. **结构完整性**:`plugins/embedded-dev/` 下 plugin.json、agents(4)、commands(6)、skills(2)、scripts(2)、.mcp.json 齐全;自带 marketplace.json 已删。
3. **无残留市场名**:全仓 grep 不再以 `embedded-dev-marketplace` 作为 market 名。
4. **交互冒烟(用户执行)**:`/plugin marketplace update local-marketplace`(或重新 add)→ 市场列出 2 个插件 → `/plugin install embedded-dev@local-marketplace` 独立装上。

### 5.5 不改动项
`.mcp.json`、`scripts/check-deps.*`、agents、commands、skills 内容全部保持原样(无内部路径依赖)。

## 6. 未决 / 后续
- embedded-dev 现有 project-ops 之外的插件是否将来也统一 user-scope 安装,由用户按需决定。
- 仓根 README(claude-marketplace/README.md)可顺带在 Plugins 段列出 embedded-dev(增量,非必须)。
- 推 GitHub 远程仍作为后续增量(与 project-ops 设计一致)。
