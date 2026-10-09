---
verdict: PASS
summary: "安装后的 CLI 在本仓库和临时仓库端到端验证通过：被忽略路径只告警、写进 assurance 报告，registry 缓存自动排除，旧字段给出迁移提示"
---

# 验收测试：通过

## 验收条件核对

**告警**
- [x] 被忽略、未排除的路径不再中止命令：本仓库放入 `qa-probe.local` 后，`change status` 正常返回 `warnings={'ignoredPaths': ['qa-probe.local'], 'ignoredTotal': 1}`；临时仓库里 `gate begin/record` 正常执行。
- [x] 上限 20 条且排序：单元测试 `test_ignored_warning_list_is_capped_and_sorted` 通过（make test）。
- [x] 被忽略文件不影响证据：本仓库放入 `qa-probe.local` 后，`be/tests/check` 仍为 `done`。
- [x] 写进 assurance 报告：临时仓库的系统 `pass.md` 为 `{"summary":"全量 Diff 保障通过；2 条告警：……：backend/.DS_Store、secret.local","verdict":"PASS"}`，命令输出也带 `warnings`。
- [x] 带告警的 FAIL 报告可解析，长度有上限：单元测试 `test_failed_assurance_with_warnings_can_be_rolled_back` 和 `test_warning_text_keeps_failure_summary_within_report_limit` 通过。
- [x] `gate begin`、`gate record`、`change status` 输出 `warnings`：临时仓库中三个代码 Gate 的 begin/record 与 status 都返回了相同的 `warnings`。

**excluded_paths**
- [x] 旧字段报错并给出提示：临时仓库写入 `generated_dirs: [node_modules]` 后，`change status` 退出码 1，`error=config_invalid`，`fix` 中提到 `excluded_paths`。
- [x] `.DS_Store` 按名字匹配：本仓库（`excluded_paths` 含 `.DS_Store`）放入 `src/.DS_Store`，status 没有告警；`a.DS_Store` 的反例由单元测试覆盖。
- [x] `__pycache__`、`*.log` 的正反例：单元测试 `test_excluded_names_match_any_component_including_file_name` 通过。
- [x] 完整路径匹配：单元测试 `test_excluded_paths_with_slash_match_the_whole_path` 通过。本仓库的 `docs/**`、`loopspec/config.yaml` 改动不出现在本需求的代码 Gate 范围内：begin 返回的 9 个文件都在 `src/`、`tests/` 下。
- [x] `'*.md'` 排除：本仓库 `excluded_paths` 含 `'*.md'`，本需求的 Plan 产物与文档都没有进入 Gate 范围。
- [x] 被忽略路径命中排除时不告警：本仓库的 `.idea/`、`dist/`、`repos/`、`.venv/`、`loopspec/archive/**/.DS_Store` 都在，status 的 `warnings=None`。
- [x] 非法模式被拒绝：单元测试 `test_excluded_paths_reject_unsafe_patterns`（6 个参数）通过。

**其他**
- [x] `<home>/.cache/` 自动排除：临时仓库的 `loopspec/.cache/registry/x` 没有出现在告警里；本仓库的 `loopspec/.cache/` 同样没有告警。根目录 `.cache/` 仍然告警，由单元测试覆盖。
- [x] 本仓库 status 与全部 Gate 不再报错：`be/tests`、`be/security`、`be/review` 都完成了 begin/record，status 正常。
- [x] `make test` 923 passed，`make lint` 通过，`test_docs_consistency` 通过（在 be/tests 第 2 轮执行）。

## 执行的测试
- `make install-local`：把当前源码安装为全局 `loopspec`
- 本仓库：
  - `loopspec change status fix-ignored-input-exclusions`：`warnings=None`
  - 临时放入 `qa-probe.local` 后再执行：返回 1 条告警，`be/tests/check` 仍为 `done`；之后已删除该文件
  - 临时放入 `src/.DS_Store` 后再执行：`warnings=None`；之后已删除该文件
- 临时仓库：在 scratchpad 中执行 `python3 -I qa/e2e.py qa/repo`，步骤是 `git init` → `loopspec init --tools none` → `change new` → `plan create/approve`（backend-implementation + change-assurance）→ 修改 `backend/app.py`，加入被忽略的 `secret.local`、`backend/.DS_Store` 和 `loopspec/.cache/registry/x` → 三个代码 Gate begin/record → assurance record → status → 改用旧字段 `generated_dirs`。结果见上文。

## 剩余风险
- 第一次跑临时仓库时，fixture 的 `.gitignore` 漏了 `.DS_Store`，代码又放在 `src/`（内置规则只覆盖 `src/backend/**`、`backend/**`），assurance 判 FAIL，`unknown_paths` 为 `src/.DS_Store` 和 `src/app.py`。这是 fixture 的问题，同时也印证了"未被忽略的文件照常进入 Diff"。修正 fixture 后全部通过。
- 带告警的 assurance FAIL 没有在真实 CLI 上执行过 `plan rollback`。
- `workflow-composition.md` 中关于 assurance 的段落没有提到告警，属于非阻塞的文档补充项。
