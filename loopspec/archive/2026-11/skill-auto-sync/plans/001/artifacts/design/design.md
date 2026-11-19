## 背景与现状

- `scaffold.scaffold_tools(project, tool_ids)`：为每个工具写 `<skills_dir>/skills/<template.name>/SKILL.md`（`generate_skill_content`），有 adapter 的工具再写 command（`adapter.get_file_path` + `adapter.format_file(generate_command_content(...))`）。`tool_is_configured()` 以「任一 loopspec SKILL.md 存在」判断工具已配置。
- `workflow_cli.HOME = typer.Option(Path("./loopspec"), "--home")`，所有工作流命令共用；`hook pre-tool-use`、`version`、`update`、`init` 不使用它。
- `workflow_diff._exclusions()` 已固定排除 `<home>/.cache` 与合法 memory topic 文件。

## 目标 / 非目标

见 proposal。

## 方案

### 1. 期望内容（`scaffold.managed_files(project) -> dict[Path, str]`）

对一个工具 id 返回其全部 loopspec 文件及应有内容：每个 `SKILL_TEMPLATES` 的 SKILL.md；有 adapter 且 `get_file_path` 落在项目根内（`resolve` 前用纯路径判断 `is_relative_to(project)`）的 command 文件。`scaffold_tools()` 改为复用它，保证 init 与同步写出的内容一致。

### 2. 同步（`skill_sync.sync_project_skills(home) -> SyncResult`）

1. `project = home.absolute().parent`；home 不是目录则返回。
2. `tools = [t for t in AI_TOOLS if tool_is_configured(project, t)]`；为空返回。
3. 对每个文件：`lstat` 目标与逐级父目录（项目根以下）——任一为符号链接或类型不符则记 `skipped` 不写；文件不存在或内容不同（按字节比较）则原子写入（同目录临时文件 + `os.replace`，`O_NOFOLLOW` 打开父目录 fd 写入）。
4. 返回 `updated`（含新建）、`skipped`（原因）。

### 3. 触发

`HOME` 增加 `callback=_sync_skills`：Typer 在解析 `--home`（含默认值）时调用；回调里 `try` 全部异常，`updated` 非空时向 stderr 打 `loopspec: synced N skill file(s) with the installed CLI (<version>): <相对路径...>`，`skipped` 非空时打告警。环境变量 `LOOPSPEC_SKILL_SYNC=0` 仅供测试隔离与紧急关闭（文档注明）。

### 4. 交付 Diff 排除

`_exclusions()` 增加：`managed = {repo 相对路径 for all tools, all managed files}`（以 home 的上一级为项目根，与同步一致）。`excluded(path)`：`path in managed` 且 `lstat` 为普通文件（或已删除）时排除；`directory=True` 时，若该目录是某个 managed skill 目录（`.../skills/loopspec-<name>`）且其中只有一个普通文件 `SKILL.md` 时排除。

### 5. 文档

中英文 `cli-reference`（全局说明：工作流命令会同步 skill，`LOOPSPEC_SKILL_SYNC`）、`configuration`（Diff 固定排除项）、`release-notes`。

## 归属与路径

BE：`src/loopspec/scaffold.py`、新增 `src/loopspec/skill_sync.py`、`src/loopspec/workflow_cli.py`、`src/loopspec/workflow_diff.py`；测试 `tests/test_skill_sync.py`（新）、`tests/test_workflow_diff.py`、BDD `tests/features/init.feature` 或新 feature；文档。

## 安全边界

- 只写 `managed_files` 计算出的固定路径，且限定在项目根内；不跟随符号链接（逐级 `lstat` + 父目录 fd 写入）；不改 hook 配置与非 loopspec 文件。
- 内容来自 CLI 内置模板，不读取项目内容决定写什么。
- Diff 排除只针对精确路径的普通文件，避免借此隐藏其它改动。

## 验证方案

单元：一致不写、不一致/缺失写入、未配置工具不写、符号链接跳过、项目外 command 路径不写、回调异常不影响命令、hook/version/init 不触发、`LOOPSPEC_SKILL_SYNC=0`；Diff：同步文件被排除、同目录其他文件与符号链接不被排除；BDD 一个端到端场景；LLM E2E 回归。

## 风险与取舍

- 内容比较而非版本号：最准确，代价是覆盖手工修改。
- 回调方式依赖 Typer 对默认值也调用 callback 的行为，由测试固定。

## 评审修订（Codex 只读审阅后，优先于上文）

1. `HOME` 回调必须返回收到的值；测试覆盖默认与显式 `--home`。
2. 项目根统一为 `home.resolve().parent`（与 `init` 默认一致）；`--project-root` 未持久化，自定义根目录的项目同步不生效，文档注明。
3. `scaffold.expected_files(project, tool)` 返回全部文件（含 Codex 全局 prompts），`scaffold_tools()` 照旧全部写入；同步时只保留项目根内的文件。
4. 写入使用 `workflow_io.atomic_write(project_root, relative, data)`：从根逐级 `O_NOFOLLOW` 打开并以目录 fd 写入，任一级是符号链接即失败并记为 skipped。
5. Diff 排除仅当工作区路径是普通文件且内容与当前 CLI 模板逐字节相同；删除、内容不同、符号链接都照常计入 Diff。
6. 不提供 `LOOPSPEC_SKILL_SYNC` 开关；测试项目默认未配置工具，同步自然不发生。
