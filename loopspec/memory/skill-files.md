# loopspec skill/command 文件由 CLI 管理

适用时机：修改 loopspec 的 skill 文本，或在任何项目里看到 `<工具目录>/skills/loopspec-*`、`.claude/commands/lpsx/*` 等文件时。

- 这些文件由 CLI 生成，并在每条带 `--home` 的工作流命令执行前自动同步为当前 CLI 的内置内容（过期覆盖、缺失补上），手工修改会被覆盖。要改 skill，改源文件 `builtin/skills/<verb>.md`（本仓库），不要手工复制或 `sed` 生成副本。来源：skill-auto-sync（2026-11-19）；归档第一段时同步实际纠正了本仓库手工生成而与生成器不一致的 `.claude/commands/lpsx/update-registry.md`。
- 只同步已配置的工具、只写项目根（workflow home 的上一级）内的文件；Codex 的全局 prompts（`~/.codex/prompts`）不会被同步，仍需 `loopspec init --tools codex` 刷新。来源：同上，`tests/test_skill_sync.py`。
