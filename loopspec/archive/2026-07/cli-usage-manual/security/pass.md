# Security Review: PASS

## Scope Reviewed

- `loopspec/changes/cli-usage-manual/design.md`（round 2 重写版，含 Security Notes 一节）
- `loopspec/changes/cli-usage-manual/tasks.md`（round 2 重写版，6 组 40 个任务）
- `loopspec/changes/cli-usage-manual/specs/usage-docs/spec.md`（14 条需求 / 53 个 Scenario，作为需求侧对照，确认安全约束已被规范化）
- `.attempts/round-001/security/pass.md`（round 1 的审阅结论与 4 条非阻塞建议，用于核对本轮是否已落地）
- 变更将触及的代码面：新增 `docs/**`（纯 Markdown，双语并列目录）、新增 `tests/test_docs_consistency.py`、修改 `README.md` 与 `Makefile`。设计明确 `src/loopspec/**` 不改动，无新增运行时依赖。

本轮的审阅重点是 round 1 之后新增的双语化设计（`design.md` 的 D1/D2/D6 第五组、`tasks.md` 第 4/5 组）是否引入新的安全面，以及 round 1 提出的 4 条建议是否已进入设计与任务。

## Checks Performed

- **双语化是否引入新的安全面**：没有。两个语言版本是并列的手写 Markdown 目录（`design.md` D1），Non-Goals 明确**不引入 i18n 框架、翻译工具链或机器翻译流水线**、不做构建期合成。因此不存在翻译服务的外部调用、不引入新依赖、不新增构建步骤。新增的第五组跨语言断言只是把两份仓库内文本做集合与逐字比对，属于纯读取。判定：无新增攻击面。
- **注入风险（shell / 模板 / SQL 等）**：无 SQL、无模板引擎、无 LDAP/XPath。唯一潜在面仍是"文档里的 ```bash 代码块"——`design.md` Security Notes 第 2 条与 `tasks.md` 3.5 明确规定一致性测试**严禁执行文档中的任何 shell 命令**，只做文本解析；spec「文档一致性校验的执行方式与安全边界」把该禁令固化为需求并配 `#### Scenario: 校验不执行文档中的命令`。双语化使 ```bash 块数量翻倍，但禁令是按块类型而非按数量生效的。判定：已闭环。
- **不可信输入的反序列化 / 解析**：待解析对象是仓库自有的 Markdown 与其中的 YAML 示例（与测试代码同处一个信任域）。设计指定 `yaml.safe_load` + Pydantic 校验，未使用 `yaml.load`/`Loader=FullLoader`，不存在任意对象构造。判定：安全。
- **路径遍历**：测试写文件的唯一位置是 pytest `tmp_path`（`schema-dir` 类示例物化 `templates/`、`instructions/`），设计明确 SHALL NOT 写入仓库工作区。**round 1 建议 (1) 已落地**：`design.md` Security Notes 第 3 条与 `tasks.md` 3.5 均要求物化前先用 `paths.is_safe_relative_path` 校验示例中声明的 `template`/`instruction.file` 文件名，非法则在写入任何文件之前断言失败；spec 中另有 `#### Scenario: 示例文件名不安全时拒绝物化` 与之对应。判定：已加固。
- **跨语言链接引入的路径风险**：新增的跨语言等价断言会解析并跟随相对链接（第五组 (f)(g)、`tasks.md` 3.7/5.5）。这些链接来自仓库自有文档，且断言只做"目标文件是否存在"的存在性检查与"是否越出同语言目录"的规则检查，不读取目标内容之外的东西、不跟随外部 URL、不做网络请求。判定：安全。建议见 Notes 第 1 条。
- **认证 / 授权**：本变更不涉及任何 authn/authz 逻辑，也不放宽任何既有检查（`src/` 不改）。判定：不适用。
- **密钥与凭据处理**：无凭据读写、无环境变量读取。spec「文档示例不得包含真实凭据」要求示例只用占位名与仓库内相对路径，并**对两个语言版本同等执行**；`tasks.md` 3.8 落地为自动化断言。**round 1 建议 (2) 已落地**：spec 明确失败时"只报告文件与行号及命中的规则名，SHALL NOT 回显命中的内容"，并配 `#### Scenario: 命中疑似凭据时不回显内容`；`tasks.md` 3.8 的任务描述同样标注。判定：已闭环。
- **第三方依赖**：无新增依赖。一致性测试仅使用已有的 `pytest`、`pyyaml`、`typer` 与项目自身模块。`tasks.md` 3.2 明确禁止 `import click` 与 `typer._click` 私有路径（typer 0.27 已将 click 内置），只经公开入口 `typer.main.get_command`。判定：安全。
- **数据暴露 / PII**：文档与测试均不处理用户数据。**round 1 建议 (3) 已落地**：`tasks.md` 1.1 现明确要求"每条命令显式传 `--home <tmpdir>`"，`design.md` Security Notes 与 Migration Plan 第 1 步同样标注——避免 `archive`/`rollback` 作用于仓库内真实工作流主目录而移动进行中的 change。采集到的 `--json` 样例来自临时目录中自建的占位 change。判定：已加固。
- **网络访问**：设计与任务中无任何网络调用（不引入文档生成器、不做外链可达性探测、不调用翻译服务）。判定：安全。
- **round 1 建议 (4) 的处置**：round 1 建议"未来可对错误码/字段两类闭集追加反向断言"。round 2 在跨语言维度上采纳了同一思路——`design.md` D6 说明第五组之所以能做**双向**集合相等，正是因为比对对象限定为标识符与示例这类闭集；而"代码 → 文档"方向仍保持单向。这是对建议的合理部分采纳，未采纳部分（代码 → 文档的反向断言）理由已在 D6 中说明（文档必然包含 Typer 之外的事实，反向断言会持续误报）。判定：处置得当，非阻塞。

## Notes

以下均为**非阻塞**的加固建议与残余风险记录，可在 `apply` 阶段顺手落地，不要求返工设计：

1. **链接检查只解析仓库内相对链接，遇到外部 URL 直接跳过而非尝试访问**。`tasks.md` 3.7/5.5 的链接断言应显式排除 `http://`/`https://`/`mailto:` 等 scheme，避免将来有人"顺手"把存在性检查升级成可达性探测，从而在 CI 中引入网络请求与外部依赖。设计与任务中目前均无网络调用意图，这条是防止后续误加。
2. **跨语言逐字比对失败时的报错同样不应回显整段内容**。第五组 (e) 要求示例块逐字相等，一旦不等，diff 输出会把两版示例整块打进测试日志。示例本身按 spec 不含凭据，因此风险很低；但为与凭据检查的策略保持一致，建议失败信息优先给出"文件对 + 块序号 + 首个差异行号"，需要完整 diff 时由开发者本地重跑。
3. **`tasks.md` 1.1 采集样例时注意 `--json` 样例中的绝对路径**。`loopspec status`/`instructions` 的响应含 `resolvedOutputPath` 等绝对路径字段，若直接把临时目录的真实绝对路径（含机器用户名，如 `/Users/<name>/...`）粘进文档，等于把本机用户标识写入仓库——这与 spec「文档示例不得包含真实凭据」中"真实用户标识"一条相抵。建议采集后把路径统一替换为占位根（如 `/path/to/project/...`），并考虑在 3.8 的检查规则中加入"疑似本机 home 路径"一条。这是本轮**新识别**的问题，非 round 1 遗留。
4. **保持"代码 → 文档"单向覆盖的边界不被误读为宽松**。其后果只是文档可能残留过时描述，不会导致代码行为偏差。散文层面的双语漂移同理（`design.md` Risks 已明确接受，由人工 review 兜底）。
