# Security Review: PASS

## Scope Reviewed
- `design.md`（D1–D10，第 2 轮新增 D9、D10）、`tasks.md`（7 组 31 项，第 2 轮新增第 3 组）、`specs/schema-sources/spec.md`（安全边界 requirement 新增 6 个 scenario）、`specs/loopspec-cli/spec.md`、`specs/usage-docs/spec.md`。
- 受影响代码：`src/loopspec/schema_loader.py`、`src/loopspec/instructions.py`、`src/loopspec/config.py`、`src/loopspec/models.py`、`src/loopspec/paths.py`、`src/loopspec/cli.py`、`src/loopspec/artifacts.py`，以及新模块 `schema_sources.py`。

## Checks Performed
- **第 1 轮阻塞项 a（instructions/templates 子目录外链 → 任意文件读取）**：已解决。D9 把基准改为 `schema_dir.resolve()`，由单一判定 `_contained_file` 覆盖 instruction 与 template；tasks 3.1/3.3 实现，3.5 用真实符号链接覆盖 `instructions/` 与 `templates/` 外链，5.4 在 CLI 层断言响应不含外部内容。不是换个说法：判定基准本身改变了，针对原攻击路径（`instructions -> ~/.ssh`）有直接测试。
- **第 1 轮阻塞项 b（`schema.yaml` 外链 → 经校验错误回显泄露内容）**：已解决。D9 与 tasks 3.2 要求在 `read_text` 之前判定；3.5 用含标记值的合法 YAML 做外链目标，并断言错误消息中不含该标记值。
- **第 1 轮阻塞项 c（诊断信息回显链接目标）**：已解决。D10 把规则写进 design，spec 新增「诊断信息不含链接目标」scenario，tasks 2.3、2.5、3.1、3.5 对 warning 与错误文本做「不含目标路径片段」断言。
- **TOCTOU**：D9 与 tasks 3.4 要求 `_read_template` 在读取时刻重新判定，spec 有对应 scenario。
- **路径遍历 / 名称注入**：schema 名在拼接前统一按 kebab-case 校验（D3，tasks 2.3），并补上 `.workflow.yaml` `schema` 未校验的既有缺口（tasks 1.2），测试覆盖 `../../etc`、`../x`、`a/b`（tasks 1.3、2.5、5.3）。
- **环境变量与敏感信息**：源 `path` 不做环境变量展开，只做 `~` 展开（D4）；错误消息只回显配置原文（tasks 2.2），测试以 monkeypatch `HOME` 指向 `tmp_path`，不读取真实环境值。
- **注入**：无 shell / SQL / 模板执行面；YAML 仍用 `safe_load`；未引入网络访问（远程源为非目标，含 `url` 的条目因 `extra: forbid` 被拒）。
- **写入范围**：外部源只读（D4），tasks 4.6 做代码审查项、5.5 用快照对比做回归断言。
- **依赖**：无新增第三方依赖。
- **认证授权 / 密钥**：不涉及。

## Notes
- 残余风险（已接受，已在文档任务 6.1 中说明）：外部源内容本身就是 agent 指令，可写该目录的人能影响 agent 行为。这是共享 schema 的本意，缓解手段是只配置受信任、写权限受控、最好受版本控制的目录。
- D9 的收紧同样作用于 local 源；已确认仓库内置 schema 不含符号链接。自定义本地 schema 若依赖 schema 目录外的链接会开始报错，属于有意为之，已在 design 的 Risks 中注明。
- 后续建议（非阻塞）：远程源落地时，需单独评审拉取来源校验、固定到 commit/哈希的版本锁定，以及缓存目录权限。
