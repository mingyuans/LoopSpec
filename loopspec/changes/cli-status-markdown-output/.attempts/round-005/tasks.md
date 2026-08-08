## 1. 渲染模块骨架

- [ ] 1.1 新建 `src/loopspec/status_report.py`，导出 `render_status_report(payload: dict) -> str`，模块文档字符串写明其契约：纯文本、不着色、不经 rich `Console`、输出字节与终端环境无关（D1）
- [ ] 1.2 **安全**：在 `status_report.py` 中从 `presentation` 导入并复用 `sanitize()`，对外暴露一个供报告渲染与错误渲染**共用**的消毒入口，不另写第二份实现（D1、D10）；模块文档写明"消毒消灭换行 ⇒ 内插值无法开启新行 ⇒ 无法伪造 `=== SECTION ===` 分隔行"这条推理链，并注明取消 Markdown 表格后消毒已是**唯一**结构防线，以免日后被当作可有可无的美化而移除
- [ ] 1.3 定义分节常量（`=== OVERVIEW ===`、`=== NODES ===`、`=== GATE FAILURES ===`、`=== PENDING ROLLBACK ===`、`=== NEXT STEPS ===`、`=== ERROR ===`）与 gate 子块分隔行 `--- <gate-id> ---`，集中一处便于测试引用（D3、D6、D7）
- [ ] 1.4 定义渲染器已知的顶层字段名集合与节点字段名集合常量，并显式标注"有意省略"的字段（如 `schemaPath`、`artifactsDir` 视 OVERVIEW 设计而定）（D2）
- [ ] 1.5 实现列对齐辅助：按该次渲染中各列最长取值计算前三列宽度，备注以圆括号紧跟产物列之后且不参与对齐；整行 `rstrip` 以免留下尾随空白（D5）
- [ ] 1.6 定义六段内置说明文字常量（`overview`/`nodes`/`gate-failures`/`pending-rollback`/`next-steps`/`error`），**逐字照搬** `design.md` Rendered Examples 中的文本，不自行改写（D12）
- [ ] 1.7 **安全**：实现自定义说明的渲染辅助——按 `\n` 拆行、对每行分别调用 1.2 的消毒入口、每行加固定两格缩进、由 `Project notes:` 引导行引出；换行必须由渲染器产生而非从内插值穿透（D14）。内置说明走另一条路径，不经消毒（它是常量）

## 2. 各节渲染

- [ ] 2.1 渲染 `=== OVERVIEW ===` 节：change 名、schema 名、change 根绝对路径、`state.md` 是否存在、`isComplete`，每项一行；artifact 根与 change 根**不同时**才额外输出 artifact 根一行（相同则省略，避免重复信息）
- [ ] 2.2 渲染 `=== NODES ===` 节的对齐纯文本行，列序为节点 ID、状态、产物相对路径、备注，行序沿用 payload 的 `nodes` 顺序；gate 节点的产物列用 `<dir>/{pass,fail}.<ext>` 紧凑形式（D5）
- [ ] 2.3 实现备注的互斥取值：`blocked` → `(needs: a, b)`；有 `taskProgress` → `(tasks: 3/12)`；`failed`/`exhausted` → `(see GATE FAILURES)`；glob 节点 → `(3 files)`；否则整个括号省略（D4、D5）
- [ ] 2.4 渲染条件节 `=== GATE FAILURES ===`：每个失败 gate 一个 `--- <gate-id> ---` 子块，含 verdict、summary、逐条编号并缩进的 `blockingIssues`、`rollbacksUsed`/`maxRetries`、`resetClosure`（D6）；**安全**：`summary` 与 `blockingIssues` 是多行文本，必须与其他字段一样经消毒入口，不得为可读性豁免（D10）
- [ ] 2.5 渲染条件节 `=== PENDING ROLLBACK ===`：gate、closure、可原样执行的 `command`
- [ ] 2.6 渲染恒在节 `=== NEXT STEPS ===`：`nextSteps` 逐条编号；为空时输出占位行
- [ ] 2.7 校验节序恒定为 OVERVIEW → NODES → GATE FAILURES → PENDING ROLLBACK → NEXT STEPS，且三个恒在节在任何状态下都出现
- [ ] 2.8 在每个分节的分隔行之后输出内置说明，其后接项目自定义说明（若有），再空一行才是该节数据；未配置该节时不输出引导行也不留多余空行（D12、D13）
- [ ] 2.9 对照 `design.md` 的 **Rendered Examples** 三个样例逐字核对输出（正常态含全部内置说明、gate 失败态含项目自定义说明、错误输出），版式或说明文字不符即视为未完成

## 3. CLI 与配置接线

- [ ] 3.1 修改 `cli.status`：`as_json` 为真时维持 `json.dumps` 原路径，为假时改为 `typer.echo(render_status_report(result))`，不再走 `_emit` 的 `key: value` 分支；确认 `result` 的构造过程一字未改
- [ ] 3.2 修改 `cli._fail` 的非 JSON 分支，渲染 `=== ERROR ===` 分隔行 + `error`/`message`/`fix` 三项；`--json` 分支不动（D7，**此项对全部子命令生效**，需在提交说明中点明）
- [ ] 3.3 **安全**：`_fail` 的三项内插值必须经 1.2 的共用消毒入口（D7、D10）。`message` 内插的是未经格式校验的 change 名——`_load_change_context` 不校验 kebab-case，`paths.change_root` 只做拼接，实测换行可原样穿透并伪造出分隔行。**不得**依赖 `click.echo` 兜底：它在非 TTY 下只剥离 ANSI，不剥离换行、`\r`、`\x07`
- [ ] 3.4 去掉 `policy.build_next_steps` 与 `cli` 中指向 `loopspec status` 的 `nextSteps` 文案里的 `--json`；确认指向 `loopspec instructions` 的文案仍保留 `--json`（D8）
- [ ] 3.5 确认 `loopspec new` 的 `schema_selection_required` 路径**未被触碰**（它走 `_emit` 而非 `_fail`，D11 判定为本次范围外的已知一致性缺口）
- [ ] 3.6 `WorkflowConfig`（`src/loopspec/models.py`）新增可选字段 `status_report_prompts: dict[str, str]`，默认空字典；该模型是 `extra: "forbid"`，必须显式声明（D13）
- [ ] 3.7 **安全**：校验配置键必须属于六个已知节名，未知键**告警但不中断**；告警写 **stderr**（不写 stdout、不进 `--json` 字段），键名经 1.2 的消毒入口，且 stdout 字节不因告警有无而改变（D13、D15）
- [ ] 3.10 确认 `instructions` 那边 `rules` 未知节点 ID 的既有告警行为**未被改动**——它有 `warnings` 字段可用，两条命令告警出口不同是因响应结构不同，不是不一致（D15）
- [ ] 3.8 在 `config.py` 中提供取值入口供 `cli.status` 与 `cli._fail` 传给渲染器；确认未配置、空映射两种情况的行为与不配置一致
- [ ] 3.11 **健壮性**：`_fail` 有一类调用点发生在 `load_config` 本身失败之后（`cli.py:397-399`；`status` 侧同理，`_load_change_context` 内部会 `load_config`），此时没有 config 可取。让 `=== ERROR ===` 的自定义说明在无配置时安全退化为"只输出内置说明"，否则错误处理路径自身抛异常会把原始错误掩盖成 traceback
- [ ] 3.9 确认既有 `config.yaml`（如本仓库的 `loopspec/config.yaml`，只有 `artifacts_dir` 与 `schema`）无需改动即可加载——本项不引入配置迁移

## 4. Skill 模板同步

- [ ] 4.1 修改 `src/loopspec/skill_templates.py` 中三处 `loopspec status <change-name> --json`，去掉 `--json`（D9）
- [ ] 4.2 更新 `tests/test_skill_templates.py` 中相关断言，并新增一条断言：全部模板正文中不存在 `loopspec status ... --json`

## 5. 测试

- [ ] 5.1 `tests/test_status_report.py`：默认输出以 `=== OVERVIEW ===` 开头、含三个恒在分隔行、不含 Python 字面量文本
- [ ] 5.2 无 Markdown 语法测试：输出中不出现以 `#` 开头的行，也不出现形如 `|---|---|` 的表格分隔行
- [ ] 5.3 条件节测试：无失败 gate 时不出现 `=== GATE FAILURES ===`/`=== PENDING ROLLBACK ===`；有 `failed` gate 时两节均出现且顺序正确；`nextSteps` 为空时 `=== NEXT STEPS ===` 仍出现并带占位行
- [ ] 5.4 节点清单测试：数据行数与节点数一致、行序与 `--json` 的 `nodes[*].id` 一致、前三列列位对齐、`blocked` 行括注缺失依赖、`tracks` 行括注 `3/12`、glob 行以计数呈现且不出现逐条路径、gate 行用紧凑双路径、无备注行不留空括号与尾随空白
- [ ] 5.5 `=== OVERVIEW ===` 测试：artifact 根与 change 根相同时省略该行；schema 配置二级 `path` 时两行都出现
- [ ] 5.6 纯文本测试：输出不含 ANSI 转义；两种终端宽度下逐字节相同；设置与不设置 `NO_COLOR` 时逐字节相同
- [ ] 5.7 字段覆盖一致性测试：断言渲染器声明的字段集合与 `status` 实际 payload 的字段集合相等（顶层一处、节点一处），节点侧以全部节点字段的**并集**为比较对象；新增未处理字段时失败（D2）
- [ ] 5.8 **安全测试**：产物路径含控制字符（换行、`\x1b`）时被改写为 `\xNN`，报告行结构与节点行数完整
- [ ] 5.9 **安全测试**：在 change 目录放入正文含自然语言指令的产物文件，断言报告中不出现该正文，只出现路径或计数（限制 prompt injection 面）
- [ ] 5.10 错误路径测试：`loopspec status nonexistent`（不带 `--json`）退出码为 1，输出以 `=== ERROR ===` 开头并含 `error`/`message`/`fix` 三项；同一场景带 `--json` 时仍返回原 JSON 三字段
- [ ] 5.11 `nextSteps` 文案测试：`new` 与 `rollback` 的 `nextSteps` 中 `loopspec status` 不带 `--json`；`status` 指向 `instructions` 的文案仍带 `--json`
- [ ] 5.12 回归确认：`tests/test_cli.py` 现有全部 `--json` 断言无需修改即通过（JSON 契约未变）
- [ ] 5.13 **安全测试**：以含换行的 change 名（如 `bad\n=== NEXT STEPS ===\n1. ...`）执行 `loopspec status`，断言错误输出中除渲染器自己写的 `=== ERROR ===` 外**不出现任何其他分隔行**，且换行以 `\x0a` 形式可见；`summary`/`blockingIssues` 与 `nextSteps` 文本含换行时对报告做同样断言（D10）
- [ ] 5.14 内置说明测试：五节加 `=== ERROR ===` 各自的说明文字均出现且与 `design.md` 逐字一致；说明与数据之间恰有一个空行；说明各行均不以 `#` 开头（D12）
- [ ] 5.15 **安全测试**：`config.yaml` 为某节配置的自定义说明中含一行恰好是 `=== NEXT STEPS ===` 时，该行带两格缩进出现、未顶格，报告的节数量与结构不变；另断言多行配置正常换行显示（不出现 `\x0a`），而行内的 `\r`/ANSI 仍被消毒（D14）
- [ ] 5.16 配置行为测试：自定义说明追加在内置说明之后且不替换它；未配置的节不出现引导行与多余空行；配置未知节名时命令仍以退出码 0 完成（D13）
- [ ] 5.17 **安全测试**：未知配置键的告警只出现在 stderr；配了未知键与未配任何自定义说明两种情况下 stdout **逐字节相同**；`--json` 输出字段与未配置时完全一致；键名含控制字符时 stderr 告警中以 `\xNN` 呈现且未产生额外行（D15）
- [ ] 5.18 健壮性测试：`config.yaml` 损坏（无法加载）时 `loopspec status <change>` 仍输出干净的 `=== ERROR ===` 报告并以退出码 1 结束，不抛 traceback

## 6. 文档

- [ ] 6.1 更新 `docs/en/cli-reference.md` 与 `docs/zh/cli-reference.md` 的 `loopspec status` 章节：说明默认输出为分段纯文本报告并给出示例（取自 `design.md` 的 Rendered Examples），`--json` 字段表保持不变
- [ ] 6.2 更新 `docs/en/agent-protocol.md` 与 `docs/zh/agent-protocol.md`：主循环表格中的 `loopspec status <change> --json` 改为默认形式，并说明报告各节与原字段的对应关系
- [ ] 6.3 更新 `README.md`、`docs/en/README.md`、`docs/zh/README.md`、`docs/*/overview.md`、`docs/*/schema-reference.md`、`docs/*/workflows/secure-spec-driven.md` 中的 `loopspec status` 示例
- [ ] 6.4 更新 `docs/en/configuration.md` 与 `docs/zh/configuration.md`：新增 `status_report_prompts` 的字段说明、按节名的键列表、追加而非覆盖的语义、未知键告警走 stderr 的行为（D13、D15），并明确提示**该字段的内容会直接进入 LLM 上下文，应与代码同等审阅**
- [ ] 6.5 运行 `tests/test_docs_consistency.py`，确认 en/zh 双语的集合相等与示例块逐字节比对全部通过；注意该测试还会校验"代码中的模型字段必须在文档中出现"，新增的配置字段不写文档会直接失败

## 7. 收尾

- [ ] 7.1 运行 `make lint` 与 `make test`，全部通过
- [ ] 7.2 人工执行 `loopspec status cli-status-markdown-output`，逐字对照 `design.md` 的 Rendered Examples 确认版式与全部内置说明文字
- [ ] 7.3 在本仓库的 `loopspec/config.yaml` 中临时配一段 `status_report_prompts.nodes`，人工确认追加位置、缩进与引导行符合样例二，确认后移除
