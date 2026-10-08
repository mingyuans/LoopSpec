## 背景

assurance 规则文件（如 `fragments/change-assurance/rules.yaml`）的 `unknown_paths` 用来规定：改动路径不匹配任何规则时怎么处理。现状：

- **只能填 `fail`**：模型是 `unknown_paths: Literal["fail"]`（`src/loopspec/workflow_models.py`），填其他值读取时报错。
- **判定写死**：`diagnose()` 把 `unknown_paths` 与 `missing_evidence`、`stale_evidence`、`missing_fragments` 一起算作失败条件（`src/loopspec/workflow_assurance.py`）。
- **字段实际不生效**：`assurance_rules()`（`src/loopspec/workflow_planning.py`）合并 Plan 与项目的规则时新建 `AssuranceRules(rules=...)`，没有带上 `unknown_paths`，文件里写什么最后都是默认值。

人已决定：`unknown_paths` 需要能配置为 `warn`。不匹配任何规则的改动只告警，不让 assurance 失败，由人工 review 把关。

## 用户场景

- 项目里有一些零散路径（新加的脚本、配置文件）暂时没有对应的审查规则。维护者希望 assurance 照常通过，同时在报告里能看到这些"没人审查"的路径，于是在规则文件里写 `unknown_paths: warn`。
- 项目保持默认（不写或写 `fail`）时，行为和现在完全一样。
- 某个 Fragment 自带的规则文件写了 `warn`，项目规则文件是 `fail`：不应因为 Fragment 自带的规则而放宽项目的约束。

## 范围

1. **模型**：`AssuranceRules.unknown_paths` 改为 `Literal["fail", "warn"]`，默认 `fail`。
2. **合并**：`assurance_rules()` 合并多份规则文件时保留 `unknown_paths`。只要有任何一份是 `fail` 就取 `fail`，只有全部为 `warn` 时才取 `warn`。
3. **判定**：`diagnose()` 在 `unknown_paths: warn` 时：
   - 不匹配规则的路径照样列进诊断的 `unknown_paths`，但**不计入**失败条件；
   - 诊断的 `warnings` 增加 `unknownPaths`（排序后最多 20 条）与 `unknownTotal`。和已有的 `ignoredPaths` / `ignoredTotal` 放在同一个对象里；两类都没有时，`warnings` 仍为 `None`。
   - `unknown_paths: fail` 时行为不变，`warnings` 里不出现 `unknownPaths`。
4. **报告**：系统报告的 `summary` 追加未匹配路径的告警文本，例如"N 条告警：以下改动路径没有匹配任何保障规则，未纳入审查：……"。与被忽略路径的告警共用同一个总长度上限（`MAX_WARNING_CHARS = 8000`），保证 FAIL 报告不超过 `FailureReport` 的 16384 字符限制。
5. **文档**：中英文 `configuration.md` 的保障规则部分写明 `unknown_paths` 的两个取值、合并规则（任一 `fail` 即 `fail`）和告警位置。`cli-reference.md` 的 `gate record` 段落提到未匹配路径的告警。
6. **测试**：补充单元测试，见验收条件。

## 非目标

- 不加规则级 `severity`，`missing_fragments` 的严重级别不变。
- 不修改 `missing_evidence` 和 `stale_evidence`，它们仍然判 FAIL。
- 不修改本仓库 `loopspec/fragments/change-assurance/rules.yaml`（来自 registry，本地改会和 `registry update` 冲突）和内置模板 `builtin/fragments/change-assurance/rules.yaml`，两者都保持 `fail`。要在本仓库启用 `warn`，改上游 loopspec-fragments 仓库。
- 代码 Gate 的 `gate begin/record` 和 `change status` 的输出不增加未匹配路径的告警（这些命令不做规则判定）。

## 验收条件

- [ ] 规则文件写 `unknown_paths: warn` 能被正常读取；写 `fail` 或不写，结果为 `fail`；写其他值（如 `ignore`）读取时报错。
- [ ] 只有一份规则文件且为 `warn` 时，合并结果是 `warn`（证明字段不再丢失）。
- [ ] Plan 引用的规则文件为 `warn`、项目规则文件为 `fail` 时，合并结果是 `fail`；两份都为 `warn` 时是 `warn`。
- [ ] `unknown_paths: warn`、存在未匹配路径、其他检查都通过时：assurance 判 PASS；诊断的 `unknown_paths` 仍列出该路径；`warnings` 中 `unknownPaths` 包含该路径，`unknownTotal` 正确；系统 `pass.md` 的 `summary` 提到这条告警和路径。
- [ ] `unknown_paths: warn`，但同时存在 `missing_evidence`、`stale_evidence` 或 `missing_fragments` 时，assurance 仍判 FAIL，`fail.md` 的 `summary` 同时包含未匹配路径的告警，status 能正常解析这份报告。
- [ ] `unknown_paths: fail`（默认）时行为不变：未匹配路径导致 FAIL，`warnings` 中没有 `unknownPaths`。已有的 `test_unknown_directory_and_handwritten_assurance_pass_are_not_accepted` 等测试继续通过。
- [ ] 未匹配路径超过 20 条时（测试中 25 条），`unknownPaths` 只列排序后的前 20 条，`unknownTotal` 为 25。
- [ ] 未匹配路径和被忽略路径的告警同时存在且都很长时，系统 FAIL 报告的 `summary` 仍能通过 `FailureReport` 校验。
- [ ] `make test` 全部通过，`make lint` 通过，`tests/test_docs_consistency.py` 通过。

## 风险

- **放宽门禁**：设为 `warn` 后，不匹配任何规则的业务代码改动不再阻断 assurance，只靠报告中的告警和人工 review。应对：默认保持 `fail`；多份规则合并时任一 `fail` 即 `fail`，不让 Fragment 自带的规则放宽项目约束；规则文件的修改本身在 PR 中，由人工 review。
- **已有证据**：assurance 证据绑定的是 Plan 摘要、diff 摘要和报告的 hash；这次只改了判定，没改摘要的计算方式。已经记录的 PASS 不受影响。把规则从 `fail` 改成 `warn` 后，需要重新执行 assurance 才会反映新的判定，这符合"规则实时读取"的现有设计。
- **报告长度**：两类告警共用 8000 字符的上限，按"先被忽略路径、后未匹配路径"的顺序填充，超出部分只给条数。
