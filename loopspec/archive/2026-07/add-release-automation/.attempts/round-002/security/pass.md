# Security Review: PASS

第 2 轮评审。第 1 轮的 4 项阻塞问题逐条核验如下，均已在 `design.md` / `tasks.md` / 两份 spec 中落到**可检查的**约束上，而不是换个说法重述风险。

## 前一轮阻塞问题的核验结果

**① checkout 默认持久化令牌，而两个 job 都执行仓库内代码 —— 已解决。**
新增 D13 把"令牌可见性边界"写成三条缺一不可的规则：每处 `actions/checkout` 显式 `persist-credentials: false`；令牌仅以 step 级 `env` 绑定在调用 `gh` 的 step；执行仓库代码或第三方代码的 step（`pytest`/`ruff`/`mypy`/`uv sync`/`uv build`/`shellcheck`）一律不注入令牌。`release-automation` spec 新增了对应需求，四个场景全部可以靠读 workflow 文件断言（而非只能靠人自觉）；tasks 6.2/6.5/6.8 是实现动作，9.6 是逐行复核动作。D13 还指出因为发布走 `gh` 而非 `git push`，禁用凭据持久化不损失任何功能——这消除了"为了能推 tag 而不得不留着凭据"的借口。

**② `release` job 持写令牌的同时执行未固定版本的构建后端 —— 已解决（采用了两条修复路径中的第二条，且理由成立）。**
D14 明确拒绝了"改从 `verify` 传产物"这条路，理由是：那只是把同一段构建后端代码搬到另一个 job 执行，"执行第三方构建代码"这件事没有消失，却要多引入两个 action 依赖——用一个新的供应链面换一个未被真正消除的风险。取而代之的是三层控制：`[build-system] requires` 加版本上下界（`hatchling>=1.31,<2`）缩小解析范围；构建 step 看不到令牌（D13 第 3 条）且工作目录 `.git/config` 中无凭据（D13 第 1 条），因此被投毒的构建后端拿不到可改写仓库的凭据；发布内容按文件名白名单（D3），被投毒的后端往 `dist/` 多写文件也发不出去。**这个论证接受**：攻击者的收益从"拿到写令牌"降到"污染一次本次构建的产物"，而后者本就受 GitHub 仓库权限模型约束。design 还如实记下了残余风险——版本范围不是哈希固定，范围内仍会解析到最新补丁版；`pyproject.toml` 无法表达哈希，彻底解决需要预装固定版本的构建后端，代价与本变更规模不匹配。这个残余风险被显式接受并写进了 spec（该需求明确要求"SHALL NOT 被表述为哈希级固定"），没有过度承诺。

**③ 完整性校验存在"空校验即通过"漏洞 —— 已解决。**
D8 改写为三个都必须成功的步骤：精确匹配文件名定位条目 → 断言结果**行数等于 1** → 才交给校验工具。核心原则被写死为「"没校验到"必须等于"校验失败"」。两个具体陷阱都被显式堵上：禁用 `--ignore-missing`（并写明 macOS 的 `shasum` 不支持它、且"零个文件被校验"时各实现行为不一致），以及要求**精确文件名相等而非子串匹配**（否则 `0.1.0` 会命中 `0.1.0.post1`）。spec 补了四个失败场景——条目缺失、空文件/HTML 错误页、重复条目、相似版本号误匹配——每个都是可写成测试的。tasks 4.1–4.4 是实现，9.5 要求用这四种夹具实测"确认四种都非零退出而不是静默通过"。第 1 轮那个与资产契约自相矛盾的场景（把含两行的 `checksums.txt` 直接 `-c`）已被替换。

**④ `dist/*` 通配符发布 —— 已解决。**
D3 改为按命名契约显式拼出三个文件路径、逐个断言存在、缺任一即失败，再传给 `gh release create`。spec 的资产契约需求补上了"SHALL NOT 使用通配符"以及存在性断言，并新增两个场景（产物名与预期版本号不符 → 失败；`dist/` 中的意外文件 → 不出现在 Release 中）。D3 还点出一个附带收益：显式列出顺带免费得到"版本号读取与构建产物名不一致"这个断言，失败方向是**关闭**（报错而非发出名字对不上的资产）。

## Scope Reviewed

- `loopspec/changes/add-release-automation/design.md`（第 2 轮，D1–D14、Risks、Migration Plan、Open Questions）
- `loopspec/changes/add-release-automation/tasks.md`（第 2 轮，9 组任务；重点是 **[SEC]** 标注的 1.2、2.1、3.2、3.3、4.1–4.4、5.1、5.3、5.6、5.7、6.1、6.2、6.3、6.5、6.6、6.8、6.10、6.11、8.2、9.5–9.7）
- `loopspec/changes/add-release-automation/specs/release-automation/spec.md`（12 条需求）
- `loopspec/changes/add-release-automation/specs/cli-installation/spec.md`（11 条需求）
- `loopspec/changes/add-release-automation/.attempts/round-001/`（对照第 1 轮原文，确认修复不是重述）
- 受影响的既有代码：`pyproject.toml`（`[build-system] requires`、`[project.scripts]`、版本号）、`src/loopspec/__init__.py`（`__version__`）、`Makefile`

## Checks Performed

- **命令注入 / 参数注入**：版本号在 CI 与客户端两侧都有同一条正则闸门，且明确要求"校验通过后才参与拼接"；`LOOPSPEC_VERSION="0.1.0; rm -rf /"` 与 `"../../etc/passwd"` 各有拒绝场景。GitHub API 响应用 `sed` 宽松抽取后立刻过正则，抽取失败得到的空串同样被拒。通过。
- **路径穿越**：版本号是唯一进入文件名/URL 的外部输入，已被正则约束到 `[0-9a-z._-]` 子集；临时目录用 `mktemp -d` 而非固定路径，避免 `/tmp` 抢占。通过。
- **凭据处理**：不引入任何新 secret；只用自动注入的 `GITHUB_TOKEN`；按 job 分权限（顶层 `contents: read`，仅 `release` 提升为 `write`）；**且令牌的可见范围被限制到调用 `gh` 的 step**（D13）。第 1 轮的缺口已闭合。通过。
- **认证 / 授权**：本变更不引入也不修改任何 authn/authz 逻辑；发布权限完全由 GitHub 仓库权限模型承载，未被绕过或削弱。通过。
- **供应链**：第三方 action 全部 pin 到 40 位 commit SHA 并附版本注释（两个 SHA 经 `gh api repos/<repo>/git/ref/tags/<tag>` 核对为对应 tag 所指 commit）；发布不引第三方 action；构建后端加了版本上下界。残余的"构建时解析第三方代码"被显式记录并用令牌隔离 + 发布白名单抵消。通过。
- **产物完整性**：三步强制校验、"没校验到即失败"、无跳过开关、禁用 `--ignore-missing`、精确文件名匹配、安装器只接受本地已校验的文件路径而非远端 URL。通过。
- **不可信输入的解析**：不做反序列化；无 `eval`；JSON 只按单字段做文本抽取，随后走严格校验。通过。
- **提权与系统写入**：禁 `sudo`、禁写系统目录、拒绝回退到污染 default Python 环境的 `pip --user`、不自动替用户安装 uv/pipx。通过。
- **敏感数据外泄**：工作流不向 GitHub 之外的服务发送仓库内容；`--generate-notes` 只汇总本仓库 commit 信息；安装脚本无遥测。通过。
- **传输中断的部分执行**：`install.sh` 全部逻辑封装进函数、末尾才调用入口，`curl | sh` 收到半个脚本时不会执行任何安装动作。通过。
- **fork PR 的代码执行面**：只监听默认分支 push 与 `workflow_dispatch`，不监听 `pull_request`，无 fork PR 携带令牌执行的经典风险。design 的 Open Questions 已写明将来若加 `on.pull_request` 必须重新评估、且不得改用 `pull_request_target`。通过。
- **失败方向**：逐条检查了新增控制的失败方向——校验条目缺失→失败、校验工具缺失→失败、资产缺失→失败、`gh release view` 查询本身出错→失败（不误判为已存在/不存在）。全部 fail-closed。通过。

## Notes

以下为**非阻塞**观察，建议在实现阶段顺手处理，无需再走一轮 gate：

- **`checksums.txt` 的记录用基名，校验时须在临时目录下执行。** spec 已要求记录中的文件名是不含目录前缀的基名，因此 `install.sh` 执行 `sha256sum -c` 时必须以临时目录为工作目录（或等价手段），否则会因找不到文件而失败。这是 fail-closed 的方向，但实现时容易踩一次；顺带提醒 CI 侧生成 `checksums.txt` 时也要避免带上 `dist/` 前缀。
- **建议给调用 `gh` 的 step 显式加 `GH_REPO: ${{ github.repository }}`。** 因为 `persist-credentials: false`，最好不要依赖 `gh` 从 git remote 推断仓库。这是健壮性问题而非安全问题。
- **预发布版本号的规范化差异。** 正则允许 `0.1.0-rc1` 一类写法，而 wheel 文件名会按 PEP 440 规范化为 `0.1.0rc1`，此时 D3 的存在性断言会失败。**这是可接受的失败方向**（报错而非发出错名资产），但首次发预发布版时会撞上，值得在实现时留一行注释。
- **运行时依赖树不在完整性保证范围内。** `uv tool install <wheel>` 仍会从 PyPI 解析 `pydantic`/`typer`/`rich`/`pyyaml`/`questionary`。design 与 Risks 已如实声明不做承诺，方向正确；若将来要收紧，路径是发布带哈希的约束文件——留作后续变更。
- **`[build-system]` 的版本下界会随时间落后。** `hatchling>=1.31,<2` 的下界是本次验证所用版本，日后需要跟进时记得同步；这与 action SHA 的手动更新是同一类维护负担，可考虑一并纳入将来引入 Dependabot 的那个变更。
