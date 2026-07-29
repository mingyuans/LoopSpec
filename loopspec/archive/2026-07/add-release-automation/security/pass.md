# Security Review: PASS

第 4 轮评审。第 3 轮的 1 项阻塞问题已解决；第 1 轮的 4 项修复成果经逐条核对未被稀释。

## 前一轮阻塞问题的核验结果

**表达式插值造成的脚本注入 —— 已解决，且落到了可机械检查的约束上。**

新增 D18 把边界写成三条规则：`run:` 脚本体内不得出现 `${{ github.* }}` / `${{ env.* }}` / `${{ inputs.* }}` 插值；step 间传值走 `$GITHUB_ENV` / `$GITHUB_OUTPUT` 并以环境变量读取；`if:` 条件、`env:` 的值、`uses:`/`with:` 参数不在此限（它们不进 shell 脚本，不构成注入面）。三条规则的边界划得准确——把 `if: startsWith(github.ref, ...)` 与 `env: GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}` 明确排除在外，避免了"一刀切禁掉所有表达式"那种既不可实现又会让人绕开规则的写法。

关键的一点被讲对了：**D18 与 D6 的正则闸门是两个阶段，不可互相替代**。design 在 Context 的信任边界一节、D2、D6、D18 四处反复点明了这个先后关系——`${{ }}` 在生成脚本文件之前就展开为字面量，载荷在格式校验之前就已执行。上一轮我指出的正是"spec 只有用途闸门、没有执行边界"，现在两者都在，且 spec 的需求正文里显式写了"SHALL 同时满足，SHALL NOT 互相替代"。

落地部分也齐了：`release-automation` spec 新增一条需求带三个场景，其中一个直接就是 `v1.0.0$(<某条命令>)` 这个具体的攻击输入，且断言了正确的结果（命令替换不执行 → 作为普通字符串进入格式校验 → 被拒 → 工作流失败且不创建 Release）；tasks 6.7 是实现约束，6.8 明确"从 `GITHUB_REF_NAME`（环境变量，非插值）取值、先校验再经 `$GITHUB_ENV` 传递"；9.10 是一条可执行的验证动作（`grep -n '\${{'` 后逐条核对出现位置）。

**顺带核验 `$GITHUB_ENV` 本身不成为新的注入点。** 往 `$GITHUB_ENV` 写入不可信值是另一条已知路径（值里带换行可以伪造额外的环境变量）。tasks 6.8 的顺序是"取值 → 严格正则校验 → 才写 `$GITHUB_ENV`"，通过校验的值只可能是 `[0-9a-z._-]` 的子集，不含换行；git 本身也不允许 ref 名含控制字符。这条顺序是对的，不是偶然写对——6.8 的措辞把它固定住了。

## Scope Reviewed

- `loopspec/changes/add-release-automation/design.md`（第 4 轮，D1–D18、Risks、Migration Plan、Open Questions）
- `loopspec/changes/add-release-automation/tasks.md`（第 4 轮，9 组 54 个任务；重点是 **[SEC]** 标注的 1.2、1.4、2.1、3.2、3.3、4.1–4.4、5.1、5.3、5.6、5.7、6.1–6.3、6.5–6.10、6.12、6.14、6.15、8.3、9.5–9.10）
- `loopspec/changes/add-release-automation/specs/release-automation/spec.md`（17 条需求）
- `loopspec/changes/add-release-automation/specs/cli-installation/spec.md`（11 条需求）
- `.attempts/round-001/` ~ `round-003/`（对照历史，确认前几轮的修复成果未被本轮改动稀释）
- 受影响的既有代码：`pyproject.toml`、`src/loopspec/__init__.py`、`Makefile`

## Checks Performed

- **表达式插值 / 脚本注入**：D18 三条规则 + spec 需求 + tasks 6.7 实现约束 + 9.10 验证动作，边界划分正确（非脚本体位置放行），`$GITHUB_ENV` 的写入顺序也正确。通过。
- **命令注入 / 参数注入**：版本号在三处来源（tag 名、`LOOPSPEC_VERSION`、API 的 `tag_name`）共用同一条正则闸门，且都要求"校验通过后才参与拼接"；`gh api` 的参数用环境变量而非插值。通过。
- **版本混淆 / 降级攻击**：D5（`--expect` 三方一致）+ D15（tag 必须可从默认分支到达）+ D16（同名 Release 不得已存在）三者联合，把"能推 tag 者"的实际能力收窄到"发布默认分支历史上某个自身声明了该版本号、且尚未发布过的 commit"。本轮已把这个联合效果从"各条决策的副产品"提升为 D15 的显式论述，并在 spec 的对应需求里写明"移除其中任一条都会削弱该防护"——这一点很重要，因为 D15 仍在 Open Questions 里等人裁决，删它的连带代价现在是写在纸上的。通过。
- **新的授权假设（"能推 `v*` tag 即能发布"）**：如实披露在 Risks，并要求写进 README（tasks 8.3，含"这是仓库配置建议而非已实施控制"的限定）。通过。
- **凭据处理与令牌可见范围**：不引入新 secret；顶层 `contents: read`，仅 `release` 提升为 `write`；每处 checkout 都 `persist-credentials: false`；令牌只以 step 级 `env` 绑定在三个 `gh` step 上；`pytest`/`ruff`/`mypy`/`uv sync`/`uv build`/`shellcheck` 所在 step 无令牌。D15 选 `gh api` 而非 `git fetch`、并在本轮明确写出"可达性校验只能放在 `release` job，因为 `verify` 按 D13 不持令牌"——这个连带推理是对的，而且没有为了"看起来更早拦住"就去破坏更重要的约束。通过。
- **供应链**：两个 action 均 pin 到 40 位 SHA 且附版本注释；发布与可达性校验都用预装 `gh`，不引第三方 action；构建后端加 `>=1.31,<2`。通过。
- **产物完整性**：三步校验（精确匹配定位 → 断言恰好 1 条 → 执行校验）、"没校验到即失败"、禁用 `--ignore-missing`、以临时目录为 CWD、安装器只接本地已校验路径、无任何跳过开关。通过。
- **路径穿越**：进入路径拼接的外部值只有版本号，已被正则约束；临时目录用 `mktemp -d`。通过。
- **不可信输入的解析**：不做反序列化；无 `eval`；JSON 只按单字段文本抽取，随后走严格校验，抽取失败得到的空串同样被拒。通过。
- **提权与系统写入（客户端）**：禁 `sudo`、禁写系统目录、不自动装 uv/pipx、不回退 `pip --user`。通过。
- **传输中断的部分执行**：`main()` 封装 + 末尾调用。通过。
- **失败方向**：逐条核对——插值边界违规（由 9.10 拦在评审阶段）、tag 名非法、tag 不可从默认分支到达、三方版本号不一致（且在构建之前）、Release 已存在、资产缺失、`gh` 查询本身出错，全部 fail-closed。D16 撤掉"跳过算成功"的理由（tag 推送即明确发布意图）站得住。通过。
- **fork PR 执行面**：仍不监听 `pull_request`；Open Questions 已写明将来加上时 D13 与 D18 都须保持、且不得改用 `pull_request_target`。通过。

## Notes

以下为**非阻塞**观察，建议在实现阶段顺手处理，无需再走一轮 gate：

- **D18 目前靠人工 grep（9.10）保障，没有自动化护栏。** 一条 workflow 规约最容易在"下一次有人改这个文件"时失效。方向建议：后续另起变更把 `zizmor` 或 `actionlint` 加进 `verify` job，让 template-injection 与 credential-persistence 这类规则由工具持续检查。本轮不必做——引入新工具本身也是供应链决策，值得单独评估。
- **tasks 6.14 里 `"$TAG"` 的来源未写明。** 建议直接用已校验过的 `VERSION` 重建为 `v$VERSION`：由于校验对象正是 `${GITHUB_REF_NAME#v}`，校验通过即意味着 `GITHUB_REF_NAME` 恰好等于 `v$VERSION`，重建与原值等价，但能免去"这个变量是从哪来的、有没有被校验过"这个问题。
- **`checksums.txt` 的记录用基名，CI 侧生成时也要避免带上 `dist/` 前缀**（客户端侧 4.3 已明确以临时目录为 CWD 执行）。tasks 6.13 已写了"用不含目录前缀的基名"，实现时留意 `sha256sum dist/*.whl` 会带前缀这一点。
- **预发布版本号的规范化差异。** 正则允许 `0.1.0-rc1` 一类写法，而 wheel 文件名会按 PEP 440 规范化为 `0.1.0rc1`，此时 D3 的存在性断言会失败。**失败方向可接受**（报错而非发出错名资产），但首次发预发布版时会撞上，值得在实现时留一行注释。
- **运行时依赖树不在完整性保证范围内**，`[build-system]` 的版本下界也需日后手动跟进（与 action SHA 是同一类维护负担）。两者都已如实声明，方向正确。
