## 背景

用户在 workflow home 中已经配置好 `fragments/`、`profiles/`（手工定制，或经 `loopspec registry apply` 同步），之后只想刷新 AI 工具里的 loopspec Skill / `/lpsx:*` 命令，于是重新执行 `loopspec init`。

现状：`init`（`src/loopspec/cli.py`）每次都无条件调用 `install_resources`（`src/loopspec/workflow_resources.py`）。该函数逐文件补齐缺失的内置资源，已存在的同名文件不改写；因此用户删除或改名过的内置 Fragment、Profile（或其中单个文件）会被重新写回，与用户定制 / registry 同步的目录混在一起。用户并未要求这一步，属于非预期副作用。

## 用户场景

- 已配置用户：workflow home 中已有 `fragments/` 或 `profiles/`，执行 `loopspec init --tools claude` 只为刷新 Skill，期望 fragments/profiles 不被动到，除非自己明确同意。
- 新用户：首次执行 `loopspec init`，期望和现在一样直接得到内置 Fragment 与 Profile。
- CI / 脚本 / Agent：以非交互方式或 `--json` 调用 `init`，不能被提示阻塞；需要时可显式要求更新资源。

## 范围

1. 判定“已存在”：workflow home 下 `fragments/` 或 `profiles/` 任一为非空目录。
2. 未存在（首次 init，或两目录均不存在/为空）：行为不变，直接执行 `install_resources`。
3. 已存在时：
   - 交互终端且非 `--json`：提示 “fragments/profiles 已存在，是否用内置资源补齐？[y/N]”，默认 N；回答 y 才执行 `install_resources`。
   - 非交互或 `--json`：不提示、默认跳过。
   - 新增 `--update-resources` 选项：跳过提示，直接执行 `install_resources`（任意模式下均生效）。
4. 输出：
   - JSON 新增字段 `resourcesUpdate`，取值 `installed`（首次或已同意/强制更新）或 `skipped`（已存在且未更新）；`copiedWorkflowResources` 保持原义（跳过时为 `[]`）。
   - 人类可读输出在跳过时打印一行提示，说明已保留现有 fragments/profiles，以及如何用 `--update-resources` 更新。
5. Skill/命令脚手架、hooks 安装、`config.yaml` 创建逻辑不变。
6. 同步更新 `docs/en/cli-reference.md` 与 `docs/zh/cli-reference.md` 中 `loopspec init` 的说明与用法行。

## 非目标

- 不改变 `install_resources` “只补齐缺失文件、不改写已有文件”的语义；不新增强制覆盖为内置版本的模式。
- 不改动 registry 同步流程（`registry update/apply`）与 `registry.lock.yaml`。
- 不改动 `config.yaml` 的生成逻辑和工具选择器（picker）流程。

## 验收条件

自动化测试（pytest，`tests/test_cli.py`，以 `CliRunner` 运行，交互态通过 monkeypatch `loopspec.cli.is_interactive` 模拟）：

- [ ] AC1 首次 init（`--json`）：`fragments/requirements/fragment.yaml` 与 `profiles/bugfix.yaml` 被创建，`resourcesUpdate == "installed"`，`copiedWorkflowResources` 非空。
- [ ] AC2 已存在 + `--json`：删除 `profiles/bugfix.yaml` 后再次 init，该文件**不**被恢复，`resourcesUpdate == "skipped"`，`copiedWorkflowResources == []`，退出码 0。
- [ ] AC3 已存在 + `--json --update-resources`：被删除的 `profiles/bugfix.yaml` 被补回，`resourcesUpdate == "installed"`；已定制的文件内容保持不变。
- [ ] AC4 已存在 + 非交互人类输出（无 tty）：不提示、不恢复被删文件，输出包含跳过提示及 `--update-resources` 字样，退出码 0。
- [ ] AC5 已存在 + 交互终端，输入 `n`（或直接回车）：被删文件不恢复，输出包含确认问题。
- [ ] AC6 已存在 + 交互终端，输入 `y`：被删文件被补回。
- [ ] AC7 已存在 + 交互终端 + `--update-resources`：不出现确认问题，被删文件被补回。
- [ ] AC8 已存在时 `--tools claude --json` 仍正常刷新 Skill（`.claude/skills/loopspec-new/SKILL.md` 存在），且 fragments/profiles 未被补齐。
- [ ] AC9 只有 `fragments/` 非空、`profiles/` 不存在时也视为已存在（`--json` 下跳过，`profiles/` 中无内置文件被写入）。
- [ ] AC10 现有测试全部通过（`make test`），含 `test_init_keeps_existing_resources`、文档一致性检查（`make docs-check` 若存在）。

## 风险

- 兼容性：以前依赖 `loopspec init` 在已有 home 上补齐新增内置 Fragment 的用户（如 release notes 升级步骤 “执行 `loopspec init --tools ...` 补齐内置 Fragment 与 Profile”），在非交互下将不再自动补齐。应对：提供 `--update-resources`，并在 release notes 升级步骤中改为带该选项；跳过时输出明确提示。
- 交互提示与 `--json` 混用：JSON 输出不得夹带提示文字。应对：`--json` 一律不提示，并有测试覆盖（AC2、AC8）。
- 输入处理：确认输入仅接受 `y`/`yes`（不区分大小写）为同意，其余（含 EOF）均视为拒绝，避免误更新。
- 安全：不引入新的文件写入路径；仍通过已有的 `install_resources`（拒绝链接/特殊文件、限制深度与数量）写入。
