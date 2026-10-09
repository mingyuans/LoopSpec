## 完成的任务

本 Plan 没有 design/tasks 节点，按 proposal 的范围 1–5 实现：

1. **`ignored_input` 改为告警**
   - `collect_diff()` 不再抛错，把被 Git 忽略、未排除的路径收集到 `DiffSnapshot.ignored`，按路径排序；`warnings()` 返回最多 20 条 `ignoredPaths` 与 `ignoredTotal`，没有告警时返回 `None`。
   - 告警不参与 `diff_digest` 和 `scope_digest`。
   - Git 的 `--directory` 输出会把"只装着被忽略内容的目录"也列一行，后面再列其中的条目。这类容器目录不单独判定，只判定条目本身。否则一个只含 `.DS_Store` 的目录也会产生告警。
2. **用 `workflow.excluded_paths` 取代 `generated_dirs`**
   - 删除 `generated_dirs`、`GENERATED_DIRS` 白名单与 `unsafe_exclusion`。旧字段在读取配置时报 `config_invalid`，`fix` 提示迁移到 `excluded_paths`。
   - 匹配规则：不含 `/` 的模式匹配任意一级名字（含文件名），含 `/` 的模式用 fnmatch 匹配完整路径；目录条目按 `目录/` 匹配，所以 `docs/**`、`repos/**` 能命中被忽略的整个目录。
   - 每个模式用 `relative_path(glob=True)` 校验，最多 128 项。
3. **自动排除 `<home>/.cache/`**：作为固定排除项，与当前 Change 的控制路径同级。
4. **告警接入输出与报告**
   - `gate begin` 和 `gate record` 返回 `warnings`；`gate begin` 的 instruction 提示把告警写进报告摘要。
   - `change status` 只在为复核证据计算过 Diff、且确有告警时返回 `warnings`。
   - assurance 诊断新增 `warnings`；系统报告的 `summary` 末尾追加"N 条告警：……（另有 M 条未列出）"。
5. **本仓库配置**：`loopspec/config.yaml` 改用 `excluded_paths`，内容按 proposal。
6. **文档**：zh/en 的 configuration、cli-reference、overview、release-notes 已同步。
7. **返工（第 1 次，来自 be/review/check 的 FAIL）**
   - `warning_text()` 给告警路径设了总长度上限 `MAX_WARNING_CHARS = 8000`，超出部分不列出，统一计入"另有 N 条未列出"，`ignoredTotal` 照实给出。这样系统 FAIL 报告的 `summary` 不会超过 `FailureReport` 的 16384 字符限制。
   - 新增回归测试 `test_warning_text_keeps_failure_summary_within_report_limit`：20 个约 4000 字符的路径。
   - 顺手简化 `_exclusions()` 中 cache 路径的写法，去掉不会被用到的 `None` 分支，行为不变。

## 改动文件

- 引擎
  - `src/loopspec/workflow_diff.py`：排除函数、告警收集、`DiffSnapshot.ignored` 与 `warnings()`
  - `src/loopspec/workflow_models.py`：`ProjectWorkflow.excluded_paths` 及校验
  - `src/loopspec/workflow_planning.py`：删除白名单与 `unsafe_exclusion`，更新 `config_invalid` 的提示
  - `src/loopspec/workflow_evidence.py`：begin、record 返回 `warnings`
  - `src/loopspec/workflow_runtime.py`：status 返回 `warnings`
  - `src/loopspec/workflow_assurance.py`：诊断 `warnings`，`warning_text()` 写入报告摘要
- 测试
  - `tests/test_workflow_diff.py`：重写忽略与排除相关用例（告警、上限、摘要稳定、名字匹配、路径匹配、被忽略路径命中排除、home cache、旧字段报错）
  - `tests/test_workflow_planning.py`：旧字段迁移提示、合法与非法模式
  - `tests/test_workflow_assurance.py`：告警写进报告和各输出、无告警时报告不变、带告警的 FAIL 报告仍能被解析
- 文档：`docs/{zh,en}/configuration.md`、`cli-reference.md`、`overview.md`、`release-notes.md`
- 配置：`loopspec/config.yaml`

## 执行的检查

- 返工后：`uv run pytest tests/test_workflow_assurance.py tests/test_workflow_diff.py -q`：33 passed；`make lint` 通过；`ruff format --check` 通过
- 返工前：`make test`：922 passed（6 分 27 秒）
- `make lint`：ruff All checks passed；mypy Success，31 个源文件没有问题
- `uv run pytest tests/test_docs_consistency.py`：43 passed
- `make install-local` 后执行 `loopspec change status fix-ignored-input-exclusions`：正常返回，没有告警

## 与设计的偏差

- **告警只写进 `summary`，报告没有独立的 `warnings` 字段。** FAIL 报告由严格模型 `FailureReport` 解析，只允许 `verdict` 和 `summary`；加字段会让 status 和 rollback 无法解析 `fail.md`。结构化的告警保留在诊断文件 `assurance.yaml` 和命令输出里。
- **`change status` 只在计算过 Diff 时返回 `warnings`。** `status()` 在 begin、record 等命令内部也会被调用；每次都算一遍 Diff 会额外增加全仓库扫描，所以只在已有证据、需要复核时附带告警。
- **带告警的 FAIL 没有实际执行 `plan rollback`。** 测试夹具里的 assurance 没有 `on_fail`，所以测试验证的是：带告警的 `fail.md` 能被 status 解析，节点进入 failed/exhausted。rollback 读取的是同一个 `failure_report()`。

## 后续事项

- assurance 判定严重级别（规则级 `severity`、`unknown_paths` 可配置为 warn）另开需求。
- `collect_diff()` 每次都读全仓库、扫两遍，`MAX_BUNDLE_BYTES` 按全仓库统计，这个性能问题另开需求。
- `state-md-writeback` 草稿的基线还是 `a2bfe30`，恢复前需要重建。
