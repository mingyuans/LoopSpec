# Security Review: FAIL

## Blocking Issues

- **`actions/checkout` 默认把 `GITHUB_TOKEN` 持久化进 `.git/config`，而两个 job 都会执行仓库内可被修改的代码。** design D1/D4 与 tasks 5.2/5.3/5.4 都没有要求 `with: persist-credentials: false`。`verify` job 跑 `pytest`（执行仓库里的任意测试代码），`release` job 跑 `uv build`（执行 `pyproject.toml` 声明的构建后端钩子）——这两处都能读到 `.git/config` 里的 `http.extraheader` 凭据。`release` job 持有的是 `contents: write` 令牌，一旦被读走即可改写仓库。修复方向：两个 job 的 checkout 都显式 `persist-credentials: false`；令牌只以 `env: GH_TOKEN` 的形式绑定在调用 `gh` 的那几个 step 上，不要放在 job 级或 workflow 级 `env`。design 与 spec 都需要把"令牌不得暴露给执行仓库代码的步骤"写成显式要求，目前的「凭据与权限最小化」需求只约束了"不写入日志"，覆盖不到这条路径。

- **`release` job 在持有写令牌的同时，从 PyPI 解析并执行未固定版本的构建后端。** `pyproject.toml` 的 `[build-system] requires = ["hatchling"]` 没有版本上界也没有哈希固定，design D1 又决定让 `release` job **重新构建**（而非复用 `verify` 的产物）。结果是：一段每次运行都从网络新解析的第三方代码，在一个能写仓库的 job 里执行。design 的 Risks 一节只讨论了"重复构建是否确定性"，完全没有把它当作供应链问题看。修复方向：要么让 `release` job 不再自己构建（改为从 `verify` 取产物，需重新评估 D1 里"少两个 action 依赖"这个取舍），要么保持重新构建但把构建步骤与持有令牌的步骤在凭据可见性上彻底隔开（配合上一条：令牌只绑定在 `gh` step 上，构建 step 不注入任何令牌），并在 design 里把这条残余风险显式记下来。无论选哪条，design 必须给出结论，spec 需要一条对应的需求。

- **完整性校验存在"空校验即通过"的漏洞：没有任何要求"wheel 的条目必须存在于 `checksums.txt` 中"。** `cli-installation` 的需求只说"校验 wheel 的 SHA256"，其场景写的是"把 wheel 与 `checksums.txt` 下载到同一目录并运行 `sha256sum -c checksums.txt` → 校验通过"。但按 `release-automation` 的资产契约，`checksums.txt` 同时包含 wheel 与 sdist 两行，而脚本只下载 wheel——`sha256sum -c` 会因缺失 sdist 而非零退出，场景与契约自相矛盾。实现者要绕过它只有两条路，且都不安全：用 `--ignore-missing`（macOS 的 `shasum` 是 Perl 脚本，不支持该选项，跨平台直接坏掉；且当没有任何文件被校验时的行为在实现间不一致），或用 `grep` 抠出 wheel 那一行再比对（`grep` 匹配不到时会得到空字符串，若不显式判空就会变成"空 vs 空"的假通过）。这是一个安全控制可以静默失效的缺口。修复方向：spec 需要把"从 `checksums.txt` 中定位 wheel 对应条目失败（缺失或多于一条）时必须以非零码中止"写成显式需求与场景，并让场景与资产契约自洽（例如要求脚本先从 `checksums.txt` 提取出只含 wheel 一行的子集再交给校验工具，且提取结果为空时即失败）；tasks 4.1/4.2 需要相应地把"条目缺失 → 中止"作为一个可验证的任务列出来。

- **`gh release create ... dist/*` 用通配符发布，无法满足 spec"上传且仅上传三个资产"的要求。** tasks 5.7 用 `dist/*` 展开，而 `release-automation` 的资产契约是"SHALL 上传且仅上传"三个指定文件名。通配符把"发布哪些文件"的决定权交给了构建目录的实际内容，任何意外落入 `dist/` 的文件都会被公开发布。修复方向：改为按 spec 的命名契约显式拼出三个文件路径再传给 `gh release create`，并在上传前断言这三个文件都存在（缺失即失败），使发布内容与契约一一对应。

## Scope Reviewed

- `loopspec/changes/add-release-automation/design.md`（D1–D12、Risks、Migration Plan）
- `loopspec/changes/add-release-automation/tasks.md`（全部 8 组任务，重点是标注了 **[SEC]** 的 1.2、2.2、2.3、3.1、3.3、4.1–4.4、5.1、5.2、5.4、5.7、7.2）
- `loopspec/changes/add-release-automation/specs/release-automation/spec.md`
- `loopspec/changes/add-release-automation/specs/cli-installation/spec.md`
- 受影响的既有代码：`pyproject.toml`（`[build-system]`、`[project.scripts]`、版本号）、`src/loopspec/__init__.py`（`__version__`）、`Makefile`

## Checks Performed

- **命令注入 / 参数注入**：版本号在两侧（CI 与客户端）都有正则闸门，且明确要求"校验通过后才参与拼接"，`LOOPSPEC_VERSION="0.1.0; rm -rf /"` 与 `"../../etc/passwd"` 都有对应的拒绝场景——这部分设计是充分的。
- **路径穿越**：版本号是唯一进入文件名/URL 的外部输入，已被同一个正则约束到 `[0-9a-z._-]` 子集；临时目录用 `mktemp -d` 而非固定路径，避免了 `/tmp` 抢占。通过。
- **凭据处理**：不引入任何新 secret、只用自动注入的 `GITHUB_TOKEN`、按 job 拆分权限——方向正确，但**令牌向执行仓库代码的步骤的暴露路径未被覆盖**（见 Blocking Issues 第 1、2 条）。
- **认证 / 授权**：本变更不引入也不修改任何 authn/authz 逻辑。发布权限完全由 GitHub 的仓库权限模型承载，未被绕过或削弱。通过。
- **供应链**：第三方 action 全部 pin 到 40 位 commit SHA 并附版本注释（两个 SHA 已核对为对应 tag 所指 commit），发布不引入第三方 action——这部分是本设计的强项；但构建后端的解析未被纳入考量（见第 2 条）。
- **产物完整性**：强制 SHA256 校验、无跳过开关、安装器只接受本地已校验的文件路径而非远端 URL——意图正确，但存在空校验漏洞（见第 3 条）。
- **不可信输入的解析**：GitHub API 响应用 `sed` 宽松抽取 + 严格正则校验，抽取失败得到空串也会被正则拒绝。解析层不做反序列化，无 `eval`。通过。
- **提权与系统写入**：脚本明确禁止 `sudo`、禁止写系统目录、拒绝回退到会污染 default Python 环境的 `pip --user`。通过。
- **敏感数据外泄**：工作流不向 GitHub 之外的服务发送仓库内容；`--generate-notes` 只汇总本仓库 commit 信息；安装脚本不上报任何遥测。通过。
- **fork PR 的代码执行面**：工作流只监听默认分支 push 与 `workflow_dispatch`，不监听 `pull_request`，因此不存在 fork PR 携带写令牌执行的经典风险。通过（后续若按 design 的 Open Question 加上 `on.pull_request`，必须重新评估这一点）。

## Recommended Fix Direction

前两条是同一个问题的两面——"持有写令牌的 job 里跑了会执行第三方/仓库代码的步骤"。建议在 design 里新增一条决策，专门规定**令牌可见性边界**：checkout 一律 `persist-credentials: false`；令牌只以 step 级 `env` 注入调用 `gh` 的那几个 step；任何执行仓库代码或第三方构建后端的 step 都不得看到令牌。然后据此更新 `release-automation` 的「凭据与权限最小化」需求（补上"不得暴露给执行仓库代码或第三方构建代码的步骤"），以及 tasks 里 5.2/5.3/5.4/5.7 的具体写法。如果决定改为从 `verify` 传递产物以彻底避免在特权 job 里构建，需要回到 D1 明确推翻"不用 artifact action"这个取舍并说明理由。

第三条建议把"定位 wheel 在 `checksums.txt` 中的条目"提升为一个独立的、必须成功的步骤，而不是隐含在"跑一下校验工具"里：提取 → 断言恰好一条 → 才交给校验工具，任一环节失败即非零退出。同时修掉 spec 场景与资产契约不自洽的地方。

第四条按 spec 的命名契约显式列出三个文件即可，顺带加一条"三个文件必须都存在"的前置断言。

其余部分（输入校验、无降级路径、action pin、脚本执行形态、不提权）无需改动，重做时请原样保留——尤其是"没有校验工具就中止、不提供跳过开关"这一条，它是本设计里最不该被便利性侵蚀的约束。
