# Plan 001

本计划执行中的决策与备注。人与 LLM 可直接编辑；`loopspec change status` 原样输出全文，引擎不解析。

## 人工决策

<!-- 节点要求询问人时：- YYYY-MM-DD [节点 id] 问：…；答：… -->

## 假设与偏离

<!-- 执行中的假设、与设计的偏差及原因：- YYYY-MM-DD [节点 id] … -->

## 返工记录

<!-- Gate FAIL 并 rollback 后：- YYYY-MM-DD [Gate id] attempt N：失败原因摘要；修复方向 -->
- 2026-10-12 [be/review/check] attempt 1：安装阶段 OSError（安装器缺失/不可执行、临时目录不可写）未映射，CLI 以 traceback 退出，违反 {error,message,fix} 契约；修复：在 run_update 中映射为 update_installer_missing / update_install_failed，顺带修正 --check --version 的提示文案并补 CLI 传参测试。

## 事件

<!-- 引擎在此之后追加生命周期事件，勿在此段之后新增段落。 -->
- 2026-10-12T04:07:16+00:00 · create · digest 321f50cd · note: 新增 loopspec update：CLI 自升级（校验 checksum 后用 uv/pipx 安装）
- 2026-10-12T04:08:38+00:00 · approve · revision 1 · digest 321f50cd
- 2026-10-12T05:05:16+00:00 · rollback · gate be/review/check · attempt 1 · reset: assurance/check, be/code/implement, be/review/check, be/security/check, be/tests/check, qa/test
