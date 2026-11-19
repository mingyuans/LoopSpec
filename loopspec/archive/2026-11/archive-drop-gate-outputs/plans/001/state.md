# Plan 001

本 Plan 的假设、偏离、待解决问题和返工认识；引擎在末尾追加生命周期事件。
优先用 `loopspec state add` 追加；`loopspec change status` 原样输出全文，引擎不解析内容。

## 假设

<!-- 尚未验证、暂时据此推进的前提与验证方式；证实或推翻时追加新条目。用 `loopspec state add --section assumption` 追加。 -->
- 2026-11-19 [requirements/proposal] 历史清理只覆盖有 plans/ 的新格式归档；1.x schema 旧格式归档（security/、approval/ 等）无法从现有定义判定 Gate 产物，不清理。验证：最终报告向人说明。

## 偏离

<!-- 实际执行相对设计的重要差异、原因及影响。用 `loopspec state add --section deviation` 追加。 -->

## 待解决问题

<!-- 本方案中的具体未知项；解决或移交时追加新条目并引用原问题。用 `loopspec state add --section open-question --scope plan` 追加。 -->

## 返工记录

<!-- Gate FAIL 并 rollback 后：失败后的认识与修复方向。N 为该 Gate 的返工轮次，S 为对应 rollback 的全局序号，由框架推导。用 `loopspec state add --section rework` 追加。 -->

## 事件

<!-- 引擎自动追加生命周期事件，请勿手工编辑，也勿在此段之后新增段落。 -->
- 2026-11-19T14:51:58+00:00 · 已为 Change archive-drop-gate-outputs 创建 Plan 001 草稿 · 状态：待批准 · 计划定义校验值（digest）：306db557 · 备注：change archive 归档时删除 Gate 产物
- 2026-11-19T14:53:40+00:00 · 已批准 Change archive-drop-gate-outputs 的 Plan 001 · 计划版本：1 · 状态：可执行 · 计划定义校验值（digest）：306db557
