# loopspec skill/command 文件由 CLI 管理

适用时机：修改 loopspec 的 skill 文本，或在任何项目里看到 `<工具目录>/skills/loopspec-*`、`.claude/commands/lpsx/*` 等文件时。

- 这些文件由 CLI 生成，并在每条带 `--home` 的工作流命令执行前自动同步为当前 CLI 的内置内容（过期覆盖、缺失补上），手工修改会被覆盖。要改 skill，改源文件 `builtin/skills/<verb>.md`（本仓库），不要手工复制或 `sed` 生成副本。来源：skill-auto-sync（2026-11-19）；归档第一段时同步实际纠正了本仓库手工生成而与生成器不一致的 `.claude/commands/lpsx/update-registry.md`。
- 只同步已配置的工具、只写项目根（workflow home 的上一级）内的文件；Codex 的全局 prompts（`~/.codex/prompts`）不会被同步，仍需 `loopspec init --tools codex` 刷新。来源：同上，`tests/test_skill_sync.py`。
- 在 LoopSpec 仓库里开发 skill 时，用 `uv run loopspec` 执行工作流命令，否则全局安装的旧版 CLI 会把副本同步回旧内容（见 [[dev-environment]]）。来源：text-output-default（2026-11-20，实际发生）。
- skill 与命令输出分工：命令的文本报告每节自带读法说明（引用块、字段、下一步、Gate 协议等），skill 只写流程与红线（人工确认、不代替人表态、决策适用范围、权限边界、memory 规则）。新增或修改命令输出时把读法写进该节说明段，不要再写进 skill。例外：continue 与 archive 共享的 memory 维护流程必须保持一致（archive 的 CLI 审阅指引直接取自 archive.md）。来源：skill-dedup（2026-11-20，用户提出并选择全量去重；5 个 skill 4567→4187 词，make test-llm 13 passed）。
