# Security Review: PASS

## Scope Reviewed
- 第 3 轮（approval 第 1 轮 changes requested 之后重做）：`proposal.md`（已按 registry 模型重写）、`design.md`（D1–D8）、`tasks.md`（8 组 33 项）、`specs/schema-registry/spec.md`、`specs/lpsx-skills/spec.md`、`specs/usage-docs/spec.md`。
- 将受影响的代码：新模块 `src/loopspec/registry.py`，以及 `models.py`、`config.py`、`errors.py`、`cli.py`、`builtin/skills/update-schemas.md`；schema 加载路径（`schema_loader.py`）不改。

## Checks Performed
- **命令 / 参数注入（本次新增的主要风险）**：唯一的子进程入口为 `_run_git`（tasks 2.1），使用 `shell=False` 与参数列表，URL / ref 之前有 `--`；URL 在进入子进程之前经白名单校验（拒绝 `-` 开头、`::`、`ext::`、`http://`、`git://`），ref 有字符白名单并拒绝 `-` 开头与 `..`（tasks 1.2 / 1.3）。测试捕获 `subprocess.run` 参数做断言（tasks 2.4）。
- **协议滥用**：每次调用都前置 `protocol.allow=never` 与单一协议白名单（D2），挡住了 `ext` 与重定向到其他协议。
- **远程内容造成的路径穿越 / 符号链接 / 子模块**：不 checkout 工作区，只读 git 对象；拒绝 `120000` / `160000` 条目；逐段校验路径，并拒绝 `.git` 段（D4，tasks 3.1）；写入时经 `resolve_within`，并逐级检查父目录不是符号链接，再原子替换（D7，tasks 5.3），有针对「本地 schema 目录为外链」的测试（tasks 5.5）。第 1 轮 security 的阻塞项 a / b 所依赖的「外部目录直接作为 schema 加载」模型已被 approval 否决；registry 永远不会写入符号链接，这条攻击路径在新模型下不存在。原来的既有缺口已列为后续加固项（design Open Questions），不是被换了个说法搁置。
- **凭据与敏感信息**：拒绝 https URL 内嵌 userinfo，且错误消息不回显原 URL（tasks 1.2，并断言 `ghp_xxx` 不出现）；loopspec 不读取、不打印环境变量，认证完全交给本机 git 凭据配置；`GIT_TERMINAL_PROMPT=0` 防止挂起；stderr 截断输出。第 1 轮阻塞项 c（诊断回显敏感路径）在新模型中对应的是 URL / 凭据回显，已覆盖。
- **不可信的反序列化**：锁文件是被提交的文件，经 pydantic 严格校验（键、commit、哈希格式）（tasks 1.4）；YAML 继续使用 `safe_load`；`plan.json` 由 loopspec 自己生成，且位于 `.cache` 下。
- **资源耗尽**：单文件 1 MiB、总数 2000 的限额，读取前先查大小（tasks 3.2）；git 调用 300 秒超时。
- **完整性与写入授权**：`update` 只读 `<home>/schemas/` 与锁文件（有快照断言，tasks 4.3）；`apply` 在写入之前完成 planId、冲突、本地哈希复核、`load_schema` 四项校验（tasks 5.2）；`--resolve` / `--skip` 的路径与计划键做精确匹配，不做拼接（tasks 5.1）。skill 要求所有写入都经用户确认（tasks 6.1 / 6.2）。
- **依赖**：不新增 Python 依赖；运行时依赖本机 `git`，缺失时给出明确错误。
- **认证授权**：loopspec 不实现认证；仓库访问控制由 git 托管平台负责。

## Notes
- 非阻塞，建议实现时一并处理：tasks 3.3 目前只把「本地文件本身是符号链接」记为 `unsupported`。实现本地哈希读取与 `localPath` 时，应复用 tasks 5.3 的父目录符号链接检查——本地 `<home>/schemas/<name>/instructions` 若是外链，按上游路径直接拼接读取就会读到目录外的文件，并把该路径作为 `localPath` 交给 LLM。触发前提是项目自己在本地放了外链（registry 无法造成这种情况），风险低，但修复成本也低。
- 非阻塞：`--plan` 参数只用于与最新 planId 做相等比较，不参与路径拼接；实现时保持这一点（暂存路径只由 `plan.json` 中的 id 计算）。
- 残余风险（已接受，并在 tasks 7.1 中写入文档）：registry 内容最终会成为所有接入项目的 agent 指令，能写 registry 的人就能影响这些项目。缓解手段是逐项的用户确认，加上 registry 侧的分支保护与代码评审。
- 残余风险（已接受）：`file://` registry 会在用户指定的本地仓库上运行 `git-upload-pack`；这个路径由用户自己配置，与在该仓库中手动执行 git 的风险相同。
