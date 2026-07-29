# Human Approval: CHANGES REQUESTED

## Changes Requested

- **发布触发方式从"版本号驱动"改为"tag 驱动"**：工作流的发布路径 SHALL 由推送符合 `v<version>` 形式的 tag 触发（`on.push.tags`），SHALL NOT 再由默认分支的普通 push 加"读 `pyproject.toml` 的 `version`"来决定是否发布。`release-automation` spec 中的「发布由版本号驱动，已发布的版本跳过且不算失败」这条需求需整条替换。
- **发布版本号的权威来源改为 tag 名**：`release`（发布）路径的版本号 SHALL 从触发它的 tag 名（去掉 `v` 前缀）取得，SHALL NOT 从 `pyproject.toml` 读取后再去判断 tag 是否存在。`scripts/check_version.py` 的职责需相应调整——它不再是"发布版本号的来源"，而变成"校验 tag 名与 `pyproject.toml`/`src/loopspec/__init__.py` 三者一致"的校验器（wheel 文件名由 `pyproject.toml` 的版本决定，因此三者不一致时构建产物名会与 tag 对不上，必须显式拦住）。
- **"Release 已存在则跳过且算成功"这条语义需要重新裁定**：原语义存在的理由是"默认分支每个 commit 都跑发布路径，不能每次亮红叉"；改为 tag 驱动后，一次 tag 推送就是一次明确的发布意图，"静默跳过"会掩盖失败。design 需要给出新结论并说明理由。
- **`design.md` 的 D2（发布判定）、D3（发布命令中的版本号来源）、D5（`check_version.py` 的职责）、D12（README 的 Releases 一节）需按 tag 驱动重写**；`tasks.md` 中 6.1（触发条件）、6.7（发布判定）、6.9/6.10（版本号来源与资产断言）、8.2（README 发布说明）需相应改写。
- **tag 名是新引入的外部输入，必须纳入输入校验**：tag 名会流入 Release 名、构建产物名断言与文件路径，`on.push.tags` 的 glob 过滤不等于严格校验，因此 tag 名 SHALL 走与 `LOOPSPEC_VERSION` 相同的严格正则闸门。这条需要在 `release-automation` spec 中成为显式需求，并重跑 `security` 门。

## Human's Words

> 版本改成读 tag，比如 master 分支提交 tag: 'v0.1.0'，才触发 release, 版本号直接读这 tag

## Summary Presented to the Human

向人展示的是第 2 轮方案的完整摘要：

- **问题**：仓库没有 `.github/`、没有 CI、没有分发产物；README 的 "Install" 教的是 `make install`（开发环境搭建），用户要用 CLI 必须 clone + 装 uv + sync。
- **新增两个 capability**（无 Modified）：`release-automation`（12 条需求，CI 侧发布链路）、`cli-installation`（11 条需求，用户侧安装脚本）。
- **关键决策与代价**：发布版本号驱动（tag 已存在则跳过且算成功）换掉"每次 push 都发"；两个 job `verify`(read) → `release`(write) 且 `release` 重新构建，换掉 artifact 传递以少两个 action 依赖；用预装 `gh release create` 换掉第三方发布 action；action 全部 pin 到 40 位 SHA，代价是需手动跟进；只发 GitHub Release 不发 PyPI。
- **任务清单**：9 组共 46 个任务，顺序为版本号入口 → 构建后端约束 → 安装脚本骨架 → 完整性校验 → 版本解析与安装 → workflow → Makefile → README → 验证。
- **安全评审结论**：第 1 轮 FAIL（4 项阻塞：checkout 持久化令牌、特权 job 内执行未固定版本的构建后端、完整性校验可空校验假通过、`dist/*` 通配符发布），走了一次完整 rollback；第 2 轮逐条修掉后 PASS。显式接受两条残余风险：构建后端版本范围非哈希固定；`uv tool install` 解析的运行时依赖树不在完整性保证范围内。
- **两个请人裁决的问题**：① 仓库默认分支是 `main` 而非需求原文说的 `master`，当前按 `main` 实现；② 首次合并会立即发出 `v0.1.0`（当前版本号尚无 Release）。

人给出的回应没有回答上述两问，而是改变了发布触发机制本身——这使问题 ② 自动消解（不再有"合并即发布"，必须显式推 tag），问题 ① 的实质也变了（tag 不属于任何分支，需要重新决定是否约束被打 tag 的 commit 必须可从默认分支到达）。

## Suggested Direction

重做 `design`/`specs`/`tasks` 时，以下几点是新方案绕不开的，需要明确给出结论而不是含糊带过：

- **不要把"默认分支 push 跑构建校验"一起丢掉**。人改的是**发布**的触发方式，不是"要不要持续校验"。如果只保留 `on.push.tags`，那么 `main` 上的普通 commit 将完全没有 CI——这是相对第 2 轮方案的功能退化。方向建议：保留两个触发器，`main` 的 push 只跑 `verify`，tag 的 push 跑 `verify` + `release`，`release` job 用 ref 条件把自己限制在 tag 上。
- **三处版本号的关系要讲清楚**。tag 是发布版本号的权威来源，但 wheel/sdist 的文件名由 `pyproject.toml` 的 `version` 决定，`__init__.py` 的 `__version__` 又是源码 checkout 下 `loopspec version` 的 fallback。方向建议：tag 权威，CI 断言三者一致，不一致即失败（fail-closed）。若考虑用 `hatch-vcs` 一类方案让版本号真正只有 tag 一个来源，需要显式评估它引入的构建依赖与对 `loopspec version` 既有 fallback 语义的影响，并给出取舍结论。
- **人明确说的是"master 分支提交 tag"**，而 git 的 tag 并不属于任何分支。需要决定是否加一条"被打 tag 的 commit 必须可从默认分支到达"的校验来落实这个意图，并说明代价（需要 `fetch-depth: 0`）。这条属于新增约束，请在 design 里作为独立决策给出，便于下一轮 approval 时人能单独否掉它。
- **`workflow_dispatch` 的语义需要重新定义**：tag 驱动下手动触发若跑在分支 ref 上就没有版本号可读，应当明确失败而不是猜一个版本号。
- **`make release-dry-run` 需要重新定位**：本地没有 tag 上下文，应保留"`pyproject.toml` 与 `__init__.py` 一致"的校验，并支持可选地传入一个 tag 名做三方校验的预演。
- **重跑 `security` 门**：新增的外部输入（tag 名）与新增的信任假设（谁能推 tag 就能发布，可用 GitHub 的 tag protection / ruleset 约束）都需要重新评估。第 2 轮已通过的那些控制（令牌可见性边界 D13、构建后端约束 D14、完整性校验三步断言 D8、发布文件名白名单 D3）**不受本次改动影响，应原样保留**。

## state.md Write-Back

- Decision Log: round 1 - changes requested
- Rejected Options: 「发布由 `pyproject.toml` 的 `version` 驱动 + Release 已存在则跳过且算成功」这一整套发布判定方式
- Open Questions: 是否约束被打 tag 的 commit 必须可从默认分支到达（落实"在默认分支上打 tag"的意图）；tag 驱动下 `workflow_dispatch` 的语义；是否改用 `hatch-vcs` 一类方案让 tag 成为版本号的唯一来源
- Current Focus: redo specs/design per round 1 feedback
- Artifact Notes: approval/changes-requested.md - changes requested
