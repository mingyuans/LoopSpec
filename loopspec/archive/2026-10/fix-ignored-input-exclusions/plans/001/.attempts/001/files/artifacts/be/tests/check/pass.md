---
verdict: PASS
summary: "本轮固定输入下 make test 922 passed，忽略/排除相关定向用例 108 passed，ruff 与 mypy 通过"
---

# 后端测试：通过

## 审查输入
- 轮次 `001.1:be/tests/check:1`，基线 `7531fb87`，scopeDigest `1d4bd78b2170…`
- 范围内 9 个文件：`src/loopspec/workflow_{assurance,diff,evidence,models,planning,runtime}.py`，`tests/test_workflow_{assurance,diff,planning}.py`
- 本轮 `warnings` 为空

## 执行的测试
- `make test`：922 passed（6 分 35 秒）
- `uv run pytest tests/test_workflow_diff.py tests/test_workflow_planning.py tests/test_workflow_assurance.py tests/test_docs_consistency.py -q`：108 passed
- `make lint`：ruff All checks passed；mypy Success，31 个源文件没有问题
- 覆盖的验收条件：
  - 告警：不抛错、上限 20 条且排序、被忽略文件不影响摘要、写进 assurance 报告与诊断、`gate begin/record/status` 输出 `warnings`、带告警的 FAIL 报告可被解析
  - excluded_paths：旧字段迁移提示、名字匹配含文件名（`.DS_Store`/`__pycache__`/`*.log` 的正反例）、完整路径匹配（`docs/**`、`loopspec/config.yaml`）、被忽略路径命中后不告警、非法模式被拒绝
  - `<home>/.cache` 自动排除，根目录 `.cache/` 仍告警

## 剩余风险
- 带告警的 assurance FAIL 只验证了报告能被 status 解析，没有实际执行 `plan rollback`（夹具里的 assurance 没有 `on_fail`）；rollback 复用同一个 `failure_report()`。
- `*.md` 这一条只通过 `excluded_paths: ['*.md']` 的匹配语义间接覆盖，没有在 assurance 层单独测 `builtin/skills/*.md`。
