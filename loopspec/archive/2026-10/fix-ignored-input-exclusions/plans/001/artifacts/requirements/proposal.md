## 背景

`collect_diff()`（`src/loopspec/workflow_diff.py`）计算需求 Diff 时，会列出所有被 git 忽略的未跟踪路径（`git ls-files --others --ignored --exclude-standard --directory`）。只要其中任意一项既不是本需求的控制文件，也不在 `workflow.generated_dirs` 中，就抛出 `ignored_input` 并中止命令。

这条检查目前造成以下问题：

- **所有需要计算 Diff 的命令都会被拦下**，包括 `gate begin/record`、assurance、有证据时的 `change status` 和 `change archive`。add-fragment-registry 因此无法查看状态，也无法正常归档，最后只能 `--force` 按未完成归档。
- **常见的无害文件都会触发**：
  - 本仓库实测的阻塞项：`.idea/`、`dist/`、`repos/`、`loopspec/.cache/`、`loopspec/.DS_Store`，以及 `loopspec/archive/**/.DS_Store`；
  - 其中 `loopspec/.cache/registry/` 是 `registry update` 自己写入的缓存（`registry_sync.py` 的 `CACHE`），所以任何跑过 registry 同步、且 `.gitignore` 忽略了 `.cache` 的项目都会被卡住。
- **`generated_dirs` 无法解决**：
  - 取值受白名单 `GENERATED_DIRS` 限制（`workflow_planning.py:25`），其他名字报 `unsafe_exclusion`；
  - 只匹配父目录名，不匹配文件名；
  - 不支持通配符，也不能按完整路径排除。
- **报错不指明具体路径**，用户只能自己排查。

此外，add-fragment-registry 的 assurance 之所以判 FAIL，是因为 `docs/**`、`.claude/**`、`*.md` 等路径命中 `rules.yaml` 的 project-support 规则，但 pr-review 的 `evidence.paths` 不覆盖它们（65 条 `missing_fragments`）；`loopspec/config.yaml` 等路径又不命中任何规则（`unknown_paths`）。人已决定：本仓库中这些路径不纳入门禁，由人工 review 把关。

经讨论确认：

- 被忽略的文件不会被 `git add` 提交，不会进入 PR，也不会上线；
- 已跟踪的文件不受 `.gitignore` 影响，改动照样进 Diff；
- `.gitignore` 和 `config.yaml` 本身的修改也在 PR 里，由人工 review 把关。

因此 `ignored_input` 改为**告警并记录到审查报告**；同时用一个统一的 `excluded_paths` 取代 `generated_dirs`，让项目能明确声明哪些路径不纳入门禁。

## 用户场景

- 在 macOS 上开发的工程师，Finder 在仓库里生成了 `.DS_Store`。Gate、status、archive 应能正常运行，`.DS_Store` 只作为告警写进 assurance 报告；在 `excluded_paths` 里配置 `.DS_Store` 后，告警也会消失。
- 使用 registry 同步的项目，执行 `loopspec registry update` 后，Gate 和 assurance 不受缓存目录影响，也不产生告警。
- 项目希望文档、生成的 skill、IDE 和构建目录不纳入门禁，可以在 `excluded_paths` 里用名字（`.idea`、`*.log`）或完整路径（`docs/**`、`loopspec/config.yaml`）声明。
- 人工审查者阅读 assurance 报告时，能看到有哪些被忽略但未声明的路径，从而判断是否存在用 `.gitignore` 藏代码的情况。

## 范围

1. **`ignored_input` 从错误改为告警**
   - `collect_diff()` 不再因为"被忽略且未排除"的路径抛错，而是把这些路径收集进快照（`DiffSnapshot` 新增字段）。保留排序后的前 20 个路径和总数。
   - 告警**不参与** `diff_digest` 和 `scope_digest` 的计算：被忽略文件的增删不会让已有 Gate 证据过期。
   - **写进 assurance 的审查报告**：系统生成的 `pass.md` / `fail.md` 增加 `warnings`（被忽略路径列表与总数），`summary` 写明告警数。诊断文件 `.gates/<assurance>/assurance.yaml` 同步加 `warnings`。告警不影响 PASS/FAIL 判定。
   - 代码 Gate 的 `gate begin`、`gate record` 输出，以及 `change status` 输出，都带上同样的 `warnings`，方便审查的 Agent 写进自己的审查报告。
   - 删除 `ignored_input` 错误码。
2. **用 `workflow.excluded_paths` 取代 `generated_dirs`（不兼容变更）**
   - 删除 `workflow.generated_dirs` 字段、`GENERATED_DIRS` 白名单和 `unsafe_exclusion` 错误码。配置中仍写 `generated_dirs` 时，读取配置报错，错误信息提示改用 `excluded_paths`。
   - 新增 `workflow.excluded_paths`：模式列表，最多 128 项，匹配规则与 `.gitignore` 一致：
     - **不含 `/` 的模式**：对路径中**每一级名字（包括最后一级的文件名）**用 `fnmatch.fnmatchcase` 匹配。例如 `__pycache__`、`.DS_Store`、`*.log`、`.idea`。
     - **含 `/` 的模式**：用 `fnmatch.fnmatchcase` 匹配完整的仓库相对路径，`*` 可以跨目录。例如 `docs/**`、`loopspec/config.yaml`、`.claude/**`。
   - 命中的路径不进入 Diff：不要求任何审查，不参与 assurance 判定，不影响证据摘要；被忽略的路径命中时也不产生告警。
   - 校验：不能为空，不能含 NUL，不能是绝对路径，不能有 `.` 或 `..` 这样的路径分量。含 `/` 的模式沿用 `relative_path(pattern, glob=True)`。
3. **自动排除 `<home>/.cache/`**：引擎内置这条排除，把 workflow home 下的 `.cache/` 当作和需求控制文件同级的固定排除项，既不进 Diff 也不产生告警。仓库里其他位置的 `.cache/` 不受影响。
4. **本仓库配置**（`loopspec/config.yaml`）：删除 `generated_dirs`，改为
   ```yaml
   excluded_paths: [.venv, __pycache__, .pytest_cache, .mypy_cache, .ruff_cache,
                    .idea, dist, repos, .DS_Store,
                    docs/**, README*, '*.md', .claude/**, .codex/**, .github/**, loopspec/config.yaml]
   ```
5. **文档与测试**：
   - 同步 `docs/zh` 与 `docs/en` 的 configuration（删除 `generated_dirs`，新增 `excluded_paths`）、cli-reference（删除 `ignored_input`、`unsafe_exclusion`，补充 `warnings` 输出）、overview（Diff 排除说明）；
   - release-notes 写明 `generated_dirs` 的不兼容变更和迁移方法；
   - 补充并修改单元测试。

## 非目标

- 不修改 assurance 的判定规则，包括 `unknown_paths` 和 `missing_fragments` 的严重级别、规则级 `severity`。
- 不修改 `loopspec/fragments/**`（含 `rules.yaml` 和 pr-review 的 `evidence.paths`），避免和 registry 冲突。本仓库用 `excluded_paths` 让相关路径不进 Diff，从而绕开二者的矛盾；`project-support` 规则在本仓库里因此不再命中任何路径，保留不动。
- 不优化 `collect_diff()` 的性能：目前每次读取全部文件、扫描两遍，`MAX_BUNDLE_BYTES` 也按全仓库统计。另开需求。
- 不支持 `!` 取反、`**` 的 gitignore 特殊语义或以 `/` 开头的锚定写法；`*` 的语义沿用 fnmatch。
- 不修改代码 Gate 审查报告的格式（仍然只有 `verdict` 和 `summary`），由 Agent 自行把告警写进 `summary`。
- 不处理 `state-md-writeback` 需求。

## 验收条件

**告警**
- [ ] 工作区存在被忽略、未排除的目录或文件时，`collect_diff()` 不抛异常，快照的 `warnings` 包含该路径。`ignored_input` 错误码已从源码和文档中删除。
- [ ] 被忽略、未排除的路径有 25 个时，告警只列出排序后的前 20 个，总数为 25。
- [ ] 已记录证据后，新增一个被忽略文件，证据仍然有效（`diff_digest` 和 `scope_digest` 不变）。
- [ ] assurance 在有告警、其他检查都通过时判 PASS；系统写入的 `pass.md` 包含 `warnings` 和总数，`summary` 提到告警数；诊断文件包含相同的 `warnings`。没有告警时，报告中的告警为空或不出现。
- [ ] assurance 报告增加告警字段后，FAIL → `plan rollback`、`report_hash` 证据校验、`change archive` 都能正常处理（回归测试覆盖 rollback 路径）。
- [ ] `gate begin`、`gate record`、`change status` 的 JSON 输出中有 `warnings` 字段，内容和快照一致。

**excluded_paths**
- [ ] 配置中写了 `generated_dirs` 时，读取配置报错，错误信息里提到 `excluded_paths`。`unsafe_exclusion` 错误码和 `GENERATED_DIRS` 白名单已删除。
- [ ] `excluded_paths: [.DS_Store]` 能排除 `.DS_Store` 和 `a/b/.DS_Store`，不排除 `a.DS_Store`。
- [ ] `excluded_paths: [__pycache__]` 能排除根目录和任意深度的 `__pycache__/` 下的文件，不排除 `foo__pycache__/x`。
- [ ] `excluded_paths: ["*.log"]` 能排除 `a/b/x.log`，不排除 `x.log.bak`。
- [ ] `excluded_paths: [docs/**, loopspec/config.yaml]` 能排除 `docs/a.md` 和 `loopspec/config.yaml`，不排除 `src/loopspec/config.yaml`。
- [ ] `excluded_paths: ['*.md']` 时，`builtin/skills/new.md` 的改动不在 Diff 中，assurance 不对它报 `unknown_paths` 或 `missing_fragments`；`src/x.py` 的改动仍在 Diff 中。
- [ ] 被忽略的路径命中 `excluded_paths` 时不产生告警。
- [ ] 非法值（空字符串、绝对路径、含 `..` 或 `.` 分量）在读取配置时被拒绝；未配置 `excluded_paths` 时，只有需求控制文件和 `<home>/.cache/` 被排除。

**其他**
- [ ] `<home>/.cache/registry/x` 在未配置任何排除项时，既不进 Diff 也不产生告警；仓库根目录被忽略的 `.cache/x` 仍然产生告警。
- [ ] 本仓库改为新配置后，执行 `loopspec change status fix-ignored-input-exclusions` 与本需求的全部 Gate 不再报错退出，assurance 能正常判定。
- [ ] `make test` 全部通过，lint 无新增问题，`tests/test_docs_consistency.py` 通过。

## 风险

- **不兼容变更**：删除 `generated_dirs` 后，旧配置读取会直接报错。应对：错误信息给出迁移方法（把原来的名字原样搬进 `excluded_paths`，语义一致），并写进 release notes。
- **安全边界放宽**：
  - `excluded_paths` 不限制取值，可以写成 `src/**` 把业务代码排除在门禁之外；
  - `ignored_input` 降级后，被忽略的本地文件不再阻断流程。
  - 应对：`config.yaml` 和 `.gitignore` 的修改都在 PR 里，由人工 review 把关；未声明的被忽略路径会写进 assurance 报告，保留可见性。文档写明排除业务代码的后果。
- **`*.md` 排除范围大（人已明确接受）**：fnmatch 的 `*` 加上按名字匹配，`'*.md'` 会排除仓库里所有 Markdown，包括会发布出去的 `builtin/skills/*.md`、`builtin/fragments/**/*.md`（skill 与 Fragment 指令）。这些文件的改动之后不再经过任何 Gate，只靠人工 review。`.claude/**`、`.codex/**` 中生成的 skill 同理。`README*` 也会命中 `docs/README.md` 等任意位置的 README。
- **审查报告格式变化**：assurance 的系统报告目前是 `{verdict, summary}`，加上 `warnings` 后，读取这份报告的地方（例如严格校验的 `FailureReport`、rollback 时的归档、`report_hash` 校验）可能因为多出的字段而报错。应对：在设计阶段梳理所有读取点，用回归测试覆盖。
- **旧证据兼容**：已有 assurance 证据的 `report_hash` 按旧格式计算。校验时比较的是落盘文件的 hash，旧文件不变就仍然有效；只有新记录才写新格式。用测试确认。
- **配置变化会让证据失效**：修改 `excluded_paths` 会改变 Diff 条目，可能让已有证据过期。这符合预期：排除范围变了，就应当重新审查。
- **告警量**：大型仓库可能有大量被忽略的路径，因此列表上限 20 条并附总数，避免报告和输出过大。
