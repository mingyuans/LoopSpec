## 背景

命令改为默认文本输出后，每节都带说明段：引用块怎么读、`fragmentDir`、`resolvedOutputPath`、STATE PROTOCOL 的命令与规则、并行 NEXT STEPS、Gate 协议、rollback、修订预览、归档两段的输入与删除项。5 个 skill 仍逐条复述这些读法，与输出重复，增加模型阅读负担。用户（2026-11-20）选择「审视全部 5 个 skill 去重」。

## 用户场景

模型读 skill 获得流程与红线，读命令输出获得具体读法与下一步；两者不重复、不冲突。

## 范围

- `builtin/skills/{new,continue,archive,bulk-archive,update-registry}.md`：删除命令输出已说明的读法与机制描述。
- 保留：人工确认与不代替人表态、HUMAN 决策适用范围、`taskProgress` 一次一项、并行 sub agent 的权限边界、Gate 只能经协议记录、assurance 只认系统检查、rollback 只按 `on_fail`、修订/重规划需同意、不手改工作流文件、memory 读取与维护规则（含 continue 与 archive 共享且由测试固定一致的维护流程，archive 的 CLI 指引直接取自它）、state 手工编辑规则、registry 审阅要求。
- 生成副本经 `uv run loopspec` 同步。

## 非目标

- 不改 CLI 代码与输出；不改 memory 维护流程正文。

## 验收条件

- [ ] 5 个 skill 不再描述输出格式细节（begin/end 引用、字段命名、`fragmentDir` 解析方式、`resolvedOutputPath`、round id 性质、`.attempts` 机制等），总词数下降。
- [ ] 被删内容都能在对应命令的文本输出说明段中找到（逐条核对表）。
- [ ] `test_skill_templates.py` 等现有测试通过（红线短语仍在）。
- [ ] `make test-llm` 全部通过。

## 风险

模型行为回归：由 LLM E2E 覆盖 new/continue/archive/update-registry 主要路径。
