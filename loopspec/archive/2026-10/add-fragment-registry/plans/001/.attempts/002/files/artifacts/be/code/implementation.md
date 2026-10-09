## 完成的任务

### 第 2 轮：修复安全 Gate 第 1 轮 FAIL（priorAttempts seq 1）

- **阻塞问题 1，缓存仓库可被预置**：`RegistryRepo.ensure()` 不再复用磁盘上已有的 `repo.git`。每个实例首次使用时先在 O_NOFOLLOW 打开的缓存目录里用 lstat 检查：如果是符号链接或非目录，返回 `unsafe_path`；如果是目录，就用 `rmtree(dir_fd=)` 删除。然后新建目录并 `git init --bare`。`fetch_base` 改为先按锁中的 tag 拉取基线，失败时再按 commit 拉取，以适应每次都是新仓库的情况。
- **阻塞问题 2，文件名可注入 shell**：新增 `SEGMENT_RE = [A-Za-z0-9._-]+` 与 `safe_segments`，在四处统一校验：
  - 远端读树时，名称不合法的条目计入 warning，不回显原名。
  - 锁的 `FILE_RE`、`is_definition_file`，不合法时返回 `config_invalid`。
  - 本地扫描时，名称不合法的文件跳过并计数 warning，不回显原名。
  - `PlanEntry.path` 也做同样的校验，哈希字段校验为 64 位十六进制。
- **阻塞问题 3，stdin 可能死锁**：`run_git` 改为在后台线程里写 stdin，超时控制覆盖整个过程。`_read_blobs` 遇到缺少换行、内容截断或结尾缺 LF 时一律返回 `registry_invalid`。
- **非阻塞加固**：
  - 增加 `-c http.followRedirects=false`。
  - ssh 与 scp 形态的用户名禁止以 `-` 开头。
  - apply 先构建下一版锁、再写入任何文件。
  - skill 第 2 步要求展示指令、模板、定义类文件的内容 diff，提示用户留意其中的指令性文字，并提醒审阅锁文件的 diff。
- **新增回归测试（先红后绿）**：
  - `test_preplanted_cache_repository_is_never_trusted`：预置 config 中的 `url.insteadOf` 指向恶意仓库，验证不会生效。
  - `test_cache_repository_symlink_is_refused`
  - `test_shell_metacharacters_in_names_are_dropped`（5 组参数）
  - `test_ssh_user_cannot_start_with_dash`
  - `test_local_files_with_unsafe_names_are_ignored`
  - `test_lock_with_unsafe_file_name_is_invalid`
  - 以下两项写好时就已通过，作为防回归保护：`test_large_batch_read_completes`（1900 个 blob，在 macOS 上没有复现死锁）、`test_forged_plan_cannot_write_outside_definitions`。
- `test_unchanged_commit_only_runs_ls_remote` 的断言改为 `["init", "ls-remote"]`：每次都会新建私有仓库，但仍然不 fetch、不读树。

### 第 1 轮（保留）


- 1.1/1.2：新增 `RegistrySpec`（url / version / path 白名单校验，`registry_scheme`、`check_tag`），`WorkflowConfig.registry`；`config_invalid` 提示加入 registry，且不回显 URL。
- 2.1–2.3：新增 `registry_git.py`。`run_git` 带协议白名单，过滤会改变仓库定位或注入配置的 `GIT_*` 环境变量，设置 `GIT_TERMINAL_PROMPT=0`，stdout 有上限，stderr 截断并脱敏，按命令区分超时。`RegistryRepo` 负责：
  - `resolve_target`：ls-remote 预检，覆盖 latest 与固定 tag。
  - `fetch`：`--depth=1` 浅拉取，并检查拉到的 commit 与预检一致。
  - `fetch_base`：尽力补拉基线 commit。
  - `read_tree`：`ls-tree -z -l` 加 `cat-file --batch`，只接受普通 blob；符号链接与子模块计为 unsupported；路径逐段校验；限额为 2 MiB / 2048 个 / 16 MiB。
- 3.1/3.2：新增 `registry_sync.py`。`RegistryLock` 模型含 `definitions` 与 `files`；本地扫描遇到链接计为 unsupported；七类三方分类；`plan.json` 与 staging 暂存；`update()` 覆盖预检、离线、`--full`，以及「有定义落后于顶层 commit 时仍进入比对」。
- 4.1/4.2：`apply()` 在 flock 下依次检查 planId（只做相等比较）、plan 与配置一致、resolve/skip 合法、本地哈希与计划一致、staging 哈希与计划一致；然后在预览树中用 `FragmentExpander` 与 `validate_profile` 校验；通过后原子写入或删除，清理空目录，最后按 D10 推进锁中的 `definitions`。
- 5.1/5.2：新增 `loopspec registry update [--full]` 与 `loopspec registry apply --plan [--resolve]... [--skip]...`；`fragment list` / `profile list` 的每个条目增加 `registry` 字段，锁损坏时为 null。
- 6.1/6.2：新增 `builtin/skills/update-registry.md`（`loopspec-update-registry`），由 init 分发，模板数从 4 变为 5。
- 7.1/7.2：中英文 `configuration.md`（registry 字段、锁文件字段与示例）、`cli-reference.md`（两个命令、list 新字段、6 个新错误码）、`agent-protocol.md`（第 8 节更新流程）；`test_docs_consistency.py` 纳入 `RegistrySpec`、`RegistryLock`、`DefinitionVersion` 与 `registry-lock` 示例。
- 8.1–8.3：全量测试、lint、手工冒烟均通过，见下文。

## 改动文件

- 第 2 轮再次修改：`src/loopspec/models.py`、`src/loopspec/registry_git.py`、`src/loopspec/registry_sync.py`、`builtin/skills/update-registry.md`、`tests/test_registry_git.py`、`tests/test_registry_sync.py`
- 新增源码：`src/loopspec/registry_git.py`、`src/loopspec/registry_sync.py`、`builtin/skills/update-registry.md`
- 修改源码：`src/loopspec/models.py`、`src/loopspec/workflow_cli.py`、`src/loopspec/workflow_planning.py`
- 新增测试：`tests/registry_helpers.py`、`tests/test_registry_config.py`、`tests/test_registry_git.py`、`tests/test_registry_sync.py`
- 修改测试：`tests/test_workflow_cli.py`、`tests/test_skill_templates.py`、`tests/test_scaffold.py`、`tests/test_cli.py`、`tests/test_builtin_resources.py`、`tests/test_docs_consistency.py`。后四个的改动只是把写死的 skill 数量从 4 改为 5，或在 skill 列表里加上 `update-registry`。
- 文档：`docs/en|zh/configuration.md`、`docs/en|zh/cli-reference.md`、`docs/en|zh/agent-protocol.md`
- 工作区配置（规划阶段，经用户告知）：`loopspec/config.yaml` 删除 1.x 的 `schema` 字段；`loopspec/fragments/{backend-tests,backend-pr-review,security-review}/fragment.yaml` 的 `evidence.paths` 与 `loopspec/fragments/change-assurance/rules.yaml` 改为本仓库的实际路径。

## 执行的检查

- 第 2 轮：
  - 新增的回归测试先跑出 9 failed、3 passed；ssh 用例收紧后单独跑为 1 failed。
  - 修复后 `tests/test_registry_*.py` 与 `tests/test_skill_templates.py` 共 138 passed。
  - `make test`：898 passed, 1 skipped in 359.86s。跳过的是 release 用例，因为 `dist/` 已按用户决定删除，与本次改动无关。
  - `make lint`：ruff 显示 All checks passed；mypy 显示 Success: no issues found in 31 source files。
- 第 1 轮：
  - 改动前的基线：`uv run pytest -q`，794 passed。
  - 新增测试先红后绿：`test_registry_config.py` 先因 ImportError 收集失败，实现后 42 passed；`test_registry_git.py` 15 passed；`test_registry_sync.py` 32 passed；`test_workflow_cli.py` 的 registry 用例先 4 failed，实现后 46 passed；skill / scaffold 用例先 3 failed，实现后 320 passed；`make docs-check` 先 8 failed，补文档后 43 passed。
  - `make test`：887 passed in 477.33s。
  - `make lint`：ruff 显示 All checks passed；mypy 显示 Success: no issues found in 31 source files。
  - 手工冒烟（scratchpad，`file://` 本地 registry，`path: workflows`）：
    - 首次 update 得到 `files` 为 0 个、`definitions` 为 16 个，apply 后生成锁文件，再次 update 返回 `upToDate: true`。
    - 上游发布 v1.1.0，同时本地修改 `bugfix.yaml`：update 得到 `upstream-modified` 与 `conflict` 各一项；不带 `--resolve` 时 apply 返回 `registry_conflict_unresolved`；带上 `--resolve =local` 和 `--skip` 后 apply 成功。
    - list 中 `qa-testing` 显示 v1.0.0（被跳过），`design` 显示 v1.1.0；再次 update 时被跳过的文件重新出现。
  - 冒烟测试发现一个缺陷：`--home` 为相对路径时 `--git-dir` 解析错误。已补回归测试 `test_relative_home`（先红），并在 `RegistryRepo` 中改用绝对路径（后绿）。

## 与设计的偏差

- D2：`run_git` 默认超时为 30 秒（ls-remote 60 秒、fetch 300 秒），与设计一致。另外追加了 `-c init.templateDir=`、`core.fsmonitor=false`，并过滤 `GIT_TEMPLATE_DIR`、`GIT_EXEC_PATH`、`GIT_ALLOW_PROTOCOL` 等环境变量，比设计更严格。
- D2：stderr 只保留最后 20 行、不超过 2000 字符，并额外把不可打印字符替换为 `?`，防止终端控制字符注入。
- D4：读树改用 `<commit>:<path>` 加 `ls-tree -l`，大小直接取自树列表，再用一次 `cat-file --batch` 批量读取，没有按文件调用 `cat-file -s`；限额不变。
- D7：apply 的写锁复用 `workflow_io.write_lock(<home>/.cache/registry)`，锁文件实际位于 `.cache/registry/plans/.write.lock`，没有另写一个锁实现。
- D7：额外校验 staging 文件的哈希必须等于计划记录的上游哈希，并要求计划中的 registry 与当前配置一致，否则返回 `registry_plan_stale`。设计中没有这两项，属于加固。
- 预览校验的范围是「本次写入涉及的定义」加「registry 管理的全部定义」，因此上游删除一个仍被引用的 Fragment 时会在写入前失败（有测试覆盖）。

- 第 2 轮：D2 中缓存的裸仓库不再跨次复用，每次 update 都会新建，代价是每次 update 都要重新浅拉取。基线内容按锁中的 tag 拉取，失败时再按 commit 拉取。

## 后续事项

- release notes 按版本组织，本次没有对应的版本号，暂未添加条目；发布时补上 registry 相关说明。
- 工作区里的 `loopspec/fragments`、`loopspec/profiles`、`.claude/` 仍未纳入版本库，`loopspec/config.yaml` 的修改也尚未提交，是否提交由用户决定。
