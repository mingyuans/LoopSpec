# Plan 001

本 Plan 的假设、偏离、待解决问题和返工认识；引擎在末尾追加生命周期事件。
优先用 `loopspec state add` 追加；`loopspec change status` 原样输出全文，引擎不解析内容。

## 假设

<!-- 尚未验证、暂时据此推进的前提与验证方式；证实或推翻时追加新条目。用 `loopspec state add --section assumption` 追加。 -->

## 偏离

<!-- 实际执行相对设计的重要差异、原因及影响。用 `loopspec state add --section deviation` 追加。 -->

## 待解决问题

<!-- 本方案中的具体未知项；解决或移交时追加新条目并引用原问题。用 `loopspec state add --section open-question --scope plan` 追加。 -->

## 返工记录

<!-- Gate FAIL 并 rollback 后：失败后的认识与修复方向。N 为该 Gate 的返工轮次，S 为对应 rollback 的全局序号，由框架推导。用 `loopspec state add --section rework` 追加。 -->
- 2026-11-19 [be/security/check] attempt 1（rollback #1）：安全审查 FAIL：存储根中间符号链接、固定 tag 未校验与 commit 绑定（定义不再出现在 diff，lock 成为唯一可审阅面）、LLM 守卫放行 registry 后可拉取任意仓库、lock/计划解析 RecursionError。修复方向：directory() 逐级 O_NOFOLLOW 校验存储根；fetch_commit 带 tag 时先 ls-remote 校验 tag→commit；守卫要求 config 中 url 等于测试注入的 LOOPSPEC_LLM_REGISTRY_URL；lock 用 parse_yaml，计划解析捕获 RecursionError。
- 2026-11-19 [be/security/check] attempt 2（rollback #2）：第 2 轮安全审查 FAIL：_private_dir 先 mkdir 后检查符号链接；缓存命中不校验 lock tag 绑定；LLM 守卫逐行扫描 config 可被流式 YAML 绕过。修复方向：从最深已存在祖先用 directory(create=True) 逐级 O_NOFOLLOW 创建；manifest 记录已验证 tag，命中但 tag 未验证时在线校验；守卫调用被测 CLI 的 load_config 解析 url。隐式联网拉取为已接受设计风险，需写进文档。
- 2026-11-19 [be/security/check] attempt 3（rollback #3）：第 3 轮安全审查 FAIL：守卫按 token 猜 --home 可被 --note 值误导；固定 tag 项目允许 lock 省略 tag 跳过校验。修复：守卫对默认 home 与所有 --home 候选都校验；pinned() 在 config 固定 tag 时要求 lock.tag 相等。祖先目录竞态记为剩余风险。
- 2026-11-19 [be/review/check] attempt 1（rollback #4）：代码审查 FAIL：update 快速路径只比 commit 导致固定 tag 改名后卡死；registry_spec 严格加载 config 造成非 registry 项目回归；来源切换预览不一致；instructions 多次解析 lock；lock 体积未在 update 检查；超大 lock 错误码回归。修复方向见 review fail 报告；source 字段保留（兼容新增）。

## 事件

<!-- 引擎自动追加生命周期事件，请勿手工编辑，也勿在此段之后新增段落。 -->
- 2026-11-19T03:48:24+00:00 · 已为 Change registry-global-store 创建 Plan 001 草稿 · 状态：待批准 · 计划定义校验值（digest）：b64310fc · 备注：registry 定义迁到用户级全局存储，项目只保留 lock
- 2026-11-19T03:51:23+00:00 · 已更新 Change registry-global-store 的 Plan 001 草稿 · 状态：待批准 · 计划定义校验值（digest）：558dae0a · 备注：registry 定义迁到用户级全局存储，项目只保留 lock
- 2026-11-19T03:52:44+00:00 · 已批准 Change registry-global-store 的 Plan 001 · 计划版本：1 · 状态：可执行 · 计划定义校验值（digest）：558dae0a
- 2026-11-19T04:28:00+00:00 · 已对 Change registry-global-store 的 Plan 001 执行返工重置（不回退业务代码） · 来源 Gate：be/security/check · 返工记录全局序号：1 · 重置范围：assurance/check, be/code/implement, be/review/check, be/security/check, be/tests/check, qa/test
- 2026-11-19T04:57:48+00:00 · 已对 Change registry-global-store 的 Plan 001 执行返工重置（不回退业务代码） · 来源 Gate：be/security/check · 返工记录全局序号：2 · 重置范围：assurance/check, be/code/implement, be/review/check, be/security/check, be/tests/check, qa/test
- 2026-11-19T05:08:49+00:00 · 已对 Change registry-global-store 的 Plan 001 执行返工重置（不回退业务代码） · 来源 Gate：be/security/check · 返工记录全局序号：3 · 重置范围：assurance/check, be/code/implement, be/review/check, be/security/check, be/tests/check, qa/test
- 2026-11-19T05:18:34+00:00 · 已对 Change registry-global-store 的 Plan 001 执行返工重置（不回退业务代码） · 来源 Gate：be/review/check · 返工记录全局序号：4 · 重置范围：assurance/check, be/code/implement, be/review/check, be/security/check, be/tests/check, qa/test
