# Plan 001

本计划执行中的决策与备注。人与 LLM 可直接编辑；`loopspec change status` 原样输出全文，引擎不解析。

## 人工决策

<!-- 节点要求询问人时：- YYYY-MM-DD [节点 id] 问：…；答：… -->
- 2026-10-12 [be/code/implement] 问：测试计划 AC1–AC10 与行为规则（默认 N、非交互跳过、`--update-resources`、release notes 升级步骤加该选项）是否确认；答：approve

## 假设与偏离

<!-- 执行中的假设、与设计的偏差及原因：- YYYY-MM-DD [节点 id] … -->
- 2026-10-12 [be/code/implement] 假设：符号链接形式的 fragments/profiles 不计为“已存在”，交由 install_resources 按原逻辑拒绝（unsafe_path），保持既有安全行为。

## 返工记录

<!-- Gate FAIL 并 rollback 后：- YYYY-MM-DD [Gate id] attempt N：失败原因摘要；修复方向 -->

## 事件

<!-- 引擎在此之后追加生命周期事件，勿在此段之后新增段落。 -->
- 2026-10-12T10:24:14+00:00 · create · digest e2093548 · note: init 时已有 fragments/profiles 需确认后才更新
- 2026-10-12T10:24:52+00:00 · approve · revision 1 · digest e2093548
