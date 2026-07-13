# 记忆数据模型（知识图谱）

## 实体类型（entityType）
- pitfall — 踩过的坑：报错根因、反直觉行为、陷阱。
- decision — 重要决策/关键数据：选型拍板、关键参数。
- progress — 项目进度节点：阶段完成、分支合并、里程碑。
- operation — 重要操作：git 回退/revert/reset、删除或重命名关键文件、改配置、迁移、危险命令。
- component — 项目模块/子系统。
- convention — 项目约定：命名、流程、平台约束。

## Observation（挂在实体上的事实）
- 每条一句，带日期前缀：`YYYY-MM-DD: 具体事实`。
- 事实性、可复用；不写一次性对话细节。

## Relation（有向）
- pitfall —occurs_in→ component
- decision —affects→ component
- operation —acts_on→ component
- 迁移生成的历史关联统一用 relates_to。

## 四类写入触发场景
| 场景 | 信号 | 记成 |
| 坑 | 报错根因、"原来是因为…"、反直觉行为 | pitfall 实体 + observation |
| 重要数据/决策 | 选型拍板、关键参数、架构约定 | decision / convention 实体 |
| 项目进度 | 阶段完成、分支合并、里程碑 | progress 实体，更新既有而非堆叠 |
| 重要操作 | git 回退/revert/reset、删改关键文件、改配置、迁移、危险命令 | operation 实体 + observation：记改了什么、为什么、影响、如何复原 |

## git 回退专项（必记）
一旦执行或用户提到 git revert/reset/回退，必须写一条 operation observation，含：
- 回退了哪些 commit（短 SHA + 主题）
- 回退原因
- 丢弃 / 恢复了什么改动
- 当前 HEAD 位置

## 命名规范
- 实体 name 用 kebab-case，全项目唯一。
- 进度类：优先 add_observations 到既有 progress 实体，不为同一里程碑反复建新实体。
- 操作类：git 历史操作统一记到 name 为 `git-operations` 的 operation 实体，按日期追加 observation，不逐次建新实体。
