## ADDED Requirements

### Requirement: config.yaml 支持按报告节名配置自定义说明
项目级 `config.yaml` SHALL 支持一个可选配置项，用于为 `loopspec status` 报告的各个分节追加项目自定义说明文字。该配置项 SHALL 以**报告节名的小写连字符形式**为键，取值为该节的说明文本：`overview`、`nodes`、`gate-failures`、`pending-rollback`、`next-steps`、`error`。

```yaml
status_report_prompts:
  nodes: |
    This project keeps API contracts under specs/api/.
    A specs node is not done until every endpoint has one.
  next-steps: |
    Always run commands from the repository root.
```

该配置项 SHALL 为可选且默认为空，使既有的 `config.yaml` 无需改动即可继续加载——本项 SHALL NOT 引入任何配置迁移步骤。

这是继 `context`（全局注入）与 `rules`（按节点 ID 注入）之后 `config.yaml` 的第三个项目级扩展维度，三者互不替代：`context`/`rules` 注入的是 `loopspec instructions` 给生成节点的上下文，本项注入的是 `loopspec status` 报告给读者的阅读说明。

配置文本的呈现规则（追加而非覆盖、逐行消毒、逐行缩进），以及未知键告警的输出通道与消毒要求，均由 `status-report` 能力规定。

#### Scenario: 配置按节名生效
- **WHEN** `config.yaml` 为 `nodes` 与 `next-steps` 两个节配置了说明
- **THEN** 加载成功，两节的说明分别与其节名关联

#### Scenario: 未配置该项时照常加载
- **WHEN** `config.yaml` 未出现该配置项
- **THEN** 加载成功，全部节均无项目自定义说明

#### Scenario: 配置了不存在的节名
- **WHEN** `config.yaml` 中出现一个不属于报告分节的键（如 `nodess`）
- **THEN** 系统输出告警但不中断命令执行，该键被忽略；告警的输出通道与消毒要求见 `status-report` 能力

#### Scenario: 配置项为空映射
- **WHEN** `config.yaml` 中该配置项存在但为空映射
- **THEN** 加载成功，行为与未配置时相同
