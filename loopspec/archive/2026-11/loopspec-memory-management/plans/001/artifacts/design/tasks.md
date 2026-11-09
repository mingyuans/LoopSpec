## 1. 引擎：topic 发现、索引与读取（`src/loopspec/workflow_memory.py`）

- [x] 1.1 定义 topic 名正则、常量（`CORE_INLINE_LIMIT=8*1024`、摘要条数 20、`list` 默认 `limit=200`/上限 500、总量上限 5000、`hint` 截断 120）与错误码（`memory_not_found`、`memory_too_large`、`memory_too_many`，路径问题沿用 `unsafe_path`）；验证：topic 名单测覆盖合法与非法（`../x`、`a/b`、大写、过长）。
- [x] 1.2 实现 `list_topics(offset, limit)`：目录描述符 + `O_NOFOLLOW` 枚举，按 topic 名排序，提取 title/hint/bytes/status，子目录、非 `.md`、符号链接被忽略或标注，缺目录为空，返回 `total/nextOffset`；验证：索引字段、hint 规则、`too_large`、符号链接目录与文件、分页取全无重复无遗漏、`limit` 上限、`memory_too_many`。 另：总条目（含非 topic）超过 `ENTRY_SCAN_MAX=20000` 返回 `memory_too_many`，扫描期间消失的条目被跳过；验证：对应用例。 并含：按 topic 名排序、`scandir` 提前终止、`title` 上限、`ignored` 有界（前 `limit` 项 + `ignoredTotal`）、非 UTF-8 文件名转义、贴切的 `fix` 文案；验证：对应用例。
- [x] 1.3 实现 `read_topic`：校验、`O_NOFOLLOW`、`MAX_FILE_BYTES`；验证：正常读取、缺失、超限、符号链接。
- [x] 1.4 实现 `core_view`：按完整条目/段落（前言 + 各 `## ` 小节）边界内联至 8 KiB，放不下的单元即停止，前言超限则不内联，`truncated/shown/bytes/showCommand`，不改原文件，多字节字符安全；验证：整体不超限、超限在小节边界、不出现多行条目前半截、前言超限、无 `## ` 大文件、多字节边界的测试。

## 2. CLI（`src/loopspec/workflow_cli.py`）

- [x] 2.1 注册只读 `memory list [--all] [--offset N] [--limit N] [--json]` 与 `memory show <topic> [--json]`，支持 `--home`；验证：CLI 测试覆盖输出结构、分页与 `nextOffset`、退出码、非法 topic 的结构化错误。

## 3. 读取注入

- [x] 3.1 `workflow_changes.status()` payload 新增 `memory`（core、前 20 条 topics、total、omitted、listCommand、untrustedData），原有键不变；验证：payload 单测，含 topic 数大于 20 的 `omitted`。
- [x] 3.2 `status_report.py` 新增 `SECTION_MEMORY` 与渲染（core 引用 + `sanitize`、前 20 条摘要、`omitted` 与 `memory list` 入口、不可信标注、`(no memory)` 空提示、core `truncated` 时输出“未读全，必须补读”入口）；验证：`test_status_report.py` 新增用例，既有断言不回归。
- [x] 3.3 `workflow_runtime.instructions()` 新增 `memory`（前 20 条摘要 + total/omitted/listCommand + core 读取入口，不含 core 全文）；验证：所有节点摘要相同、无 core 全文。

## 4. init、Diff 与兼容

- [x] 4.1 `cli.init` 创建空 `<home>/memory/`（`lexists` 判断），不预置 topic，重复执行不改已有内容；验证：内容与 mtime 不变的断言，悬空或指向别处的符号链接不崩溃、不覆盖。
- [x] 4.2 `workflow_diff._exclusions` 只排除 `<home>/memory/<topic>.md`（合法 topic 文件）；验证：只改 topic 文件不进 Diff、不触发 `missing_fragments`，`memory/` 下的脚本、子目录、非法名文件仍进入 Diff。 名字像 topic 的符号链接不被排除，照常进入 Diff。
- [x] 4.3 老项目缺 `memory/` 时 status、instructions、`memory list` 不报错；验证：测试。

## 5. Skill 与文档

- [x] 5.1 按 design §7 修改 `builtin/skills/{new,continue,archive}.md`：读侧与维护侧提示词（中英语义对应，共用结构化标记；`new` 为“创建 change 之后、规划前运行 `memory list` 并读 core”，`continue` 与 `new` 含 core `truncated` 时补读 `memory show core`、未读全需报告，`archive` 为“仅在用户已请求归档时执行、整理不构成归档授权、仍 dry-run 与重查证据、冲突不阻塞归档且不出现提问后继续归档”）；验证：`test_skill_templates.py` 断言触发与关键约束标记，且不含 `memory add|archive`、`confirmed_by`、逐条人确认。 并加测试保证 `continue` 与 `archive` 中的 maintenance procedure 逐字一致。
- [x] 5.2 同步 `docs/zh` 与 `docs/en` 的 overview、cli-reference、agent-protocol，写明 topic 约定、读取规则、LLM 与引擎职责、模型行为验收场景；验证：`make docs-check` 通过。
- [x] 5.3 重新生成本仓库已安装的 skill/command 副本（`.claude/skills`、`.claude/commands`、`.codex` 中对应文件）；验证：与 `builtin/skills` 内容一致。

## 6. 总体验证

- [x] 6.1 e2e：放入 `memory/core.md` 与 `memory/testing.md` → status 内联 core 并列摘要 → instructions 给出摘要与入口 → `memory list` 取全索引 → `memory show testing` 返回全文；再放入超过 20 个 topic，验证摘要有界且分页取全。
- [x] 6.2 `make test` 与 `make lint` 全绿，真实输出记录到 `implementation.md`。
- [x] 6.3 整理模型行为验收场景（已有 topic 同义不重复、新主题创建、core 被截断时补读、新证据修订/冲突不覆盖）的预期结果，写入 docs 或实现报告，并如实注明未自动化。
