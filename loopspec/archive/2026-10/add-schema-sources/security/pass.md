# Security Review: PASS

## Scope Reviewed
- 第 4 轮（approval 第 2 轮 changes requested 之后重做）：`proposal.md`、`design.md`（D1–D10，本轮新增 D9 两层版本号与 D10 ls-remote 预检，D1 的 `ref` 改为 `version`，D3 改为按预检结果拉取）、`tasks.md`（9 组 40 项）、`specs/schema-registry/spec.md`（新增「版本选择与 ls-remote 预检」「schema 级与 registry 级版本号的展示」两个 requirement）、`specs/lpsx-skills/spec.md`、`specs/usage-docs/spec.md`。
- 将受影响的代码与第 3 轮相同：新模块 `registry.py`，以及 `models.py`、`config.py`、`errors.py`、`cli.py`、`builtin/skills/update-schemas.md`。

## Checks Performed
- **第 3 轮结论是否仍然成立**：命令注入防护（`_run_git` 单一入口、`shell=False`、`--`、协议白名单）、远程树读取（只读对象、拒绝符号链接 / 子模块、逐段路径校验、限额）、apply 的四项写前校验与写入边界均未改动。第 3 轮的两条非阻塞建议已写进 tasks 4.3（本地读取复用父目录符号链接检查，并且不把不安全的路径作为 `localPath` 输出）与 tasks 6.1（`--plan` 只做相等比较）。
- **新输入 1：`registry.version`**。取值为 `latest`，或经 `validate_tag_name` 校验的 tag 名（字符集 `[A-Za-z0-9._+-]`，不以 `-` / `.` 开头，不含 `..`、`@{`，不以 `.lock` 结尾）（tasks 1.3）。字符集中不含 `:`、空白、`*`、`^`、`~`，因此拼进 refspec `+refs/tags/<tag>:refs/loopspec/upstream` 时无法注入额外的 refspec，也无法改写目标 ref；由于不以 `-` 开头，它也不能被当作 git 选项。
- **新输入 2：`ls-remote` 的输出（远程可控）**。逐行严格解析「十六进制 commit + 制表符 + refname」，只接受 `refs/tags/*` 与 `HEAD`，tag 名经同一校验，不合法则丢弃，且 warning 中不回显（tasks 3.1）。测试以 `v1.0.0$(touch x)` 验证不会被执行、也不会被输出（tasks 3.4）。解析出的 tag 会进入 JSON 与 LLM 上下文，但已被限制在安全字符集内，不能携带提示注入所需的空白或标点。
- **版本选择的正则**：`^v?\d+(\.\d+){0,2}$` 没有嵌套量词，不存在 ReDoS 风险；比较时使用数字元组。
- **竞态（TOCTOU）**：预检与 fetch 之间远端可能变化，D3 与 tasks 2.3 要求 fetch 之后 `rev-parse` 的 commit 必须等于预检结果，否则失败，不会拿别的 commit 去生成计划。
- **离线判定依赖锁文件**：固定版本且锁文件 `tag` 相同时直接返回 `upToDate`，不启动任何子进程。锁文件被篡改的后果最多是「误报已是最新」，不会触发任何写入或执行；锁文件本身仍经严格的 pydantic 校验（tasks 1.4 已扩展到 `tag` 与 `schemas`）。
- **新输入 3：上游 `schema.yaml` 的 `version`**。只经 `yaml.safe_load` 读取单个字段，不合法则为 `null` 加 warning（tasks 4.6）；版本号不参与分类与写入决策（D9），因此伪造的版本号只会影响展示，不会导致错误写入。
- **凭据**：没有引入 GitHub API、`gh` 或 token；`ls-remote` 与 fetch 一样复用本机 git 凭据配置，仍有 `GIT_TERMINAL_PROMPT=0`。
- **依赖**：无新增依赖。

## Notes
- 残余风险（维持第 3 轮的判断，已接受）：registry 内容最终会成为 agent 指令；缓解手段是逐项的用户确认，加上 registry 侧的分支保护与评审。
- 非阻塞：`latest` 模式下，远端可以通过推送更高的 semver tag 让所有项目「看到」新版本。这与「跟踪最新版本」的语义一致，且所有写入仍需用户确认；对供应链更敏感的项目可以使用固定版本，文档任务 8.1 中宜点明这一取舍。
