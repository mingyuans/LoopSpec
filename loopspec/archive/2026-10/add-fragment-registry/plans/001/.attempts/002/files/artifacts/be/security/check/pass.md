---
verdict: PASS
summary: "第 1 轮的三项阻塞（预置缓存仓库命令执行、文件名 shell 注入、stdin 死锁）经独立复审与实验确认已修复；未发现新的阻塞问题"
---

# 后端安全审查：通过

## 审查输入
- 轮次 `001.1:be/security/check:2`，基线 `9b90c66c11bab432176d640cfc6caad760706fcc`，固定路径 16 个（与测试 Gate 第 3 轮相同）。
- 由独立的只读子代理复审，实验全部在 scratchpad 中进行；主代理核对结论，并复查了 skill 文本。

## 检查项
- **命令 / 参数注入**：
  - URL 只接受四种形态的白名单；不能以 `-` 开头，不能含 `::`；ssh / scp 的用户名不能以 `-` 开头。
  - tag 经 `check_tag` 校验；commit 必须是 40/64 位十六进制。
  - 所有 git 调用都用参数列表、`shell=False`；URL 前有 `--`；对象参数前有 `--end-of-options`。
- **协议与配置**：
  - `protocol.allow=never`，只放行当前用到的那一种 scheme；另有 `http.followRedirects=false`、`core.hooksPath=/dev/null`、`transfer.fsckObjects=true`。
  - 会改变仓库定位或注入配置的 `GIT_*` 环境变量都被过滤。
  - 私有裸仓库每次都新建，经 dir-fd 与 O_NOFOLLOW 校验：repo.git、`.cache/registry`、`.cache` 中任何一级是符号链接都返回 `unsafe_path`，链接目标不受影响；预置的 include / insteadOf / alternates 一律清除（已实测）。
- **路径穿越 / 符号链接**：
  - 远端只接受普通 blob，符号链接与子模块计为 unsupported。
  - 路径每一级只允许 `[A-Za-z0-9._-]+`，并在远端读树、锁文件、本地扫描、计划条目四处统一校验，不回显不合法的名称（已实测 7 类恶意名称）。
  - 写入和删除都经 dir-fd 与 O_NOFOLLOW；`_prune` 不会删到定义目录以上；staging / preview 是符号链接时返回 `unsafe_path`。
- **篡改与确认边界**：
  - planId 只做相等比较，plan.json 自身的 digest 也要一致。
  - staging 内容按计划记录的哈希复核；本地文件在计划生成后被修改则拒绝。
  - `--resolve` 只能指向冲突条目，`--skip` 只能指向待确认条目。
  - 写入前先完成预览树校验并构建好下一版 lock。
- **敏感信息**：https 不允许 userinfo；stderr 经脱敏、截断，并替换控制字符；锁文件与 JSON 中没有凭据；不读取、不打印环境变量。
- **资源耗尽与死锁**：
  - 限额：单文件 2 MiB、文件数 2048、总量 16 MiB、目录深度 8；stdout 有上限；按命令区分超时。
  - stdin 由后台线程写入，超时覆盖整个过程；`cat-file --batch` 输出逐条校验格式（实测 1900 个 blob、请求约 78KB，没有挂起）。
- **不安全反序列化**：只用 `yaml.safe_load`（经 `parse_yaml`）、`json.loads` 与 pydantic 严格模型。
- **依赖来源**：没有新增依赖，只调用本机 `git`。

## 剩余风险
以下均为非阻塞，建议作为后续加固：
- skill 第 2 步只要求对 `*.instruction.md`、`*.template.md`、`fragment.yaml` 和 profile 展示内容 diff。但 `fragment.yaml` 可以引用任意文件名作为 instruction 或模板（例如 `check.pass.md`、`rules.yaml`），恶意上游可以借此避开内容审阅。建议改为对全部待确认文件和冲突文件展示 diff。
- git 的 stderr（包括远端返回的 `remote:` 行）在脱敏后进入错误消息，bidi 等 Unicode 格式字符没有被过滤。建议在 `redact` 中过滤 Cf 类别，并在 skill 中说明错误文本同样只是数据。
- `run_git` 没有显式关闭 Popen 的管道，也没有 join 写线程（CPython 下影响很小）。
- 已接受：`fetch --depth=1` 的体积只受超时限制；`copytree` 以及 apply 中「检查哈希后再写入」之间存在本地 TOCTOU 窗口；在大小写不敏感的文件系统上，staging 中的同名文件会互相覆盖，但 apply 会以 `registry_plan_stale` 失败关闭；保留 `file://`；`latest` 会跟随上游的更高 tag（文档已建议敏感项目固定 tag）。
