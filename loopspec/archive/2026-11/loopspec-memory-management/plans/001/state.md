# Plan 001

本计划执行中的决策与备注。人与 LLM 可直接编辑；`loopspec change status` 原样输出全文，引擎不解析。

## 人工决策

<!-- 节点要求询问人时：- YYYY-MM-DD [节点 id] 问：…；答：… -->

## 假设与偏离

<!-- 执行中的假设、与设计的偏差及原因：- YYYY-MM-DD [节点 id] … -->

## 返工记录

<!-- Gate FAIL 并 rollback 后：- YYYY-MM-DD [Gate id] attempt N：失败原因摘要；修复方向 -->
- 2026-11-08 [be/security/check] attempt 1：保障 Diff 把整个 `memory/` 目录排除，非 topic 文件可绕过审查；另有扫描无条目上限、stat 竞态下静默返回空索引、`init` 遇悬空符号链接崩溃三个低风险问题；修复：Diff 只排除合法 topic 文件（`memory/<topic>.md`）、扫描总条目设上限、逐条处理竞态消失、`init` 用 lexists，先写失败测试，并同步 design 与 docs 的表述。
- 2026-11-08 [be/review/check] attempt 2：独立审查并经核实：limit 夹紧与“每个节点同摘要”两个测试名不副实、`memory list --all` 的 ignored 不受分页约束、title 无长度上限、Diff 排除不看文件类型（符号链接会被排除）、测试源码含字面量 U+2028、`summary()` 错误分支与 topic 上限边界缺测试；另有按 topic 名排序、`scandir` 提前终止、ignored 名字转义、`fix` 文案、skill 维护提示词重复的小问题。修复：逐条先写失败测试再改代码，并同步 design 与 docs。
- 2026-11-08 [be/review/check] attempt 3：复审核实：上一轮重构（按函数名去重）留下仍然空转的旧测试 `test_every_node_gets_the_same_memory_summary`；`workflow_diff` 的 `lstat` 只捕获 `FileNotFoundError`，目录被换成文件时抛裸 `NotADirectoryError`；`raise _refix(exc) from exc` 造成自引用 cause；`_refix` 对 EACCES 也提示符号链接；`pointer` 出错、status 在 topic 超限时的行为与 skill 提示词一致性测试有缺口。修复：先写失败测试，删除旧测试，`lstat` 捕获 `OSError`，仅在需要时改写异常，`_refix` 只处理 ELOOP/ENOTDIR，补齐缺口测试。

## 事件

<!-- 引擎在此之后追加生命周期事件，勿在此段之后新增段落。 -->
- 2026-11-08T07:24:39+00:00 · create · digest 94659f97 · note: 仅评估 memory 管理：requirements + design + assurance，不含实现
- 2026-11-08T07:26:42+00:00 · replace-draft · digest b64310fc · note: requirements→design→be implement→assurance
- 2026-11-08T07:27:05+00:00 · approve · revision 1 · digest b64310fc
- 2026-11-08T09:34:21+00:00 · rollback · gate be/security/check · attempt 1 · reset: assurance/check, be/code/implement, be/review/check, be/security/check, be/tests/check
- 2026-11-08T09:56:47+00:00 · rollback · gate be/review/check · attempt 2 · reset: assurance/check, be/code/implement, be/review/check, be/security/check, be/tests/check
- 2026-11-08T10:49:46+00:00 · rollback · gate be/review/check · attempt 3 · reset: assurance/check, be/code/implement, be/review/check, be/security/check, be/tests/check
