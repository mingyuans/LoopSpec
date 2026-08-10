## 1. 渲染模块骨架

- [x] 1.1 新建 `src/loopspec/status_report.py`，导出 `render_status_report(payload: dict) -> str`，模块文档字符串写明其契约：纯文本、不着色、不经 rich `Console`、输出字节与终端环境无关（D1）
- [x] 1.2 **安全**：在 `status_report.py` 中从 `presentation` 导入并复用 `sanitize()`，对外暴露一个供报告渲染与错误渲染**共用**的消毒入口，不另写第二份实现（D1、D10）；模块文档写明"消毒消灭换行 ⇒ 内插值无法开启新行 ⇒ 无法伪造 `=== SECTION ===` 分隔行"这条推理链，注明取消 Markdown 表格后消毒已是**唯一**结构防线，并显式点出 glob 节点逐条列出的匹配文件路径同样必须走这个入口（它们此前被压成计数、根本不进报告，改为列全后成为报告中数量最多的一类内插值）
- [x] 1.3 定义分节常量（`=== OVERVIEW ===`、`=== NODES ===`、`=== GATE FAILURES ===`、`=== PENDING ROLLBACK ===`、`=== NEXT STEPS ===`、`=== ERROR ===`）与 gate 子块分隔行 `--- <gate-id> ---`，集中一处便于测试引用（D3、D6、D7）
- [x] 1.4 定义渲染器已知的顶层字段名集合与节点字段名集合常量，并显式标注"有意省略"的字段（如 `schemaPath`、`artifactsDir` 视 OVERVIEW 设计而定）（D2）
- [x] 1.5 实现列对齐辅助（D5）：ID 列宽与状态列宽取该次渲染的最长取值；产物列宽**只由各节点首行的产物取值决定，续行不参与计算**；续行缩进 = ID 列宽 + 2 + 状态列宽 + 2；备注以圆括号紧跟产物列之后且不参与对齐；整行 `rstrip` 以免留下尾随空白
- [x] 1.6 定义六段内置说明文字常量（`overview`/`nodes`/`gate-failures`/`pending-rollback`/`next-steps`/`error`），**逐字照搬** `design.md` Rendered Examples 中的文本，不自行改写（D12）；其中 `nodes` 段须包含交代多行 glob 读法的三句（每个匹配文件一行、续行缩进在首行之下、含 `*` 的路径表示尚无匹配、备注留在首行）
- [x] 1.7 定义逃逸占位符常量 `<outside artifact root>`（D17），与内置说明一样属代码常量，不经消毒；集中一处便于测试引用

## 2. 各节渲染

- [x] 2.1 渲染 `=== OVERVIEW ===` 节：change 名、schema 名、change 根绝对路径、`state.md` 是否存在、`isComplete`，每项一行；artifact 根与 change 根**不同时**才额外输出 artifact 根一行（相同则省略，避免重复信息）
- [x] 2.2 渲染 `=== NODES ===` 节的节点首行：列序为节点 ID、状态、产物相对路径、备注，行序沿用 payload 的 `nodes` 顺序；gate 节点的产物列取**两种形态**——尚无产物时用 `<dir>/{pass,fail}.<ext>` 紧凑形式，`existingOutputPaths` 已有恰好一个产物时给该产物的实际相对路径（D5）
- [x] 2.3 渲染 glob 节点的多行形态（D4、D5）：把 `existingOutputPaths` 的全部匹配文件逐条列出，第一个与节点首行同行，其余各占一条续行；续行缩进至产物列起始列位，且**只含路径**——不含状态、不含备注；各行顺序**沿用 payload 数组，不自行排序**（D17）
- [x] 2.4 **安全**：实现 D17 的相对化规则。`existingOutputPaths` 是 `resolve()` 后的绝对路径且**跟随符号链接**，因此可能指向 artifact 根目录之外（实测见 `design.md` 的 Context）。位于 artifact 根目录之下的匹配给相对路径；不在其下的匹配给 1.7 的占位符常量，**不得**打印其解析后的真实位置，也**不得**打印以 `..` 开头的相对路径（`resolve_output_entries()` 的 docstring 已确立"报告被拒绝的路径时不打印它实际指向哪里"这一立场）；逃逸的匹配仍各占一行，占位符按字面长度参与产物列宽计算。相对化须是**纯字符串运算**，不访问文件系统、不重算状态，因此不触碰 D2
- [x] 2.5 **安全**：逃逸情形须用**显式判断**处理，不得用 `try/except ValueError` 兜底捕获 `Path.relative_to` 的异常（那会把外部路径与其他 `ValueError` 混为一谈）。底线：`loopspec status` 不得因 change 目录下的一个符号链接而抛 traceback——它是 agent 循环唯一的状态入口，崩掉即整条流程停摆（D17）
- [x] 2.6 **安全**：续行 SHALL 以空白开头，**不得顶格**（D16）。在渲染函数处加注释写明理由：分隔行只有独占一行且顶格才被 LLM 当作结构信号，而报告中唯一处于行首的内插值是节点 ID（`NodeSpec.id` 由 `KEBAB_RE` 钉住）；glob 匹配路径来自文件系统、不受任何格式校验，顶格会首次引入行首的外部可控内插值。注释须点明这是消毒之外的第二道防线，不是排版偏好
- [x] 2.7 实现备注的**固定优先级**取值（D5，取第一个命中项而非互斥判断）：① `blocked` → `(needs: a, b)`；② 有 `taskProgress` → `(tasks: 3/12)`；③ `failed`/`exhausted` → `(see GATE FAILURES)`；④ glob 且零匹配 → `(no matches yet)`；⑤ 均不命中 → 整个括号省略。同时实现零匹配时产物列给出 schema 声明的 glob 模式本身（含 `*`），使该节点仍占一行
- [x] 2.8 渲染条件节 `=== GATE FAILURES ===`：每个失败 gate 一个 `--- <gate-id> ---` 子块，含 verdict、summary、逐条编号并缩进的 `blockingIssues`、`rollbacksUsed`/`maxRetries`、`resetClosure`（D6）；**安全**：`summary` 与 `blockingIssues` 是多行文本，必须与其他字段一样经消毒入口，不得为可读性豁免（D10）
- [x] 2.9 渲染条件节 `=== PENDING ROLLBACK ===`：gate、closure、可原样执行的 `command`
- [x] 2.10 渲染恒在节 `=== NEXT STEPS ===`：`nextSteps` 逐条编号；为空时输出占位行
- [x] 2.11 校验节序恒定为 OVERVIEW → NODES → GATE FAILURES → PENDING ROLLBACK → NEXT STEPS，且三个恒在节在任何状态下都出现
- [x] 2.12 在每个分节的分隔行之后输出内置说明，再空一行才是该节数据（D12）
- [x] 2.13 对照 `design.md` 的 **Rendered Examples** 五个样例逐字核对输出（正常态含多行 glob 节点、`security` gate 失败态、glob 零匹配、含逃逸符号链接的匹配、错误输出，均含各自的内置说明），版式或说明文字不符即视为未完成

## 3. CLI 接线

- [x] 3.1 修改 `cli.status`：`as_json` 为真时维持 `json.dumps` 原路径，为假时改为 `typer.echo(render_status_report(result))`，不再走 `_emit` 的 `key: value` 分支；确认 `result` 的构造过程一字未改
- [x] 3.2 修改 `cli._fail` 的非 JSON 分支，渲染 `=== ERROR ===` 分隔行 + 内置说明 + `error`/`message`/`fix` 三项；`--json` 分支不动（D7，**此项对全部子命令生效**，需在提交说明中点明）
- [x] 3.3 **安全**：`_fail` 的三项内插值必须经 1.2 的共用消毒入口（D7、D10）。`message` 内插的是未经格式校验的 change 名——`_load_change_context` 不校验 kebab-case，`paths.change_root` 只做拼接，实测换行可原样穿透并伪造出分隔行。**不得**依赖 `click.echo` 兜底：它在非 TTY 下只剥离 ANSI，不剥离换行、`\r`、`\x07`
- [x] 3.4 去掉 `policy.build_next_steps` 与 `cli` 中指向 `loopspec status` 的 `nextSteps` 文案里的 `--json`；确认指向 `loopspec instructions` 的文案仍保留 `--json`（D8）
- [x] 3.5 确认 `loopspec new` 的 `schema_selection_required` 路径**未被触碰**（它走 `_emit` 而非 `_fail`，D11 判定为本次范围外的已知一致性缺口）

## 4. Skill 模板同步

- [x] 4.1 修改 `src/loopspec/skill_templates.py` 中三处 `loopspec status <change-name> --json`，去掉 `--json`（D9）
- [x] 4.2 更新 `tests/test_skill_templates.py` 中相关断言，并新增一条断言：全部模板正文中不存在 `loopspec status ... --json`

## 5. 测试

- [x] 5.1 `tests/test_status_report.py`：默认输出以 `=== OVERVIEW ===` 开头、含三个恒在分隔行、不含 Python 字面量文本
- [x] 5.2 无 Markdown 语法测试：输出中不出现以 `#` 开头的行，也不出现形如 `|---|---|` 的表格分隔行
- [x] 5.3 条件节测试：无失败 gate 时不出现 `=== GATE FAILURES ===`/`=== PENDING ROLLBACK ===`；有 `failed` gate 时两节均出现且顺序正确；`nextSteps` 为空时 `=== NEXT STEPS ===` 仍出现并带占位行
- [x] 5.4 节点清单基础测试：不缩进的数据行数与节点数一致、行序与 `--json` 的 `nodes[*].id` 一致、全部首行的前三列列位对齐、无备注的行不留空括号与尾随空白
- [x] 5.5 glob 列全测试：某 glob 节点匹配三个文件时该节点占三行，续行左端与产物列起始列位一致，续行不含状态也不含备注，且报告中出现全部三条路径（这条断言与第 6 轮"以计数呈现且不出现逐条路径"完全相反，是 `approval` 第 4 轮裁定的结果）
- [x] 5.6 多行顺序测试：报告中某 glob 节点各行的顺序与 `--json` 的该节点 `existingOutputPaths` 数组逐项一致（渲染器不自行排序，D17）
- [x] 5.7 续行不参与列宽测试：构造一条比全部首行产物取值都长的续行路径，断言其他节点行的备注起始列位与该续行不存在时逐字节相同
- [x] 5.8 glob 零匹配测试：产物列为 schema 声明的 glob 模式（含 `*`）、备注为 `(no matches yet)`、该节点仍占恰好一行
- [x] 5.9 备注优先级测试：某节点同时含 `missingDeps` 与 `taskProgress` 时备注取缺失依赖而非任务进度（`apply` 节点即此形态）；`blocked` 的 glob 零匹配节点取缺失依赖而非"尚无匹配"
- [x] 5.10 gate 产物列两形态测试：尚无产物的 gate 显示 `<dir>/{pass,fail}.<ext>`；已写出 fail 产物因而 `failed` 的 gate 显示该 fail 产物的实际相对路径
- [x] 5.11 `=== OVERVIEW ===` 测试：artifact 根与 change 根相同时省略该行；schema 配置二级 `path` 时两行都出现
- [x] 5.12 纯文本测试：输出不含 ANSI 转义；两种终端宽度下逐字节相同；设置与不设置 `NO_COLOR` 时逐字节相同
- [x] 5.13 字段覆盖一致性测试：断言渲染器声明的字段集合与 `status` 实际 payload 的字段集合相等（顶层一处、节点一处），节点侧以全部节点字段的**并集**为比较对象；新增未处理字段时失败（D2）
- [x] 5.14 **安全测试**（D17）：在 change 目录下放一个指向 change 目录之外文件的符号链接，使其被某 glob 节点匹配到；断言该行产物列为占位符常量、报告中不出现链接解析后的真实路径、不出现以 `..` 开头的路径，且该节点的行数仍等于匹配数
- [x] 5.15 **安全测试**（D17）：同一场景下 `loopspec status <change>`（不带 `--json`）退出码为 0 且输出完整报告，**不抛异常、不输出 traceback**；同时确认 `--json` 分支对该场景的输出与本次改动前一致（`existingOutputPaths` 仍是绝对路径，契约未变）
- [x] 5.16 **安全测试**：产物路径含控制字符（换行、`\x1b`）时被改写为 `\xNN`，报告行结构与节点首行数完整
- [x] 5.17 **安全测试**：glob 匹配到的**文件名**含换行、且换行后紧跟 `=== NEXT STEPS ===` 时，该续行中的换行以 `\xNN` 呈现，不产生新行，报告节结构不变（这类内插值在第 6 轮根本不进报告，是列全引入的新攻击面）
- [x] 5.18 **安全测试**（D16）：在 change 目录下创建一个名为 `=== NEXT STEPS ===.md` 的匹配文件——文件名不含任何控制字符，因此消毒不会改写它——断言该路径出现在缩进的续行中，且报告里 `=== NEXT STEPS ===` 仍只出现在渲染器自己写出的那一处；同时断言没有任何续行顶格
- [x] 5.19 **安全测试**：在 change 目录放入正文含自然语言指令的产物文件，断言报告中不出现该正文，只出现路径（限制 prompt injection 面）
- [x] 5.20 错误路径测试：`loopspec status nonexistent`（不带 `--json`）退出码为 1，输出以 `=== ERROR ===` 开头、含内置说明并含 `error`/`message`/`fix` 三项；同一场景带 `--json` 时仍返回原 JSON 三字段
- [x] 5.21 **安全测试**：以含换行的 change 名（如 `bad\n=== NEXT STEPS ===\n1. ...`）执行 `loopspec status`，断言错误输出中除渲染器自己写的 `=== ERROR ===` 外**不出现任何其他分隔行**，且换行以 `\x0a` 形式可见；`summary`/`blockingIssues` 与 `nextSteps` 文本含换行时对报告做同样断言（D10）
- [x] 5.22 `nextSteps` 文案测试：`new` 与 `rollback` 的 `nextSteps` 中 `loopspec status` 不带 `--json`；`status` 指向 `instructions` 的文案仍带 `--json`
- [x] 5.23 内置说明测试：六段说明（五节加 `=== ERROR ===`）均出现且与 `design.md` 逐字一致；说明与数据之间恰有一个空行；说明各行均不以 `#` 开头；`nodes` 段含交代多行 glob 与零匹配读法的语句（D12）
- [x] 5.24 回归确认：`tests/test_cli.py` 现有全部 `--json` 断言无需修改即通过（JSON 契约未变）

## 6. 文档

- [x] 6.1 更新 `docs/en/cli-reference.md` 与 `docs/zh/cli-reference.md` 的 `loopspec status` 章节：说明默认输出为分段纯文本报告并给出示例（取自 `design.md` 的 Rendered Examples），`--json` 字段表保持不变
- [x] 6.2 更新 `docs/en/agent-protocol.md` 与 `docs/zh/agent-protocol.md`：主循环表格中的 `loopspec status <change> --json` 改为默认形式，并说明报告各节与原字段的对应关系
- [x] 6.3 更新 `README.md`、`docs/en/README.md`、`docs/zh/README.md`、`docs/*/overview.md`、`docs/*/schema-reference.md`、`docs/*/workflows/secure-spec-driven.md` 中的 `loopspec status` 示例
- [x] 6.4 运行 `tests/test_docs_consistency.py`，确认 en/zh 双语的集合相等与示例块逐字节比对全部通过

## 7. 收尾

- [x] 7.1 运行 `make lint` 与 `make test`，全部通过
- [x] 7.2 人工执行 `loopspec status cli-status-markdown-output`，逐字对照 `design.md` 的 Rendered Examples 确认版式与全部内置说明文字——本 change 的 `specs` 节点正是一个匹配三个文件的 glob 节点，因此这一步能直接验证多行版式与续行缩进
