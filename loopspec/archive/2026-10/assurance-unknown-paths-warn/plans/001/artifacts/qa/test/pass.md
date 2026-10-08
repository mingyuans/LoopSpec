---
verdict: PASS
summary: "安装后的 CLI 端到端验证通过：规则为 warn 时未匹配路径只告警并写进报告，项目规则为 fail 时合并结果仍判 FAIL"
---

# 验收测试：通过

## 验收条件核对
- [x] 规则文件可以写 `warn`，读取正常：临时仓库把 `change-assurance/rules.yaml` 改为 `unknown_paths: warn` 后，`plan create/approve` 和全部 Gate 正常。非法值和默认 `fail` 由单元测试覆盖。
- [x] 单份规则为 `warn` 时字段不再丢失：场景 1 中未匹配的 `scripts/tool.sh` 没有导致 FAIL。
- [x] 任一规则文件为 `fail` 即 `fail`：场景 2 中 Fragment 规则为 `warn`、项目规则 `project-rules.yaml` 为 `fail`，assurance 判 FAIL，`unknown_paths=['scripts/tool.sh']`，`warnings=None`。
- [x] warn 模式通过并告警：场景 1 判 PASS，`unknown_paths=['scripts/tool.sh']`，`warnings={'unknownPaths': ['scripts/tool.sh'], 'unknownTotal': 1}`，系统 `pass.md` 为 `{"summary":"全量 Diff 保障通过；1 条告警：以下改动路径没有匹配任何保障规则，未纳入审查：scripts/tool.sh","verdict":"PASS"}`，`change status` 为 `complete`。
- [x] warn 模式下其他缺口仍判 FAIL，FAIL 报告可解析：单元测试 `test_warn_mode_still_fails_on_other_gaps` 通过；场景 2 的 FAIL 报告也能被 status 解析（status=active）。
- [x] fail 模式行为不变：场景 2 和单元测试 `test_fail_mode_has_no_unknown_warning`、原有 unknown 用例通过。
- [x] 上限 20 条：单元测试 `test_unknown_warning_list_is_capped` 通过。
- [x] 两类长告警的长度上限：单元测试 `test_combined_long_warnings_keep_failure_summary_within_limit` 通过。
- [x] `make test` 933 passed，`make lint` 通过，文档一致性测试通过（在 be/tests 轮次执行）。

## 执行的测试
- `make install-local`：把当前源码安装为全局 `loopspec`
- 在 scratchpad 中执行 `python3 -I qa/e2e_warn.py qa/warn`，两个临时仓库的步骤都是：`git init` → `loopspec init --tools none` → 把 Fragment 规则改为 `warn`（场景 2 再加上 `unknown_paths: fail` 的项目规则）→ `change new` → `plan create/approve`（backend-implementation + change-assurance）→ 修改 `backend/app.py`，新增未匹配的 `scripts/tool.sh` → 三个代码 Gate begin/record → assurance record → status。结果见上文。

## 剩余风险
- 同一份规则文件同时被 Plan 和项目引用时会去重，沿用原有逻辑，没有单独做端到端验证。
