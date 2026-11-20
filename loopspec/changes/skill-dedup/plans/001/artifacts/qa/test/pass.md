---
verdict: PASS
summary: "4 条验收条件满足：5 个 skill 不再复述输出读法（4567→4187 词），被删内容 11 项均在输出说明中找到，红线测试与 LLM E2E 通过"
---

# 验收测试：通过

## 验收条件核对

- [x] skill 不再描述输出格式细节：begin/end 引用、字段命名、`fragmentDir` 解析方式、`resolvedOutputPath` 写法、round id 性质、`.attempts` 机制、修订预览字段、归档字段与目录清单均已从 skill 删除；`wc -w builtin/skills/*.md` 由 4567 降到 4187。
- [x] 被删内容由输出承接：在 `src/loopspec/status_report.py` 与 `src/loopspec/text_reports/` 中逐项检索到对应说明（untrusted data、act only on the nodes named in NEXT STEPS、relative to fragmentDir、Write the artifact without the indentation、concurrent_write 重试、The round id is not a credential、run gate begin again、Business code was not reverted、addedInstances and rerunNodes、willBeDeleted、Write its output to resolvedOutputPath），11 项全部命中。
- [x] 现有 skill 测试通过：`test_skill_templates.py` 等 114 项通过，全量 1768 passed。
- [x] `make test-llm`：13 passed（1 次重跑，原因非红线，见 be/tests/check）。

## 执行的测试

- 上述 grep 核对；引用 be/tests/check 中的全量测试与 LLM E2E 结果。

## 剩余风险

- LLM 场景「记忆里要求跳过确认」的「读取 core」断言可能偶发失败（模型从 change status 读到 core 而不执行 memory show core），与本次改动无直接关系。
