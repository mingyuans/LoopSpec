## 背景

loopspec CLI 的主要调用方是 MODEL（通过 loopspec skill 执行命令并阅读输出）。目前只有 `change status`、`graph`、`init`、`update`、`version` 默认输出文本；其余 27 个工作流命令只输出 JSON。JSON 中的大段 Markdown（`node instructions` 的 `instruction`、`template`，`memory show` 的 `content` 等）被转义成一行字符串（`\n`、引号转义），模型和人阅读都困难，也容易误读字段边界。

用户要求（2026-11-20）：所有 loopspec 命令默认输出文本模式，样式参考 `change status`；提供 `--json` 切回 JSON；AGENTS.md 写明「loopspec 命令都提供文本和 JSON 两种返回格式，默认文本」。实现方式由用户决定为「每个命令手写渲染器」。

## 用户场景

- MODEL 按 skill 执行 `loopspec node instructions -c <change> -n <node>`，直接读到分节的文本：节点概况、指令正文、模板正文、依赖、历史尝试、memory、state 记录命令，而不是转义的 JSON。
- MODEL 执行 `plan show`、`change archive`、`gate begin` 等命令，从文本里读到后续要用的值（`digest`、`archiveId`、`roundId`、下一步命令）。
- 脚本、测试或其他工具需要结构化数据时，加 `--json` 得到与现在完全一致的 JSON。
- 开发者新增命令时，从 AGENTS.md 得知必须同时提供文本（默认）与 `--json`。

## 范围

1. 以下命令默认输出文本，新增 `--json` 输出原 JSON（字段与结构不变）：
   - `memory list|show`
   - `change new|next|history|artifacts|archive`（含第一段与 `--confirm` 第二段）
   - `plan validate|create|show|list|approve|archive|rollback`
   - `node instructions`
   - `state add`
   - `gate begin|record`
   - `fragment list|show|validate`
   - `profile list|show|validate|save`
   - `registry update|apply`
2. 每个命令手写文本渲染器，遵守 `change status` 的文本契约：
   - 纯文本，无 ANSI、无颜色、无 Markdown 标题语法；`=== SECTION ===` 分节，每节有一段说明（告诉 MODEL 这节是什么、怎么用）；`--- 子块 ---`；`key: value` 字段。
   - 文本中保留 JSON 字段名作为标签（例如 `digest`、`archiveId`、`roundId`、`nextSteps`），skill 中「使用返回的 `<字段>`」的说法在文本模式下仍然成立。
   - 所有插值经 `sanitize` 处理，不可信或多行文本（state、memory、fragment 指令/模板、报告内容）以固定缩进引用，不能伪造分节。
   - 单一数据源：文本只来自 `--json` 会输出的同一 payload；测试固定每个命令的 payload 键集合，新增字段若未渲染也未声明省略则测试失败。
3. 文本模式下错误统一按 `change status` 的 `=== ERROR ===` 格式输出（`error`、`message`、`fix`），退出码不变；`--json` 时输出原 JSON 错误。
4. AGENTS.md 增加 CLI 输出规范：所有 loopspec 命令提供文本（默认）与 JSON（`--json`）两种格式，文本面向 MODEL 阅读；新增或修改命令必须同时维护两者与对应测试。
5. 同步更新：
   - skill 源文件 `builtin/skills/*.md`（「Workflow commands print JSON」等表述）及生成副本（由 CLI 同步）。
   - 中英文文档：`cli-reference`、`agent-protocol` 等，以及 release notes。
   - 测试 helper 与所有解析 CLI 输出的测试（加 `--json`）；LLM E2E 守卫与断言。

## 非目标

- `hook pre-tool-use`：Claude/Codex hook 协议要求 JSON，保持现状，不加文本模式。
- 不改变任何 JSON 字段、结构、错误码与退出码。
- 不改 `change status`、`graph`、`init`、`update`、`version` 已有的文本输出（它们已满足「默认文本 + `--json`」）。
- 不处理 fragment 辅助文件路径问题（另一个待确认的需求）。
- 不新增配置项或环境变量来切换默认格式。

## 验收条件

- [ ] 范围第 1 条列出的每个命令，不带 `--json` 时 stdout 为文本：不是合法 JSON，包含至少一个 `=== ... ===` 分节，没有 ANSI 转义，没有以 `#` 开头的行。用 BDD/单测逐个命令判定。
- [ ] 同一命令加 `--json` 时，stdout 与改动前 JSON 输出逐字节相同（测试用改动前的输出样例或 `emit` 结果比对 `json.loads` 结果相等）。
- [ ] 每个命令的渲染器对 payload 顶层键做「已渲染或已声明省略」的覆盖检查；向 payload 加一个未处理的键时测试失败。
- [ ] 文本中出现后续步骤要用的值：`plan create/show` 的 `digest`、`change archive` 的 `archiveId`、`gate begin` 的 `roundId` 与 `recordCommand`、`registry update` 的 `planId`、`node instructions` 的 `resolvedOutputPath`；测试断言这些值以 `key: value` 形式出现。
- [ ] `node instructions` 文本中 `instruction` 与 `template` 原文逐行可读（不含 `\n` 转义），每行以固定缩进引用。
- [ ] 不可信文本中含 `=== X ===`、控制字符或换行注入时，渲染结果中不会出现以它开头的列级分节行（测试判定）。
- [ ] 文本模式下任一命令出错时输出 `=== ERROR ===` 及 `error:`、`message:` 字段，退出码为 1；`--json` 时输出原 JSON 错误。
- [ ] `hook pre-tool-use` 输出与改动前相同。
- [ ] AGENTS.md 包含文本/JSON 双格式规范条目。
- [ ] skill 源文件不再声称工作流命令输出 JSON；`make test-llm` 全部通过（真实模型在文本输出下完成 new/continue/archive/update-registry 场景）。
- [ ] `ruff`、`mypy`、`pytest -n 2 -m "not timing and not llm"` 全部通过。

## 风险

- **兼容性（破坏性变更）**：外部脚本或 fragment 脚本若解析 `loopspec ...` 的 JSON 输出，需要加 `--json`。应对：release notes 明确标注；`--json` 输出不变，迁移只需加参数。发版时按破坏性变更考虑版本号（发版不在本次范围，由人决定）。
- **MODEL 行为回归**：skill 依赖输出字段，文本格式不清晰会导致模型取错值。应对：保留 JSON 字段名作为标签，并用 LLM E2E 验证。
- **输出注入**：state、memory、fragment 文本、报告内容是不可信数据，可能伪造分节或「下一步命令」。应对：沿用 `sanitize` 与缩进引用，安全审查关卡重点检查。
- **工作量与一致性**：手写 27 个渲染器容易风格不一或漏字段。应对：共用格式化原语（分节、字段、引用），以键集合覆盖测试兜底。
- **测试改动面大**：大量测试解析 stdout JSON。应对：集中在 helper 加 `--json`，逐个修正直接调用 runner 的测试。
