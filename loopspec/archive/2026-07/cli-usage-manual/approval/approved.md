# Human Approval: APPROVED

## Summary Presented to the Human

向人类呈现的 round 2 计划摘要（在 round 1 的双语反馈被并入之后）：

- **本轮流程**：round 1 的双语要求走 `approval` 的 FAIL 路径记为 changes requested，`loopspec rollback` 把 round 1 的 `design.md`/`specs/usage-docs/spec.md`/`tasks.md`/`security/pass.md` 移入 `.attempts/round-001/`（移动而非删除），重做时人类的要求作为 `priorAttempts` 传给被重置的节点。
- **问题（未随双语要求改变）**：`README.md` 是仓库唯一文档；10 个子命令中 `history`/`schemas *`/`version` 从未被提及；`config.yaml` 实际 6 个字段而仅 2 个有示例；`schema.yaml` 全字段与加载期语义校验只能读 `src/` 获得；`--json` 作为主协议却无字段级文档，15 个错误码只存在于代码与 spec 中。
- **能力**：新增 `usage-docs`（文档集的结构与内容契约，含双语布局与两版等价性）；不修改任何既有能力的 spec 级行为。
- **双语布局决策**：语言并列子目录 `docs/en/**` 与 `docs/zh/**`，跨语言文件名逐一同名；`docs/README.md` 是唯一位于语言目录之外的文件，只做双语语言入口不承载事实性内容。选它的理由是跨语言等价性因此退化为机械的集合比对——漏译一篇即路径集合不相等。否决文件名后缀方案（两版混放同一目录导致相对链接易跨语言交叉，漏译表现为少一个文件而非集合不等）与单文件双语并排方案（人类需滚动跳过另一语言，LLM 每次局部读取吞双倍 token，代码块重复两遍会使"示例校验"与"示例逐字相等"两组断言互相打架）。
- **规范源决策**：英文版为 normative source（与 `README.md`、代码注释、CLI `--help`、错误码 `fix` 文案同源），中文版为等价译本，撰写顺序固定先 en 后 zh；但中文版必须通过与英文版完全相同的全部一致性断言，不是次要文档。
- **等价性如何可测**：命令名、选项名、字段名、错误码、示例块内容、示例标记注释、文件路径、`## loopspec <command>` 小节标题一律不翻译，翻译只作用于散文与表格说明列。于是原四组"代码 → 文档"断言按语言各跑一遍，并新增第五组跨语言等价断言（文件清单、命令小节标题、字段名、错误码四类集合相等 + 带标记示例块逐字相等 + 每篇首屏语言互链且目标存在 + 除首屏链接外无跨语言链接）。
- **明确接受的缺口**：散文不做逐句比对——中文散文可能落后于英文散文而测试仍绿，由人工 review 兜底；逐句比对需要对齐机制或翻译记忆，成本远超收益。`--json` 响应示例不做自动校验（构造 fixture change 目录成本高于收益），但仍受跨语言逐字相等约束。
- **规模**：`specs/usage-docs/spec.md` 14 条需求 / 53 个 Scenario；`tasks.md` 6 组 40 个任务，顺序为采集事实源 → 英文版 7 篇 → 一致性测试仅对 en 执行 → 中文版 7 篇加语言入口 → 双语等价断言 → 收敛 `README.md`/`Makefile` 并验收。新增 15 个文档文件加 1 个测试文件。
- **security 复审结论**：PASS。确认双语化未引入新安全面（无翻译服务调用、无新依赖、无构建期合成），round 1 的 4 条建议全部已落地（`schema-dir` 示例物化前校验相对路径安全性、凭据断言失败不回显命中内容、采集样例时每条命令显式传 `--home <tmpdir>`、闭集反向断言思路在跨语言维度被采纳）。**新识别一条**：`status`/`instructions` 的 `--json` 样例含 `resolvedOutputPath` 等绝对路径，直接粘入文档会把本机 home 路径（含用户名）写进仓库，与"示例不得含真实用户标识"相抵，采集后须替换为占位根如 `/path/to/project/...`。另有 3 条非阻塞建议：链接断言显式跳过外部 scheme、跨语言逐字比对失败时优先报"文件对 + 块序号 + 首个差异行号"、单向覆盖与散文双语漂移的边界不可误读为宽松。
- **主动告知的一处越界操作**：`proposal` 节点不在 `approval` 的回退闭包内（`on_fail.reset: [specs, design]`），loopspec 未归档它，但其文件清单已与双语决策矛盾。遂就地同步了 What Changes、Capabilities、Impact 三处（Why 未动，双语要求不改变问题陈述），并在 `state.md` 记录为"定点同步、未被归档"及理由。
- **留给人类的开放问题**：`--json` 响应示例是否值得做自动校验（round 1 已提出，人类当时未表态）；新增第三种语言时表头词映射与两两比对是否需改为以 en 为基准。

## Human's Words

> approve

（人类未附加任何限定条件、例外或前置要求，也未对摘要中列出的任何决策、接受的缺口或 security 建议提出异议。）

## Non-Blocking Suggestions

人类未提出任何附加建议。以下是进入 `apply` 时必须携带的既有非阻塞事项，来源是 round 2 的 `security/pass.md` 而非本次人类反馈：

- 采集 `--json` 样例后，把 `resolvedOutputPath`、`changeRoot`、`statePath` 等绝对路径字段统一替换为占位根（如 `/path/to/project/loopspec/changes/add-payment/proposal.md`），避免把本机 home 路径与用户名写入仓库；并考虑在凭据检查规则中加入"疑似本机 home 路径"一条。
- 链接存在性断言显式跳过 `http://`、`https://`、`mailto:` 等 scheme，防止后续被误升级为网络可达性探测。
- 跨语言示例逐字比对失败时，优先输出"文件对 + 块序号 + 首个差异行号"，而非把两版示例整块打进测试日志。

## state.md Write-Back

- Decision Log: round 2 - approved
- Frozen Decisions: 双语布局为语言并列子目录 `docs/en/**` 与 `docs/zh/**` 且跨语言文件名逐一同名；`docs/README.md` 只做双语语言入口不承载事实性内容；英文版为规范源、中文版为等价译本且两版受同一套断言约束；撰写顺序先 en 后 zh；不翻译清单（命令名、选项名、字段名、错误码、示例块内容、示例标记注释、文件路径、`## loopspec <command>` 小节标题）；字段表五列固定顺序且断言按列位置定位；跨文档链接只在同语言目录内；示例块内不得写翻译性注释；双语等价性只覆盖结构化事实、散文不做逐句比对；一致性测试的四组单向覆盖按语言分别执行并加第五组跨语言等价断言；纯 Markdown 无新依赖、不引入 i18n 框架或翻译工具链；不改动 `src/loopspec/**`。以上为人类签核的计划要点，后续节点 SHALL NOT 静默变更——变更需要新一轮 approval。
- Artifact Notes: approval/approved.md - approved
