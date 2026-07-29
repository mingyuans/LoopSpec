# Change State

## Current Focus
- `apply` 已完成：40/40 任务勾选，`make lint` 通过、`make test` 545 passed、`make docs-check` 40 passed，报告见 `apply/report.md`。变更可归档。
- （已完成）round 2 计划获人类批准（`approval/approved.md`）后进入 `apply`。
- （已完成）round 2 的 `design.md`、`specs/usage-docs/spec.md`（14 条需求 / 53 个 Scenario）、`tasks.md`（6 组 40 个任务）按双语要求重做，`security` gate 复审判定 **PASS**（4 条非阻塞建议，其中 1 条为本轮新识别）。
- （已完成）redo specs/design per round 1 feedback：人类在 round 1 要求 `docs/` 文档集提供 zh/en 两个语言版本，`approval` 判定 changes requested，`specs`/`design`/`tasks`/`security` 已回退重做。
- 重做时需保留 round 1 未被质疑的决策（多文件拆分、单向覆盖的一致性测试、`<!-- loopspec:example=... -->` 示例标记、README 收敛、`Makefile` 新增 `docs-check`），只改动双语相关部分。
- （round 1 历史）计划四件产物首轮已完成且 `security` 判定 PASS（4 条非阻塞加固建议）；`approval` 首次抵达时本运行环境无交互提问工具，未代替人类批准，节点保持 `ready` 直至人类给出上述反馈。

## Frozen Decisions
- 纯 Markdown、仓库内文档，不引入静态站点生成器或任何新依赖。
- 文档集放在仓库根的 `docs/`；`README.md` 收敛为入口并链接到 `docs/README.md` 索引。
- 按"读者要解决的问题"拆分多文件，每个文件自包含，可单独喂给 LLM。
- 唯一新增能力为 `usage-docs`；本变更不修改任何既有能力的 spec 级行为。
- 本变更不改动 `src/loopspec/**`，不改 CLI 行为、`--json` 结构或 schema 语义。
- 文档集文件清单固定为 7 个（见 design D1）：`docs/README.md`、`overview.md`、`cli-reference.md`、`configuration.md`、`schema-reference.md`、`agent-protocol.md`、`workflows/secure-spec-driven.md`。
- 一致性测试只做单向覆盖（代码 → 文档），四组断言：命令/参数、模型字段（alias 优先）、错误码、YAML 示例可校验。
- 可校验示例块用前置 HTML 注释标记 `<!-- loopspec:example=config|schema|schema-dir -->`。
- 一致性测试严禁 `import click`（typer 0.27 已把 click 内置为 `typer._click`，顶层 import 会失败——已实测），只经 `typer.main.get_command` 取命令树。
- 一致性测试严禁执行文档里的任何 shell 命令，只做 `yaml.safe_load` + Pydantic 校验；`schema-dir` 示例只在 `tmp_path` 下物化。
- （round 1 后追加，上溯修正）上面"文档集文件清单固定为 7 个"一条**已被 round 1 人类反馈取代**：文档集须提供 zh/en 双语，文件清单改为每语言各 7 篇加语言入口文件，具体清单由重做的 `design.md` 决策后写入 `specs/usage-docs/spec.md`。同一条中列出的 7 个文件名（`README.md`、`overview.md`、`cli-reference.md`、`configuration.md`、`schema-reference.md`、`agent-protocol.md`、`workflows/secure-spec-driven.md`）仍是每个语言版本内部的文件构成。
- （round 1 后追加）上面"一致性测试只做单向覆盖（代码 → 文档）四组断言"一条仍然成立，但须扩展：四组断言对**每个语言版本**分别执行，并新增一组跨语言等价性断言。
- （round 2 决定）双语布局为**语言并列子目录** `docs/en/**` 与 `docs/zh/**`，跨语言文件名逐一同名；`docs/README.md` 是唯一位于语言目录之外的文件，只做双语语言入口，不承载事实性内容。
- （round 2 决定）**英文版为规范源**、中文版为等价译本，撰写顺序固定先 en 后 zh；但中文版必须通过与英文版完全相同的全部一致性断言，不是次要文档。
- （round 2 决定）不翻译清单：命令名、选项名、字段名、错误码、示例块内容、示例标记注释、文件路径、`## loopspec <command>` 小节标题。翻译只作用于散文与表格"说明"列。
- （round 2 决定）字段表五列顺序固定，表头词按语言固定（en：`Field`/`Type`/`Required`/`Default`/`Description`；zh：`字段`/`类型`/`必填`/`默认值`/`说明`），但断言按**列位置**而非表头文字定位字段名。
- （round 2 决定）跨文档链接只在同语言目录内；跨语言链接只允许出现在每篇首屏的语言切换链接与 `docs/README.md`。
- （round 2 决定）示例块内不得写翻译性注释（否则违反两版示例逐字相等）；解释写在示例块外的散文里。
- （round 2 决定）双语等价性只覆盖结构化事实（文件清单、命令小节标题、字段名、错误码、示例逐字），**散文不做逐句比对**——这是刻意取舍，由人工 review 兜底。
- **（round 2 已由人类签核）以上全部 round 2 决定，连同"纯 Markdown 无新依赖 / 不引入 i18n 框架或翻译工具链 / 不改动 `src/loopspec/**`"，均为人类批准的计划要点。后续节点 SHALL NOT 静默变更其中任何一条——需要变更则必须再走一轮 `approval`。**

## Decision Log
- 2026-07-29 选择"多文件 + 索引"而非单一大文件：CLI 参考、config 参考、schema 参考三块内容各自都会较长，合成一份会让 LLM 每次都要读入无关章节。
- 2026-07-29 决定新增 `tests/test_docs_consistency.py`：文档手册最大的风险是随代码漂移，所以把"命令/字段/错误码全覆盖 + 示例可校验"做成测试而非人工约定。
- 2026-07-29 决定把内置 schema 的说明单独放 `docs/workflows/secure-spec-driven.md`：与 `docs/schema-reference.md`（格式参考）区分开，后者讲"怎么写 schema"，前者讲"内置这份 schema 是什么"。
- 2026-07-29 round 2 - approved：人类逐字回复"approve"，无限定条件、无例外、未对任何决策或已接受的缺口提出异议。签核的计划要点已写入 Frozen Decisions；verdict 原文见 `approval/approved.md`。
- 2026-07-29 round 1 - changes requested：人类要求 `docs/` 文档集提供 zh/en 两个语言版本、两版内容等价。据此需重做 `specs/usage-docs/spec.md`（重写文件清单需求 + 新增双语等价性需求）、`design.md`（新增双语目录布局决策、删除"不做 i18n"这条 Non-Goal、更新一致性测试决策 D4 使四组断言按语言分别执行并新增跨语言等价断言）、`tasks.md`（文档撰写量由 7 篇变为双语共 14 篇加语言入口，需明确两版产出顺序）。人类未对 round 1 其余决策提出异议。verdict 原文见 `approval/changes-requested.md`。

## Rejected Options
- 单文件 `docs/MANUAL.md`：人类可读性尚可，但 LLM 检索/局部读取成本高，且与现有 spec 按能力切分的习惯不一致。
- 用 `mkdocs`/`sphinx` 生成站点：需要新依赖与 CI 发布链路，超出"手册"这一需求的范围。
- 从 Typer 自动生成 CLI 参考：能防漂移但生成不出 `--json` 响应字段表与用法示例，达不到"详细、全面"的要求；改为"手写 + 一致性测试反查"。
- （round 1 被人类否决）单一语言版本的 `docs/` 文档集：人类要求 zh/en 双语。
- （round 1 被人类否决）`design.md` 中「不做 i18n（单一语言版本）」这条 Non-Goal：与双语要求直接冲突，重做后的 `design.md` 不得再出现该条。round 2 已将其改写为"不引入 i18n 框架/翻译工具链/机器翻译流水线"与"不支持 zh/en 之外的第三种语言"。
- （round 2 否决）双语用文件名后缀（`cli-reference.md` + `cli-reference.zh.md`）：两版混放同一目录导致相对链接易跨语言交叉，"漏译"表现为少一个文件而非集合不等，`workflows/` 子目录还要再叠一层后缀。
- （round 2 否决）单文件双语并排（同一文件内中英分节）：人类需滚动跳过另一语言，LLM 每次局部读取吞双倍 token，且代码块重复两遍会使"示例校验"与"示例逐字相等"两组断言互相打架。
- （round 2 否决）只翻译索引 / 部分翻译：人类要求两版等价，不是"中文导览 + 英文正文"。

## Open Questions
- `--json` 响应示例暂不做自动校验（构造 fixture change 目录成本高于收益），这是已知覆盖缺口，已在 design Risks 记录；round 1 已向人类提出该开放问题，人类未表态，仍未决。
- 若撰写过程中发现 `src/loopspec/` 实现与 `openspec/specs/` 某条 SHALL 冲突：以**实现**为准撰写文档，并记录到 design 的 Open Questions，不改代码。
- ~~双语目录布局的最终选型~~：round 2 已决策为语言并列子目录（见 Frozen Decisions），否决理由已记入 Rejected Options。
- ~~两个语言版本中散文部分的等价程度要求~~：round 2 已决策为"只保证结构化事实等价，散文不做逐句比对"。若后续发现中文散文实际落后严重，可考虑追加"段落数量相等"一类弱结构断言——本轮不做。
- 新增第三种语言时，字段表表头词映射与跨语言两两比对是否需改为"以 en 为基准逐一比对"？本轮只支持 zh/en，按两两比对实现，扩展时再改。

## Artifact Notes
- `proposal.md`：Why 部分的缺口统计基于当前 `README.md` 与 `src/loopspec/cli.py`（10 个子命令）、`models.py`（`WorkflowConfig` 6 字段）、`errors.py`（15 个错误码）。
- `proposal.md`（round 1 之后定点同步，**未被归档**）：`proposal` 节点不在 `approval` 的回退闭包内（`on_fail.reset: [specs, design]`），因此 round 1 版本未进入 `.attempts/round-001/`，而是就地更新了 What Changes 的文件清单（改为双语并列 + 每语言 7 篇）、Capabilities 中 `usage-docs` 的描述（补入双语等价性）、Impact 的新增文件清单（15 文档 + 1 测试）与维护成本段。原因是不同步会让 `proposal.md` 与 round 2 的 `design.md`/`specs` 互相矛盾，而 `apply` 节点会读取全部产物。Why 一节未改动——双语要求不改变问题陈述。
- `design.md`：`docs/llms.txt` 的开放问题已在 D2 收口为"不需要"；新增 Security Notes 一节（无凭据、只解析不执行、正面说明路径安全规则）供 security gate 审阅。
- `specs/usage-docs/spec.md`：13 条 ADDED 需求，覆盖文件清单、双读者写法约定、CLI/错误码/config/schema 四类完整覆盖、示例可校验、一致性校验的单向性与安全边界、默认值对齐、Agent 契约、内置工作流、README 收敛、示例不含凭据。
- `tasks.md`：4 组 25 个任务（采集事实源 → 撰写 7 篇文档 → 一致性测试 → 收敛验收）。三处安全相关约束已在任务描述中显式标注供 security gate 定位：1.1/3.5 只在临时目录操作不污染工作区、3.5 只解析不执行 shell、3.8 断言示例不含凭据。
- `approval`（round 1 首次抵达时）：**未产出任何 verdict 文件**。原因是本次运行环境无交互提问工具，无法取得人类决定；不是失败，也不是批准。其后人类给出双语要求，遂写入 `approval/changes-requested.md`。
- `apply/report.md`：实现完成。新增 15 份文档（`docs/README.md` + 每语言 7 篇）与 `tests/test_docs_consistency.py`（40 条断言）；修改 `README.md`（收敛为入口）与 `Makefile`（新增 `docs-check`）；`src/loopspec/**` 未改动。测试由 505 passed 增至 545 passed。已做变异检查确认断言非空转。round 2 security 的 4 条建议全部落地（含把 `--json` 样例的绝对路径替换为 `/path/to/project/...`，并新增 `home-path` 凭据规则拦截此类泄漏）。三处偏离设计已记录：`gate.*` 三节从四级标题降为三级、一致性测试的语言参数化一次写全、新增两条把已有需求补齐为可测的结构断言。
- 实现期发现的实现侧问题（**未改代码**，本变更范围排除 `src/loopspec/**`）：`cli.bulk_archive` 的 `--complete` 选项被声明但函数体从未读取，已完成的 change 本来就总是候选，因此传它不改变任何行为。文档如实记录为"为与 `--exhausted` 对称而接受"，是否清理留给后续变更。
- `approval/approved.md`（round 2）：APPROVED。人类逐字回复"approve"。verdict 文件中记录了呈现给人类的完整 round 2 摘要（含双语布局与规范源两项决策的否决理由、等价性如何可测、两项明确接受的缺口、security 复审结论与新识别的绝对路径问题、以及 `proposal.md` 定点同步的主动告知）。进入 `apply` 时必须携带的 3 条非阻塞事项来源于 `security/pass.md` 而非人类反馈。
- `security/pass.md`（round 1 版本，见 `.attempts/round-001/security/pass.md`）：PASS。4 条非阻塞建议：(1) `schema-dir` 示例物化前用 `paths.is_safe_relative_path` 校验文件名；(2) 凭据断言失败时只报 `文件:行号` 不回显命中内容；(3) 任务 1.1 采集样例时每条命令显式传 `--home <tmpdir>`，避免 `archive`/`rollback` 误作用于仓库内真实工作流主目录；(4) 未来可对错误码/字段两类闭集追加反向断言。前 3 条已在 round 2 的 `design.md` 与 `tasks.md` 中落地，第 4 条在跨语言维度被部分采纳。
- `security/pass.md`（round 2 复审）：PASS。确认双语化未引入新安全面（无翻译服务调用、无新依赖、无构建期合成），并逐条核对 round 1 的 4 条建议均已处置。4 条新的非阻塞建议留待 `apply`：(1) 链接断言显式跳过 `http`/`https`/`mailto` 等外部 scheme，防止后续被误升级为网络可达性探测；(2) 跨语言逐字比对失败时优先报"文件对 + 块序号 + 首个差异行号"而非整块 diff；(3) **本轮新识别**——`loopspec status`/`instructions` 的 `--json` 样例含 `resolvedOutputPath` 等绝对路径，直接粘入文档会把本机 home 路径（含用户名）写进仓库，与"示例不得含真实用户标识"相抵，采集后须替换为占位根如 `/path/to/project/...`，并考虑在凭据检查中加"疑似本机 home 路径"规则；(4) 单向覆盖与散文双语漂移的边界不可误读为宽松。
- `design.md`（round 2 重写）：新增 D1 双语布局决策与 D2 规范源决策，D6 一致性测试改为"前四组按语言分别执行 + 第五组跨语言等价（7 项 a–g）"，Non-Goals 中的"不做 i18n"已改写，Security Notes 采纳 round 1 security 审阅的全部 4 条建议。round 1 版本见 `.attempts/round-001/design.md`。
- `specs/usage-docs/spec.md`（round 2 重写）：14 条需求 / 53 个 Scenario。相比 round 1 新增「双语版本的等价性」需求，重写「文档集的双语布局与文件清单」，其余需求全部加上"两个语言版本同等适用"的限定。round 1 版本见 `.attempts/round-001/specs/usage-docs/spec.md`。
- `tasks.md`（round 2 重写）：6 组 40 个任务（采集事实源 → 英文版 7 篇 → 一致性测试仅 en → 中文版 7 篇 + 语言入口 → 双语等价断言 → 收敛验收）。安全相关约束已在任务描述中显式标注：1.1 每条命令显式传 `--home <tmpdir>`、3.5 物化前校验相对路径安全性且只解析不执行 shell、3.8 凭据断言失败不回显内容。round 1 版本见 `.attempts/round-001/tasks.md`。
- `approval/changes-requested.md`：round 1 - changes requested。人类逐字反馈仅一句"补充，文档提供 zh/en 两个语言版本约束"，无限定条件；verdict 文件中已把它拆成 6 条自包含、可执行的修改项（双语版本、目录布局决策、双语等价性需求、测试断言扩展、任务重排、删除"不做 i18n"的 Non-Goal），并记录了呈现给人类的 round 1 摘要与建议方向。
