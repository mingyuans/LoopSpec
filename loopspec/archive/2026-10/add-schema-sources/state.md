# Change State

## Current Focus
- security 门禁第 2 轮 PASS（`security/pass.md`）。`approval` 节点等待人类审批。
- redo specs/design per approval round 1 feedback（`approval/changes-requested.md`）：schema 源改为 GitHub 仓库 registry + `loopspec schemas update` + 由 skill 驱动 LLM 合并并与用户确认冲突；proposal.md 也需按新方向改写。

- redo specs/design per approval round 2 feedback（`approval/changes-requested.md`）：加入 schema 级（`schema.yaml` 的 `version`）与 registry 级（git tag）版本号。
- 第 2 轮重做已完成（加入版本号、ls-remote 预检、`version: latest | <tag>`）；security 第 4 轮 PASS，`approval` 第 3 轮等待人类审批。

## Frozen Decisions
- 范围只包含本地目录源；远程源（git / HTTP）、缓存与版本锁定列为非目标。
- 源在项目 `config.yaml` 的 `schema_sources` 中声明，不引入用户级全局配置。
- 查找顺序：`local`（`<home>/schemas/`）优先，然后按 `schema_sources` 声明顺序；先命中者胜出，`local` 遮蔽外部同名 schema。
- `.workflow.yaml` 仍只记录 schema 名称，不记录源；无 `schema_sources` 时行为与现状完全一致。

## Decision Log
- 用户未就 new 阶段提出的四个范围问题（源形式、配置位置、重名处理、缓存/版本）作答，直接要求继续；proposal 按上述默认值起草，留待 approval 门禁由人类确认。

- security 第 1 轮 FAIL（三条阻塞项）：(a) instructions/templates 的包含性只相对各自子目录判定，子目录本身是外链时可读出任意本地文件并交给 agent；(b) `schema.yaml` 未做包含性检查，校验错误回显可泄露外部文件内容；(c) 未约束 warning/错误不得回显符号链接解析后的目标路径。
- 第 2 轮修复：新增 D9（schema.yaml / instructions / templates 的包含性一律以 `schema_dir.resolve()` 为基准判定，schema.yaml 先判定后读取，模板在读取时刻复判）与 D10（诊断信息只回显名字与配置原文）；spec 补 6 个 scenario；tasks 新增第 3 组。收紧对 local 源同样生效（已确认内置 schema 无符号链接）。
- approval 第 1 轮 changes requested（`approval/changes-requested.md`）：(1) 源是配置在 `loopspec/config.yaml` 中的 registry——一个 GitHub 仓库；(2) schema 仍以本地副本存在于 `<home>/schemas/`，registry 是其上游；(3) 新增 CLI 命令（如 `loopspec schemas update`）从 registry 拉取更新以合并 / 覆盖本地副本；(4) 冲突大概率发生，因此合并不由 CLI 决定：新增 skill，用户在 LLM 对话中说「更新 schemas」，LLM 经 CLI 拉取并尝试合并，有冲突时整理后与用户确认。上文 Frozen Decisions 中「仅本地目录源」「不引入远程源」「按 local → schema_sources 顺序运行时查找并遮蔽」三条被本轮推翻。
- approval 第 1 轮后的补充澄清（人类经 AskUserQuestion 作答）：registry 只配置**一个**，并且**全量同步**其中所有 schema 到 `<home>/schemas/`；没有冲突的更新（只有上游改过、本地未改的文件）也不自动写入——由 skill 驱动的 LLM 先列出全部变更，经用户一次性确认后再写入，冲突文件逐个确认；拉取方式为调用本机 `git`（复用用户已有的 git 凭据，不新增 Python 依赖）。
- 按 approval 第 1 轮意见重做（第 3 轮 design / 第 2 轮 specs）：proposal.md 按新方向重写；新 capability `schema-registry`，修改 `lpsx-skills`（4 → 5 个模板，新增 `loopspec-update-schemas`）与 `usage-docs`。关键设计：registry 内容通过 git 对象（`ls-tree` / `cat-file`）读取，使用私有裸仓库、不 checkout 工作区；锁文件 `<home>/registry.lock.yaml` 提供三方比对基线；`schemas update` 只写 `<home>/.cache/registry/`；`schemas apply` 在写入前完成 planId / 冲突 / 本地哈希 / `load_schema` 四项校验。
- 第 1 轮 security 的 D9 加固（schema 内子目录外链）不纳入本次：新模型下 registry 永远不会写入符号链接，外部写入路径已不存在；改列为独立的后续加固项（design Open Questions）。
- security 第 3 轮 PASS（`security/pass.md`）：新增的 git 子进程、远程内容与凭据风险均有对应的设计与测试任务。两条非阻塞建议留给 apply：(1) 本地树读取与 `localPath` 复用 tasks 5.3 的父目录符号链接检查；(2) `--plan` 参数只做相等比较，不参与路径拼接。
- approval 第 2 轮 changes requested（`approval/changes-requested.md`）：人类询问是否加入版本号概念，经解释后选择「两层都做」——(1) schema 级：复用 `schema.yaml` 的 `version`，`schemas update` 报告每个 schema 的 localVersion / upstreamVersion / baseVersion，锁文件按 schema 记录版本，`schemas list` 报告版本，上游文件变了但 `version` 没增加时 warning；(2) registry 级：用 git tag 标识 registry 版本，计划中报告 upstreamTag / baseTag，锁文件记录 tag，没有 tag 时退回显示 commit；(3) 版本信息同时出现在 `loopspec-update-schemas` skill 的变更汇总与中英文文档中。registry 模型本身（第 2 轮 design D1–D8）未被否决。
- approval 第 2 轮之后、重做期间的补充澄清（人类经 AskUserQuestion 作答）：(1) 用户指出每次都拉取再比对太耗时，要求先比对版本、有变化再拉取——采用 `git ls-remote` 预检（design D10），「版本」以 tag（即 GitHub Release 的 tag）为准；registry 没有 tag 时退回比较默认分支的 commit。(2) 本地指定版本的方式：`registry.version` 只支持 `latest`（默认，跟踪最高的 semver release tag）与固定 tag（如 `v1.3.0`）两种，取代原来的 `registry.ref`。(3) 固定版本且已同步时完全离线：不执行任何 git 命令，也不提示是否有更新的版本。
- 本轮重做（第 4 轮 design / 第 3 轮 specs）：design 新增 D9（两层版本号，只用于展示与提示，不参与分类）与 D10（版本选择与 ls-remote 预检，`--full` 可跳过）；specs/schema-registry 新增两个 requirement；tasks 扩展为 9 组 40 项，并吸收 security 第 3 轮的两条非阻塞建议（tasks 4.3、6.1）。proposal.md 同步更新。
- security 第 4 轮 PASS（`security/pass.md`）：新增的输入（`registry.version`、`ls-remote` 输出、上游 `schema.yaml` 的 `version`）都有校验与测试；预检与 fetch 之间的竞态由 commit 相等检查覆盖。非阻塞建议：在文档中说明 `latest` 会跟随上游推送的更高 tag，对供应链更敏感的项目应使用固定版本（tasks 8.1）。

## Rejected Options
- 外部源一律禁止符号链接：共享仓库中目录内链接是常见的去重手段，D9 的解析后包含性判定已足够。
- 源目录缺失时降级为 warning：会让同一 change 在不同机器上解析到不同 schema。
- 通过 `git clone` 出工作区再遍历文件：会在磁盘上物化符号链接并触发过滤器 / hook。
- 让 LLM 直接复制上游文件、CLI 只更新锁文件：路径安全与可加载性校验会分散到 LLM 手上。
- 在 `.workflow.yaml` 中记录源名称：会把 change 与某台机器上的源配置绑死，且需要迁移既有 change。
- （approval 第 1 轮否决）运行时按有序源查找 schema、`local` 遮蔽外部同名 schema 的模型（原 design D1/D6/D7）。
- （approval 第 1 轮否决）只支持本地目录源、把远程 git 源列为非目标。
- （approval 第 1 轮否决）由 CLI 自行完成合并决策；冲突必须由 LLM 整理后与用户确认。
- （澄清否决）多个 registry；按需同步部分 schema。
- （澄清否决）无冲突变更由 CLI 自动应用。
- （澄清否决）通过 HTTP 下载 GitHub 归档拉取 registry。
- （approval 第 2 轮否决）不加版本号直接批准；只做 schema 级或只做 registry 级版本号。
- （澄清否决）通过 GitHub Releases API（`gh` / HTTP + token）比对版本：只适用于 GitHub，且需要 loopspec 处理凭据。
- （澄清否决）semver 范围（`^1.3` / `~1.3`）与按分支跟踪（`branch: main`）；按单个 schema 固定版本（与全量同步冲突）。
- （澄清否决）固定版本时联网提示是否有更新的版本。

## Open Questions
- 无阻塞问题。已决：安全边界见 D4/D9/D10；遮蔽用 `shadowed: bool`；源 `path` 允许相对 workflow home 的路径（含 `..`）。
- （approval 第 1 轮提出、未定）registry 在 `config.yaml` 中的字段形态（仓库 URL、ref、仓库内子目录）。
- （approval 第 1 轮提出、未定）上次同步基线版本记录在何处，用于区分「本地改动」与「上游改动」的三方合并。
- （approval 第 1 轮提出、未定）`schemas update` 同步单个 schema 还是 registry 中的全部 schema；拉取方式（调用系统 `git` 还是下载归档）。

## Artifact Notes
- proposal.md：新 capability `schema-sources`；修改 `loopspec-cli`、`usage-docs`。
- design.md：D1–D8；tasks.md：6 组任务；specs：schema-sources / loopspec-cli / usage-docs。
- approval/changes-requested.md：round 1 - changes requested。
- security/pass.md：第 3 轮 PASS（registry 模型）。
- approval/changes-requested.md：round 2 - changes requested（加入版本号）。
- security/pass.md：第 4 轮 PASS（加入版本号与预检后）。

## 未完成归档

- Decision Log：2026-10-07 用户要求归档 loopspec/changes 下全部变更。本需求停在 approval 待确认、未实施完成（2.0.0 删除旧 Schema 流程后已失去意义），v1.0.3 的 archive 只接受完成的需求，因此手动移入 loopspec/archive/2026-10/，属于未完成归档，不表示已交付。
