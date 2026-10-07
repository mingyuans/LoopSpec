## 为什么需要调整

当前 new 将建目录、生成 Plan、可选偏离审批与活动计划激活放在同一步，导致 Agent 在创建需求前就要选流程，而且普通 Plan 没有统一的人类确认阶段。用户明确要求先建立 Change，再结合任务选择 Fragment/Profile，创建草稿 Plan，取得人类确认后用独立命令定稿。

## 变更内容

- **BREAKING**：新模型默认 `loopspec new <change-name>` 仅建立 Change 和最小元数据，不接受 `--plan`、`--profile`、`--approval`，不编译、审批或激活 Plan；显式 `--schema` 保留旧流程入口。
- 新增 `loopspec plans create <change-name> --plan <request-path>`，校验并保存本需求的不可变草稿快照；可用 `--profile <name>` 直接采用模板，但仍然只生成草稿。
- 新增 `loopspec plans approve <change-name>`，在真实人工确认后，将确认的当前草稿原子定稿为活动 Plan；所有新 Plan 都需要确认，不仅是模板偏离。
- 审批命令不读取人工审批 YAML 文件；提供 `--expected-digest` 防止确认期间草稿被替换，可选 `--message` 记录真实人工原话。Agent 不得从需求描述或上一轮批准推断新的计划已获批。
- 未定稿时 status/next 提供规划阶段指引；instructions、代码 Gate、保障、返工和完成归档不能执行未批准的草稿。
- Profile 保持模板定位，不再以 protected 与 deviations 控制模板偏离审批；项目最低保障约束、必须的 Gate 和全量 Diff Assurance 继续强制校验。
- 后续重组与安全扩张也先创建新草稿，再经 plans approve 激活；旧活动计划、历史预算、固定基线和已完成节点的冻结规则不变。
- 更新英文 builtin/skills 新建/继续流程及中英文产品文档；不更新真实 .codex/skills、.claude/skills 或全局安装目录。

## 能力范围

### 新增能力

- `workflow-plan-approval`：先建 Change、后建草稿、人工确认后定稿的生命周期，含摘要绑定、草稿快照、并发及失败处理。

### 修改能力

- `workflow-planning`：Plan 的首次创建与修订统一通过显式确认；Profile 不再承担偏离审批约束。
- `loopspec-cli`：new 简化，新增 plans create/approve，执行导航识别未规划、待确认和已批准状态。
- `lpsx-skills`：新建 Skill 先 new，再目录发现、草稿创建、人工沟通和 approve；Continue 不自动批准待确认计划。

现有能力基线位于已完成但尚未归档的 dynamic-workflow-composition/specs/；当前仓库尚无 loopspec/specs/ 汇总目录。本次不自动归档或改写其历史实施报告。

## 影响与边界

- 调整 CLI、工作流元数据/快照、修订事务、运行时读取、内置模板/Skill 与对应测试、文档。
- 兼容已有旧 Schema Change 与已经激活的旧 Plan；不得因默认 new 行为改变而自动迁移它们。
- 不增加审批人身份认证、电子签名、外部服务或 CI 系统；approve 是明确的本地确认动作，不是代码 Gate PASS。
- 本次修改只针对规划与定稿生命周期，不扩大代码提交、部署、安装投影或归档权限。
