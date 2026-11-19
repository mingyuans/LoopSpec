---
verdict: PASS
summary: "用本分支 CLI 在独立临时目录端到端执行 25 项检查，覆盖 proposal 全部 14 条验收条件，全部通过"
---

# 验收测试：通过

## 验收条件核对

- [x] AC1 新 clone、全局存储为空时 `fragment list` 成功：列出 13 个定义，存储中出现该 commit 快照。
- [x] AC2 新 clone 上 `change new` → `plan create` → `plan approve` → `node instructions`：返回的 instruction 与 registry 中文件逐字一致。assurance Gate 同时读取 registry 与 config 规则由单测 `test_assurance_reads_registry_rules_and_config_rules` 覆盖。
- [x] AC3 registry 仓库被移走后，同 commit 的第二个 checkout 仍可用。
- [x] AC4 快照文件被篡改报 `registry_store_corrupt`；删除该快照目录后下次读取自动重新拉取。
- [x] AC5 首次 `registry update` 后 `git status` 干净（`.cache/registry` 自带 `.gitignore`）；同版本再次 update 返回 `upToDate: true`。
- [x] AC6 `registry apply` 后 `git status` 只有 `?? loopspec/registry.lock.yaml`，项目内没有 fragments/profiles。stale 的四种情形由 `test_registry_sync.py` 覆盖。
- [x] AC7 项目内保留同名 Profile 时，`plan validate` 与 `node instructions` 都报 `registry_local_conflict`；删除副本后恢复。
- [x] AC8 `profile save docs-only` 后，`profile list` 中 `bugfix`=registry、`docs-only`=local 并存。
- [x] AC9 `profile save bugfix` 报 `profile_exists`，且未写文件。
- [x] AC10 v1 lock 加 vendored 副本时报 `registry_local_conflict`；删除副本后按 v1 lock 使用全局存储；`registry update`（`migration: true`）与 `apply` 后 lock 为 `version: 2`。
- [x] AC11 registry 模式缺少 lock 时报 `registry_not_synced`。
- [x] AC12 registry 不可达且存储为空时报 `registry_fetch_failed`，未留下半成品快照。
- [x] AC13 非 registry 项目 `init` 仍复制内置定义，定义均来自本地。
- [x] AC14 `make lint` 等价命令、全量测试与 `make test-llm` 通过（见执行的测试）。

## 执行的测试

- `artifacts/qa/test/acceptance.sh <worktree>/.venv/bin/loopspec`：在 `/tmp/lpqa/run.dWyP` 中真实执行 CLI，25 项 PASS、0 项 FAIL。前两次运行中的失败均为脚本自身问题，已修正后重跑：clone 中缺少空的 `changes` 目录；篡改前存储已被前一步清空；对已批准的 Plan 做 validate 需要 `base_revision`；列表顺序断言写错。
- `uv run pytest -q -n 2 -m "not timing and not llm"`：1670 passed, 1 skipped；`-m "timing and not llm"`：3 passed。
- `make test-llm`：12 passed，$1.666，`.llm-e2e-runs/20261119T054402Z/`。

## 剩余风险

- 未用真实远端（GitHub SSH）registry 验证，均为本地 `file://` 仓库。
- 未用 SHA-256 对象格式仓库验证。
- 本仓库自身 `loopspec/` 仍是 v1 lock 加 vendored 定义，需要按迁移步骤处理（非目标）。
