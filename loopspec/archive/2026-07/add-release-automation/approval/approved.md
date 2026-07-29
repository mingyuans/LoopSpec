# Human Approval: APPROVED

`approval` 第 2 轮（本 gate 的第 2 次尝试；第 1 次判定为「要求修改」，即改为 tag 驱动）。

## Summary Presented to the Human

向人展示的是第 4 轮方案（tag 驱动 + 插值边界）的摘要：

**发布流程**改为显式三步且必须按序：① 把 `pyproject.toml` 与 `src/loopspec/__init__.py` 的版本号同时改成目标版本并合并到 `main`；② `git tag v0.1.0 <main 上的 commit>`；③ `git push origin v0.1.0`——只有第 ③ 步触发发布。合并到 `main` 本身不再产生任何 Release（只跑 lint/test/build），这使前几轮"首次合并即发出 `v0.1.0`"的问题自动消解。

**四个由 tag 驱动逼出的连带决定**：

- `main` 的 push 仍触发工作流但只跑 `verify`——裁决改的是发布触发方式，不是"要不要持续校验"；只留 tag 触发会让 `main` 上的普通 commit 完全没有 CI。
- 版本号取自 tag，但**仍然**校验 tag = `pyproject.toml` = `__init__.py`，且放在构建之前——wheel 文件名由 `pyproject.toml` 决定而非 tag，否则会发出文件名与 Release 版本号矛盾的资产。
- Release 已存在 → **失败**，不再"跳过且算成功"——旧语义唯一的理由是"每个 commit 都走发布路径不能刷红叉"，tag 推送是明确的发布意图，此时报成功等于掩盖失败。
- **（明确标注为待确认）** 被打 tag 的 commit 必须可从 `main` 到达（D15）——git 的 tag 不属于任何分支，这是落实"在 master 分支打 tag"的唯一准确表述；并说明它与前两条联合构成版本混淆防护（删掉会削弱），且它是我的落实方式而非裁决明确要求。

**安全评审历程**：第 1 轮 FAIL（4 项：checkout 持久化令牌、特权 job 内执行未固定版本的构建后端、完整性校验可空校验假通过、`dist/*` 通配符发布）；第 2 轮 PASS；改 tag 驱动后第 3 轮又 FAIL（1 项：tag 名可被影响，`on.push.tags` 的 glob 尾部 `*` 放行 `v1.0.0$(...)`，而当时无约束禁止把它以 `${{ github.ref_name }}` 插进 `run:`——模板注入发生在正则校验之前）；第 4 轮补上 D18 插值边界后 PASS，并核验第 1 轮的 4 项修复未被稀释。

**规模**：9 组 54 个任务，未开始实现；4 轮迭代、3 次回滚，历史存于 `.attempts/round-001..003/`。

## Human's Words

> Approve.  tag 名不会被攻击，能够提交 tag 的仅仅是 repo owner, 这点不会是特别大的安全问题。

## Non-Blocking Suggestions

人在批准的同时给出了一条威胁模型上的判断：能够推送 tag 的只有 repo owner，因此 tag 名被恶意构造并非需要重点防范的风险。这条判断被如实记录，且**不改变已批准的方案**——理由有两点，一并记下以免日后被误读为"批准时忽略了这条意见"：

- 插值边界（D18）与格式闸门（D6）都是**零成本**的写法约束（值经 `env:` 绑定、脚本里带引号引用、一条 `grep` 核对），保留它们不增加任何实现或维护负担，删掉也换不回任何东西。
- 二者除了防注入还顺带承担别的作用：D6 的格式闸门是"tag 名与构建产物名一致"这条断言的前置（D3、D5 都依赖它），D18 的 `env:` 绑定形态则让 step 间传值的路径统一。删掉会牵动这些地方，收益为零。

因此方案按第 4 轮原样进入实现，人的这条判断作为威胁模型的记录保留在此处与 `state.md`。

**D15 按"随方案原样批准"处理**：人未单独否掉它，且其批准的正是包含 D15 的第 4 轮方案，故实现时保留。人关于"推 tag 者仅为 repo owner"的判断与 D15 的关切方向相邻但不重合——D15 约束的是"哪些 commit 可被发布"（防止把未合入默认分支的 commit 或旧 commit 冠以任意版本号发布），而非"谁可以发布"。若后续认为 D15 多余，删掉那一个 step 即可，但需知晓它与 D5、D16 联合构成版本混淆防护。

## state.md Write-Back

- Decision Log: round 2 - approved
- Frozen Decisions: 发布 tag 驱动（`on.push.tags` 发布，`on.push.branches: [main]` 只跑 `verify`）；发布版本号取自 tag 名；三方版本号一致性校验且置于构建之前；Release 已存在则失败不跳过；被打 tag 的 commit 必须可从默认分支到达（D15，随方案批准）；`workflow_dispatch` 语义由 ref 决定；令牌可见性边界（D13）；表达式插值边界（D18）；构建后端版本约束（D14）；完整性校验三步断言（D8）；发布资产文件名白名单（D3）；action pin 到 commit SHA（D4）。后续节点不得静默改动这些点——改动需要再走一轮 approval。
- Artifact Notes: approval/approved.md - approved
