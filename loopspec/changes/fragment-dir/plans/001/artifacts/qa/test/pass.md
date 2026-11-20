---
verdict: PASS
summary: "6 条验收条件全部满足；真实 registry 快照中 qa/clarify 的 fragmentDir 指向 qa-testcases，指令引用的两个规则文件均可解析"
---

# 验收测试：通过

## 验收条件核对

- [x] registry 模式 `fragmentDir`/`fragmentName`/`instructionPath`/`templatePath`：在锁定 aftership-channels registry 7b6cc1b 的演示项目中，用 `.venv/bin/loopspec node instructions -c DEMO1 -n qa/clarify --json` 验证：`fragmentName` 为 `qa-testcases`（`fragment` 仍为实例 `qa`），`fragmentDir` 存在且位于 `~/.loopspec/registry` 下，`instructionPath`、`templatePath` 的文件内容与 `instruction`、`template` 字段逐字节相同；`test_registry_fragment_paths_point_into_the_verified_snapshot` 通过。
- [x] 指令中的引用可解析：指令里的 `doc-writing-rules.md`、`case-writing-rules.md` 在 `fragmentDir/references/` 中找到；其余 `cases-coverage.md`、`exploration.md`、`prd_clarify.md` 是节点产物名，不属于 fragment 文件，符合预期。
- [x] 本地模式：`test_local_fragment_paths` 与 BDD「执行指令给出节点所属 Fragment 的绝对目录与文件路径」通过。
- [x] 嵌套 fragment：`test_nested_fragment_names_the_defining_fragment`（`be/code/implement` → `backend-code`）通过。
- [x] Gate 模板路径：`test_gate_template_paths` 通过。
- [x] 文本报告与兼容：`test_text_report_shows_the_paths` 通过；JSON 只新增键（演示输出键集合为旧键加 5 个新键）；全量测试与 `make test-llm` 通过（见 be/tests/check）。

## 执行的测试

- 上述 `node instructions --json` 实测脚本（读取 JSON、比对文件内容、在 `fragmentDir` 下按文件名查找引用）。
- 引用 be/tests/check 中的 ruff、mypy、pytest（1765 passed）与 `make test-llm`（13 passed）结果。

## 剩余风险

- 无阻塞项。上游 registry 中缺失的 `fragments/README.md` §4 引用仍无法解析（不在本次范围）。
