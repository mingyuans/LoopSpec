# Security Review: PASS

## Scope Reviewed

- `loopspec/changes/cli-usage-manual/design.md`（含其 Security Notes 一节）
- `loopspec/changes/cli-usage-manual/tasks.md`（4 组 25 个任务）
- `loopspec/changes/cli-usage-manual/specs/usage-docs/spec.md`（作为需求侧对照，确认安全约束已被规范化）
- 变更将触及的代码面：新增 `docs/**`（纯 Markdown）、新增 `tests/test_docs_consistency.py`、修改 `README.md` 与 `Makefile`。设计明确 `src/loopspec/**` 不改动，无新增运行时依赖。

## Checks Performed

- **注入风险（shell / 模板 / SQL 等）**：无 SQL、无模板引擎、无 LDAP/XPath。唯一潜在面是"文档里的 ```bash 代码块"——设计（Security Notes 第 2 条）与 `tasks.md` 3.5 均明确规定一致性测试**严禁执行文档中的任何 shell 命令**，只做文本解析；spec「文档一致性校验的执行方式与安全边界」把该禁令固化为需求并附场景。判定：已闭环。
- **不可信输入的反序列化 / 解析**：待解析对象是仓库自有的 Markdown 与其中的 YAML 示例（与测试代码同处一个信任域）。设计指定 `yaml.safe_load` + Pydantic 校验，未使用 `yaml.load`/`Loader=FullLoader`，不存在任意对象构造。判定：安全。
- **路径遍历**：测试写文件的唯一位置是 pytest `tmp_path`（`schema-dir` 类示例物化 `templates/`、`instructions/`），设计明确 **SHALL NOT 写入仓库工作区**。同时本变更的文档内容本身要求正面记录既有的路径安全规则（`artifacts_dir`、`schemas[*].path`、`node.template`、`instruction.file`、`tracks` 必须是非绝对、不含 `..` 的相对路径，且模板/指令不得越出 `templates/`、`instructions/`），属于降低误配风险的正向措施，不新增攻击面。判定：可接受，另见 Notes 第 1 条的加固建议。
- **认证 / 授权**：本变更不涉及任何 authn/authz 逻辑，也不放宽任何既有检查（`src/` 不改）。判定：不适用。
- **密钥与凭据处理**：无凭据读写、无环境变量读取、无日志输出。设计 Security Notes 第 1 条与 spec「文档示例不得包含真实凭据」要求示例只用占位名与仓库内相对路径，`tasks.md` 3.8 落地为自动化断言。判定：已闭环，另见 Notes 第 2 条。
- **第三方依赖**：无新增依赖。一致性测试仅使用已有的 `pytest`、`pyyaml`、`typer` 与项目自身模块。`tasks.md` 3.2 明确禁止 `import click` 与 `typer._click` 私有路径（typer 0.27 已将 click 内置），只经公开入口 `typer.main.get_command`，避免引入未声明依赖。判定：安全。
- **数据暴露 / PII**：文档与测试均不处理用户数据；任务 1.1 采集的 `--json` 样例来自临时目录中自建的占位 change（`add-payment` 一类占位名），不含真实项目信息。判定：安全。
- **网络访问**：设计与任务中无任何网络调用（不引入文档生成器、不做外链可达性探测）。判定：安全。

## Notes

以下均为**非阻塞**的加固建议与残余风险记录，可在 `apply` 阶段顺手落地，不要求返工设计：

1. **`schema-dir` 示例物化时对文件名做一次相对路径校验**。测试会依据示例 YAML 中的 `template` / `instruction.file` 在 `tmp_path` 下创建对应文件；若某示例（或未来被误改的示例）写成 `../../x.md`，写入动作可能逸出 `tmp_path`。建议物化前复用项目已有的 `paths.is_safe_relative_path` 过一遍，非法则直接断言失败。当前威胁模型下不构成漏洞（能改文档即已能改测试代码），但成本极低。
2. **凭据断言失败时不要回显命中的内容**。`tasks.md` 3.8 的检查若命中疑似凭据，断言信息应只给出 `文件:行号` 与命中的规则名，避免把疑似密钥打进测试日志/CI 输出。
3. **任务 1.1 采集样例时对每条命令显式传 `--home <tmpdir>`**。`archive` / `bulk-archive` / `rollback` 会移动目录（含 `.attempts/` 归档动作），一旦漏传 `--home` 就会作用到仓库内真实的 `loopspec/` 工作流主目录，可能移动当前正在进行的 change。这不是安全漏洞而是操作性风险，但后果是可见的工作区变更，建议在采集脚本/命令里把 `--home` 作为固定前缀而非依赖当前工作目录默认值。
4. **保持"单向覆盖"的边界不被误读为宽松**。设计 D4 决定不做"文档不得出现代码里没有的名称"的反向断言，这是可维护性取舍；其后果只是文档可能残留过时描述，不会导致代码行为偏差。若后续手册规模继续扩大，可考虑对错误码/字段两类**闭集**追加反向断言（命令与参数不适合，因为文档需额外记录 `NO_COLOR` 等非 Typer 事实）。
