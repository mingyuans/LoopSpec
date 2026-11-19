## 背景

`loopspec init --tools <...>` 把内置 skill 写进项目（`<工具目录>/skills/loopspec-*/SKILL.md`，以及支持命令的工具的 command 文件，如 `.claude/commands/lpsx/*.md`）。CLI 升级后内置 skill 会变（例如归档改为两段式），但项目里的文件只有重新 init 才更新，agent 常按旧 skill 调用新 CLI 而出错。skill 文件没有版本标记。

## 用户场景

- 开发者升级 CLI 后在项目里执行任意工作流命令（如 `loopspec change status`），项目中已配置工具的 loopspec skill/command 自动变成与 CLI 一致，stderr 提示更新了哪些文件，命令本身照常输出。
- 新版 CLI 新增了一个 skill：已配置工具缺少的那个 skill/command 被补上。
- 自动更新的 skill 文件不会进入当前 Change 的交付 Diff，不影响 Gate 证据与 assurance。
- 未配置的工具、`hook pre-tool-use`、`version`、`update`、`init` 不触发同步。

## 范围

- 所有带 `--home` 的工作流命令在执行前同步：项目根取 workflow home 的上一级；对已配置的工具（已有任一 loopspec skill 文件），逐个比较每个内置 skill 与 command 的应有内容与磁盘内容，缺失或不一致即原子写入；只处理项目根内的文件（不写用户全局目录，如 Codex 的 `~/.codex/prompts`）。
- 一致性以文件内容比较判断（不加版本字段）；项目内对这些文件的手工修改会被覆盖。
- 同步失败只在 stderr 告警，不影响原命令。
- 交付 Diff 固定排除 loopspec 管理的 skill/command 文件（仅限这些精确路径的普通文件；符号链接与同目录的其他文件仍计入）。
- 中英文文档、测试（单元、BDD、LLM E2E 回归）。

## 非目标

- 不为未配置的工具新建文件；不修改 hook 配置；不写项目根以外的路径。
- 不提供关闭开关（如需要另行讨论）。

## 验收条件

- [ ] 已配置 claude 的项目中，改动一个 loopspec SKILL.md 与一个 command 文件、删除另一个 skill，执行 `loopspec change status <c>` 后三者都与 `loopspec init` 生成的内容一致，stderr 列出这 3 个文件，stdout 不变。
- [ ] 内容一致时不写任何文件（mtime 不变）、stderr 无提示。
- [ ] 未配置的工具目录不被创建；`hook pre-tool-use`、`version`、`init` 不触发同步。
- [ ] 目标路径是符号链接或目录被替换时不跟随、不写入，stderr 告警，命令照常完成。
- [ ] 同步写入的 skill/command 文件不出现在交付 Diff（assurance 不报 unknown path、证据不过期）；同目录的非 loopspec 文件与符号链接仍计入 Diff。
- [ ] workflow home 不存在或项目没有配置任何工具时什么都不做。
- [ ] lint、全量测试、docs 一致性、LLM E2E 通过。

## 风险

- 手工修改的 loopspec skill 被覆盖：文档说明这些文件由 CLI 管理。
- 读命令产生文件写入：只在内容不同时写，且排除出交付 Diff；版本库中会出现这些文件的变化，需要提交。
- 性能：每条命令多读几十个小文件，可忽略。
