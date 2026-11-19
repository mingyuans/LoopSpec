---
verdict: PASS
summary: "本轮固定输入下 lint、类型检查、全量单元/BDD 与 timing 测试通过；skill 同步单测 15 个、BDD 3 个；LLM E2E 12 个场景一次通过"
---

# 后端测试：通过

## 审查输入

- 轮次 `001.1:be/tests/check:1`，基线 `23738851a934917e94014f0213dbd51d8dde03e1`。

## 执行的测试

- `uv run ruff check src tests hatch_version.py`：All checks passed!；`uv run mypy src hatch_version.py`：Success
- `uv run pytest -q -n 2 -m "not timing and not llm"`：1732 passed, 1 skipped in 141.84s (0:02:21)
- `uv run pytest -q -m "timing and not llm"`：3 passed, 1745 deselected in 3.69s
- `tests/test_skill_sync.py`（15）：过期/缺失文件被重写且 stdout 不变；一致时不写、不提示；显式与默认 `--home` 均触发且命令收到正确 home；未配置工具不创建；多工具同步；Codex 全局 prompts 不改；文件与目录符号链接不跟随并告警；同步异常不影响命令；version/hook 不触发；无 home 或无工具不做事；Diff 排除同步文件（含对照组）；改过内容、外来文件、删除仍计入 Diff。
- BDD `skill_sync.feature`（3）。
- LLM E2E：`make test-llm` 12 passed，无重跑，$1.686，`.llm-e2e-runs/20261119T165618Z/`。

## 剩余风险

- 本机内存原因以 `-n 2` 运行。
