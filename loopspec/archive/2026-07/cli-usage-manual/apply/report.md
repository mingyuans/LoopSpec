# Implementation Report

## Summary

按 round 2 获批的计划，新增了中英双语的 `docs/` 使用与配置手册（语言并列子目录、跨语言同名），并用一份
40 条断言的一致性测试同时守住"文档 vs 代码"与"中文版 vs 英文版"两个维度。`README.md` 收敛为入口，
`Makefile` 新增 `docs-check`。`src/loopspec/**` 一行未改，无新增依赖。

`tasks.md` 的 40 个任务全部完成并勾选。

## Files touched

新增，15 份文档：

| 路径 | 内容 |
| --- | --- |
| `docs/README.md` | 双语语言入口，6 行，只有两条语言链接与一句导航 |
| `docs/en/README.md`、`docs/zh/README.md` | 语言内索引：逐篇覆盖范围与适用读者 |
| `docs/en/overview.md`、`docs/zh/overview.md` | 定位、核心模型、磁盘布局、12 条术语表 |
| `docs/en/cli-reference.md`、`docs/zh/cli-reference.md` | 12 条命令各一节 + 失败契约 + 15 个错误码总表 |
| `docs/en/configuration.md`、`docs/zh/configuration.md` | `config.yaml` 11 个字段、9 条校验规则、两条解析路径、4 个示例 |
| `docs/en/schema-reference.md`、`docs/zh/schema-reference.md` | `schema.yaml` 19 个字段、20 条加载期校验及错误码、最小可用 schema |
| `docs/en/agent-protocol.md`、`docs/zh/agent-protocol.md` | 主循环 13 步 + 回退支线 6 步 + 三类"不是文档的节点" + `state.md` 约定 |
| `docs/en/workflows/secure-spec-driven.md`、`docs/zh/workflows/secure-spec-driven.md` | 7 节点图、逐节点产出要求、三个门禁的取值理由 |

新增，1 份测试：

| 路径 | 内容 |
| --- | --- |
| `tests/test_docs_consistency.py` | 40 条断言（见下） |

修改：

| 路径 | 改动 |
| --- | --- |
| `README.md` | 新增 Documentation 一节链接 `docs/README.md` 与两个语言版本；删除与手册重复的 `init` 输出示例、交互式选择器细节、内置 schema 节点图；`make docs-check` 加入 Development |
| `Makefile` | 新增 `docs-check` target 并加入 `.PHONY` |

## What the consistency test asserts

40 条断言，分三类：

**结构（按语言各跑一遍）**：7 个必需文件存在；`docs/` 顶层只有 `README.md`；语言内索引链接到同语言其余 6
篇；全部仓库内相对链接目标存在（外部 scheme 显式跳过，不做网络探测）；每篇首屏含覆盖范围/适用读者/对侧
语言链接；代码块均带语言标注；无图片、无 emoji、标题不超三级；字段表使用本语言约定的五列表头且不串用另一
语言的；除首屏外无跨语言链接。

**代码 → 文档单向覆盖（按语言各跑一遍）**：12 条命令各有 `## loopspec <command>` 小节；每个选项出现在其
命令自己的小节内；`WorkflowConfig`/`ConfigSchemaRef`/`SchemaSelectionSpec` 与
`WorkflowSchema`/`NodeSpec`/`GateSpec`/`GateOutputs`/`GateTemplates`/`OnFailSpec` 的每个字段（别名优先）
出现在对应文档的字段表首列；15 个错误码全部在总表中；`cli.DEFAULT_HOME`、`cli.DEFAULT_SCHEMA_NAME`、
`artifacts_dir`、`max_retries`、`on_exhausted` 的默认值与代码一致；带标记的示例真实通过
`WorkflowConfig.model_validate` / `WorkflowSchema.model_validate` / `load_schema`；示例不含凭据形态字符串。

**跨语言双向等价**：两个语言目录路径集合相等；命令小节标题集合相等；每对同名文件字段表首列标识符集合相等；
错误码集合相等；带标记示例按序逐字相等。

字段与选项的判定一律基于结构化位置（表格首列、命令小节范围内），不用全文裸子串包含——这是 spec
「名称出现在叙述文本中不算已记录」那条场景的实现方式。

## Test output

```text
$ make lint
uv run ruff check src tests
All checks passed!
uv run mypy src
Success: no issues found in 22 source files

$ make test
============================= 545 passed in 6.96s ==============================

$ make docs-check
============================== 40 passed in 0.80s ==============================
```

变更前 `make test` 为 505 passed；新增 40 条断言后为 545 passed，既有测试无一被改动或跳过。

### 变异检查（确认断言非空转）

为避免"断言在空集合上恒真"的假通过，对 `docs/zh/cli-reference.md` 做了两处临时破坏后重跑，随即还原：

- 删掉 `archive_conflict` 一行错误码；
- 把 `--older-than` 写成 `--older-then`。

结果 4 条断言失败（`test_every_option_is_documented_in_its_own_section[zh]`、
`test_every_error_code_is_documented[zh]`、`test_field_names_match_across_languages`、
`test_error_codes_match_across_languages`），还原后重回 40 passed。另核对了断言操作的数据规模：12 条命令、
15 个错误码、11 个 config 字段、19 个 schema 字段、每语言 5 个 config 示例与 1 个 schema-dir 示例。

## Security recommendations carried out

round 2 `security/pass.md` 的 4 条非阻塞建议：

1. **示例物化前校验相对路径安全性** —— 已落地。`test_marked_schema_dir_examples_load` 在写入任何文件之前，
   对示例声明的每个 `template` / `instruction.file` 调用 `paths.is_safe_relative_path`，非法即断言失败。
2. **凭据断言失败不回显命中内容** —— 已落地。`test_examples_carry_no_credentials` 的失败信息只含
   `文件:行号` 与命中的规则名（`home-path` / `bearer-token` / `api-key-assignment` / `private-host`）。
3. **`--json` 样例的绝对路径含本机 home 路径** —— 已落地。采集时每条命令显式传 `--home /tmp/...`，写入文档
   前把全部绝对路径替换为 `/path/to/project/...`；并按建议在凭据检查中加入 `home-path` 规则
   （`/Users/...`、`/home/...`），使这类泄漏此后会被测试直接拦住。
4. **链接断言不做网络探测** —— 已落地。`test_relative_links_resolve` 显式跳过 `http://`、`https://`、
   `mailto:`。

另按建议，跨语言逐字比对失败时报告的是"文件对 + 示例序号 + 首个差异行号"，而不是把两版示例整块打进日志。

## Deviations from the design

三处，都是设计未预见到的细节，均不改变已获批的决策：

1. **`### gate.outputs` 等三节从四级标题降为三级。** 设计 D4 要求标题最深三级，但 `gate` 的三个嵌套字段
   最初被写成 `####`。已改为与 `### gate` 平级的 `### \`gate.outputs\`` 等，锚点不变（`#gateoutputs`）。
2. **一致性测试的语言参数化一次写全，而非先只写 `en` 再扩。** `tasks.md` 3.9 计划"本阶段只传 en"；实际做法
   是直接按 `LANGUAGES = ("en", "zh")` 参数化，在中文版尚不存在时通过只跑 `[en]` 参数达到同一效果，避免为
   同一段代码改两次。第 3 组结束时英文侧全部断言已绿，唯一失败项是指向尚不存在的中文版的链接，符合预期。
3. **新增两条设计未列出的结构断言。** `test_top_level_has_only_the_language_entry`（`docs/` 顶层只有
   `README.md`）与 `test_field_tables_use_the_agreed_headers`（表头必须是本语言约定词且不串用另一语言）。
   两条分别对应 spec 中"顶层只有语言入口文件"与"表头词按语言固定"的场景，属于把已有需求补齐为可测，不是
   新增需求。

## Implementation notes worth keeping

- **`typer` 0.27 把 click 内置为 `typer._click`**，顶层 `import click` 会 `ModuleNotFoundError`。测试只经
  公开入口 `typer.main.get_command(app)` 取命令树，并用鸭子类型访问 `.commands` / `.params` / `.opts`，
  未依赖任何私有路径。这一点在 design D6 中已作为约束记录，实测确认。
- **字段名一律取 Pydantic `model_fields` 的别名优先值**，因此文档写的是 YAML 中真实出现的 `schema`
  （而非 `schema_name`）与 `pass`（而非 `pass_`）。
- **`--complete` 是一个被接受但从未被读取的选项。** `cli.bulk_archive` 声明了
  `complete: bool = typer.Option(True, "--complete")`，函数体中从未引用它——已完成的 change 本来就总是候选。
  文档如实记录为"为与 `--exhausted` 对称而接受，传它不改变任何行为"，未改代码（本变更范围明确排除
  `src/loopspec/**`）。这是实现侧的一个可选清理项，留给后续变更判断。

## Not done

无。`tasks.md` 全部 40 项完成，spec 的 14 条需求逐条自查通过。三条未被自动化覆盖的场景由人工确认：
`README.md` 不含字段参考表与命令参数明细表（已核对，零匹配）；两版散文措辞不同不导致失败（设计刻意如此，
等价断言只覆盖结构化事实）；`docs/README.md` 不承载事实性内容（6 行，仅两条语言链接与一句导航）。
