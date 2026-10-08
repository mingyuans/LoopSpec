---
verdict: PASS
summary: "12 条验收条件全部满足：真实 CLI 端到端验收（file:// 本地 registry）覆盖配置拒绝、git 缺失、首次同步零写入、upToDate/离线、latest 选版、三方分类、冲突/过期/成功写入与 skill 分发，其余条件由 Gate 中的自动化测试验证"
---

# 验收测试：通过

## 验收条件核对
- [x] 1. 未配置 `registry` 时行为不变：`fragment list` 中所有条目的 `registry` 为 null，`registry update` 返回 `registry_not_configured`。`make test` 905 passed / 1 skipped（测试 Gate 第 4 轮）。
- [x] 2. `ext::sh -c x`、`http://`、`git://`、`https://user:s3cr3t@…`、`-oProxyCommand=x` 均返回 `config_invalid`，输出中不含 `s3cr3t`。
- [x] 3. 首次 update：本地 fragments 与 profiles 的哈希前后一致，没有生成锁文件；与上游一致时 `files` 为空。首次同步时的 conflict 和 upstream-added 分类由 `test_first_sync_classifies_without_writing` 覆盖。
- [x] 4. 同步后同时出现 `upstream-modified`（design）、`local-modified`（qa-testing）、`conflict`（bugfix），符合预期；upstream-deleted 等分类由 `test_categories_after_sync` 覆盖。
- [x] 5. apply 后再次 update 返回 `upToDate: true`。改为固定 tag `v1.10.0` 后，在 `PATH=/nonexistent`（没有 git）的环境下仍离线返回 `upToDate: true`。只调用 ls-remote 由 `test_unchanged_commit_only_runs_ls_remote` 覆盖。
- [x] 6. 同时存在 `v1.9.0`、`v1.10.0`、`v2.0.0-rc1` 时，选中的是 `v1.10.0`；没有 tag 时跟踪 HEAD，由单元测试覆盖。
- [x] 7. 符号链接、子模块、不合法名称、超限文件由 `test_registry_git.py` 覆盖（测试 Gate 第 4 轮 108 passed）。
- [x] 8. apply 不带 `--resolve` 时返回 `registry_conflict_unresolved`；planId 错误时返回 `registry_plan_stale`；带 `--resolve profiles/bugfix.yaml=upstream` 时成功写入两个文件；未确认的 local-modified 文件保持本地内容。本地漂移和校验失败零写入由单元测试覆盖。
- [x] 9. `PATH=/nonexistent` 时返回 `registry_unavailable`；拉取失败的错误码与脱敏由单元测试覆盖。
- [x] 10. `loopspec init --tools claude` 生成了 `.claude/skills/loopspec-update-registry` 与 `.claude/commands/lpsx/update-registry.md`；skill 正文的约束由 `test_update_registry_skill_guards_writes` 覆盖。
- [x] 11. `make docs-check`（`test_docs_consistency.py`）43 passed：中英文文档包含新命令、选项、字段与错误码。
- [x] 12. 没有新增 Python 依赖；`make test` 与 `make lint` 通过（测试 Gate 第 4 轮）。

## 执行的测试
- `bash scratchpad/scripts/qa.sh <scratchpad>`：通过仓库源码的 `uv run --project … loopspec` 调用真实 CLI，在 scratchpad 中建立 `file://` registry（tag 依次为 v1.0.0、v1.9.0、v1.10.0、v2.0.0-rc1），依次执行 init、update、apply、list，输出见上文逐条核对。
- 引用的自动化结果：测试 Gate 第 4 轮 `make test` 905 passed / 1 skipped，registry 专项 108 passed，`make lint` 通过；`make docs-check` 43 passed。

## 剩余风险
- 没有对真实的 GitHub https / ssh registry（含私有仓库认证）做验收，只用了 `file://`；建议发布前手工验证一次。
- 代码审查与安全审查留下的非阻塞改进尚未处理：依赖被删时的报错难懂；来源变化的 warning 措辞与实际分类不符；部分跳过删除会留下孤儿目录；skill 的内容 diff 范围偏窄；`redact` 没有过滤 Unicode 格式字符。
- 最终保障检查预计会因为 `docs/**`、`.claude/**`、`.codex/**`、`loopspec/**` 等路径缺少覆盖而失败（用户已决定暂时不处理），与本功能的验收结果无关。
