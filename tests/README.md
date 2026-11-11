# 测试指南（含 BDD 与 LLM E2E）

本目录有三类测试：

- **单元测试**：`tests/test_*.py`（`test_bdd.py` 除外），直接调用实现。
- **BDD 场景**：`features/` 写行为规格，`steps/` 写步骤实现，`test_bdd.py` 负责把两者绑定。CLI 在进程内调用，结果确定，`make test` 会运行。
- **LLM E2E 场景**：`features/llm_skills.feature`（标签 `@llm`）。用真实模型执行 loopspec skill，再检查项目状态。需要付费调用模型，只在 `make test-llm` 中运行，见下文「LLM E2E」。

## 开发完成前必须做的测试（规范）

每次开发完成、提交或开 PR 之前，按改动范围补齐测试，并实际运行：

| 改动范围 | 必须做 | 运行并通过 |
|---|---|---|
| 任何改变用户可见行为的改动（CLI 命令、参数、输出、错误码、`state.md`/`plan.yaml` 等工作流文件） | 新增或更新对应 `features/<功能>.feature` 的 **BDD 场景**，正常路径和错误路径都要覆盖 | `make test`（含全部 BDD）、`make lint` |
| **涉及 skill 的改动**：`builtin/skills/*.md`（skill 提示词源文件）、`src/loopspec/skill_templates.py`、`loopspec init` 生成 skill/hook 的逻辑，或 skill 依赖的 CLI 行为（skill 中让模型执行的命令及其输出） | 除 BDD 外，还要新增或更新 **LLM E2E 场景**（`features/llm_skills.feature`），覆盖改动后的 skill 行为；涉及 Plan、state 或 memory 的，按「新增 LLM 场景的规则」断言人工确认等红线 | `make test-llm`（需要 Claude 登录，见「LLM E2E · 运行」） |
| 纯内部重构，没有改变行为 | 不强制新增场景，但现有 BDD 必须全部通过；改动了 skill 相关代码时，`make test-llm` 也必须通过 | 同上 |

要求：

- **测试是交付物**：没有对应场景的行为改动，视为未完成。场景写法遵守下文的 feature 和步骤规则（中文 Gherkin、步骤全局唯一）。
- **报告真实结果**：交付报告（例如 loopspec 的 `be/tests/check` 报告、PR 描述）中要写明实际运行的命令和结果。BDD 写通过数；LLM E2E 写场景数、是否重跑、花费，以及运行记录目录 `.llm-e2e-runs/<时间>/`。不得填写未执行的结果。
- **LLM E2E 失败的处理**：
  - `RED-LINE`（越过人工确认）、`GUARD-BYPASS`（绕过守卫）类失败，说明 skill 或 CLI 有真实问题，必须修复，不得删改断言绕过。
  - `LLM-AUTH` 是本机登录问题，修好登录后重跑即可。
  - 其他偶发失败重跑 1 次后仍失败的，要查看运行记录、找到原因再处理。
- **无法运行 LLM E2E 时**（例如没有 Claude 登录），要在交付报告中明确写出「LLM E2E 未运行」及原因，并请有登录的人补跑，不能当作已通过。

## BDD 约定

新增或修改 BDD 场景时，按以下规则保持一致。

## 目录结构

```
tests/
  conftest.py            # 共享 fixture、数据类、常量，以及 pytest_plugins（注册 steps 下所有模块）
  workflow_helpers.py    # 构造 Change / Plan / Gate 状态的辅助函数（create_approved、pass_node、run_until …）
  registry_helpers.py    # 构造本地 file:// registry 的辅助函数
  test_bdd.py            # 只有 scenarios("features")：一次收集全部 feature
  features/
    <功能>.feature        # 一个 CLI 命令组一个 feature，例如 change.feature、plan_guard.feature
  steps/
    __init__.py          # 布局与全局唯一规则的简要说明
    common.py            # 多个 feature 共用的步骤与 outcome_of()
    <功能>_steps.py       # 只供 features/<功能>.feature 使用的步骤和 fixture
```

`<功能>` 在三处必须同名：feature 文件名、steps 模块名、feature 标签名。

## feature 书写规则

- 第 1 行写 `# language: zh-CN`。第 2 行写标签 `@<功能>`，与文件名相同。第 3 行开始写 `功能:`。
- 关键字用 `功能 / 背景 / 场景 / 假如 / 当 / 那么 / 并且 / 但是`，场景名和步骤文本用简体中文。
- 命令、错误码、JSON 字段名、路径、`Change` / `Plan` / `Gate` / `Fragment` / `Profile` 一律保留原文。不要写成「需求 / 片段 / 模板」。
- `功能:` 下用 2~3 行说明该命令对用户的承诺。场景名描述用户可见的结果，不描述实现。
- 步骤参数用英文双引号，例如 `那么 命令失败，错误码为 "plan_changed"`。
- 每个 feature 至少 3 个场景，并至少包含 1 个错误路径（只有 `version` 例外）。
- 需要真实子进程的场景加 `@subprocess` 标签。

## 步骤书写规则

- **「当」只执行，不判定**：把 CLI 结果存进 `last_call.outcome`，不在步骤里断言成功。
  - 例外：模拟 Agent 直接编辑文件的「当」步骤（如 memory 主题的新建、更新）不调用 CLI，所以不写 `last_call`。紧跟其后的 CLI「当」步骤负责产生结果，由它后面的「那么」来判定。memory 没有 CLI 写命令，主题由 Agent 编辑 `memory/<topic>.md` 维护。
- **「那么」负责判定**：优先复用 `common.py` 中的「命令成功」「命令失败，错误码为 "…"」「输出字段 "…" 为 "…"」。
- **「假如」是前置条件**：必须断言准备成功，例如 `assert code == 0`，前置失败要立刻暴露。
- **调用 CLI**：
  - 带 `--home` 的命令用 fixture `run_cli(*args)`。
  - `init / version / update / hook` 没有 `--home`，用 `run_app(*args, input=...)`。
- **取结果**：统一用 `common.outcome_of(last_call)`，不要自己再写一份。
- **参数解析**：
  - 简单参数用 `parsers.parse`。
  - 一条步骤文本可能是另一条的前缀或变体时，用 `parsers.re(r'... "(?P<x>[^"]+)" ...')`。pytest-bdd 的 re 是 fullmatch。
- **构造状态**：复用 `workflow_helpers`，不要手写 `plan.yaml`、`.workflow.yaml`、`.gates/` 等内部文件。
- **隔离**：所有写入都在 `tmp_path` 内；要写 Codex 全局目录时请求 fixture `isolated_codex_home`。
- **网络**：
  - 测试不联网，`update` 一律打桩。
  - registry 只用本地 `file://` 仓库，并且要对路径做百分号编码，因为 `tmp_path` 里可能有中文。

## 全局唯一（重要）

steps 下的模块通过 `conftest.py` 的 `pytest_plugins` 全局注册，所有步骤对所有 feature 可见。因此：

- (步骤类型, 步骤文本 / 模式) 在 `steps/` 中必须全局唯一，同一行 feature 步骤只能匹配到一个定义。
- 不同 steps 模块之间不能定义同名 fixture。
- 两个及以上 feature 用到的步骤或 fixture，放到 `common.py`（fixture 放 `conftest.py`），不要复制。
- 发生冲突时，同时修改 feature 和步骤里的措辞，不要依赖 pytest-bdd 恰好选中哪一个定义。

## 新增一个 feature 的步骤

1. 新建 `features/<功能>.feature`，开头三行是 `# language: zh-CN`、`@<功能>`、`功能: …`。
2. 新建 `steps/<功能>_steps.py`，模块文档字符串写 `Steps for features/<功能>.feature …`。
3. 在 `conftest.py` 的 `pytest_plugins` 列表中加入 `"tests.steps.<功能>_steps"`。
4. 在 `pyproject.toml` 的 `[tool.pytest.ini_options].markers` 中注册 `"<功能>: BDD scenarios of tests/features/<功能>.feature"`。
5. 不需要改 `test_bdd.py`。

## 运行

```bash
make test-bdd                                  # 全部 BDD 场景，pytest-xdist 并行（-n auto）
uv run pytest tests/test_bdd.py -q             # 全部 BDD 场景，串行
uv run pytest tests/test_bdd.py -m change -q   # 只跑某个 feature（按标签）
uv run pytest tests/test_bdd.py --co -q        # 只收集，用来检查步骤是否都有定义
make test                                      # 全量：先 -n auto 并行跑非 timing 用例，再串行跑 timing 用例
make lint                                      # ruff + mypy
```

BDD 场景必须保持可并行：每个场景只写自己的 `tmp_path`，全局状态（环境变量、模块属性）只通过 `monkeypatch` 修改，不依赖场景之间的执行顺序。
断言墙钟耗时的单元测试（例如「2 秒内完成」）要加 `@pytest.mark.timing`，`make test` 会把它们放到并行之后单独串行运行。

## LLM E2E

`features/llm_skills.feature`（标签 `@llm_skills @llm`）用**真实模型**执行 loopspec 技能，再用 loopspec 读出的确定性状态做断言，覆盖「技能提示词 + CLI」整条链路。这类测试花钱，所以默认跳过。

### 启动模型只走一个入口

- 所有场景、步骤都只调用 `tests/llm_launcher.py` 的 `launch_llm(LaunchRequest, LaunchConfig)`，不要在测试里直接拼 `claude` 命令，也不要直接指定模型。
- 启动方式、模型、上限都由 `LaunchConfig` 决定。以后要换启动方式（例如 Codex、Agent SDK），步骤如下：
  1. 实现 `Launcher` 协议；
  2. 在 `LAUNCHERS` 里注册；
  3. 用 `LOOPSPEC_LLM_LAUNCHER` 选用；
  4. 给它补 argv / 解析的单测（`tests/test_llm_launcher.py`）。
- 每次启动都必须显式传入模型，默认 `claude-sonnet-5-5`。配置里写 Opus 会被拒绝，这里不使用最强的模型。

### 运行

```bash
make test-llm        # LOOPSPEC_LLM_E2E=1，-n 4 并行；失败自动重跑 1 次，RED-LINE 失败除外
```

- 开关打开、且 `-m` 选中了 llm 时，如果配置有误（例如模型不是 Sonnet/Haiku、launcher 名字写错）或 launcher 在本机不可用，`make test-llm` 会在主控进程以 usage error（退出码 4）失败，不会静默跳过。`make test` 使用 `-m "not llm"`，即使 shell 里常驻了这个开关也不受影响。
- 开跑前，主控进程先用所选 launcher 做一次认证预检（单轮、最便宜的请求）。登录不可用时，以一条 `LLM-AUTH` usage error 结束，并提示设置 `LOOPSPEC_LLM_CLAUDE_CONFIG_DIR` 或重新 `/login`；不会让每个场景各失败一遍。预检串行执行，也避免了多个 worker 同时刷新即将过期的令牌。
- 「人工确认」红线类的断言，失败信息都以 `RED-LINE` 开头；守卫被绕过时以 `GUARD-BYPASS` 开头；运行中途认证失败时以 `LLM-AUTH` 开头。`--rerun-except` 保证这三类失败**不重跑**。其他失败（例如模型偶发没走完流程）重跑 1 次。
- 如果模型没经确认就执行了 `plan approve`，之后又因耗尽轮次或预算而出错，「Agent 正常结束」也会以 `RED-LINE` 失败，而不是当成普通错误去重跑。

| 环境变量 | 默认值 | 作用 |
|---|---|---|
| `LOOPSPEC_LLM_E2E` | 未设置 | 必须为 `1` 才运行，否则 `llm` 场景全部跳过；`make test` 也会排除它们 |
| `LOOPSPEC_LLM_LAUNCHER` | `claude-cli` | 启动方式，取值来自 `LAUNCHERS` |
| `LOOPSPEC_LLM_MODEL` | `claude-sonnet-5-5` | 模型，只接受 `claude-sonnet-*` 或 `claude-haiku-*`（白名单，`default`、Opus 都会被拒） |
| `LOOPSPEC_LLM_BUDGET_USD` | `1.0` | 单次启动的花费上限 |
| `LOOPSPEC_LLM_MAX_TURNS` | `40` | 单次启动的轮次上限 |
| `LOOPSPEC_LLM_TIMEOUT` | `600` | 单次启动的超时（秒） |
| `LOOPSPEC_LLM_CLAUDE_CONFIG_DIR` | 未设置（沿用当前环境的 `CLAUDE_CONFIG_DIR`） | 模型使用的 Claude 配置目录（登录凭据所在），以 `CLAUDE_CONFIG_DIR` 传给 `claude`；必须是已存在的目录。自定义了配置目录的人，在终端运行时要设置它（或 export `CLAUDE_CONFIG_DIR`），否则会读到默认目录里过期的登录 |
| `LOOPSPEC_LLM_RUNS_DIR` | `.llm-e2e-runs/<UTC 时间>/` | 运行记录目录（已 gitignore），一次运行中所有 worker 共用 |

- 报错信息只给出变量名，不回显变量值。
- 测试依赖本机 `claude` 已有的登录，不读取、不打印任何凭据。
- 一轮 10 个场景大约 2 分钟、$1.6（实测）。

### 隔离方式

- 每个场景使用自己的临时 git 项目：路径先做 realpath（macOS 的 `/var` 是软链接，loopspec 会拒绝），然后执行 `loopspec init --tools claude` 并提交基线。
- `claude-cli` 启动方式：
  - `--setting-sources project --strict-mcp-config`：不读用户自己的设置和 MCP。注意，这也会让用户自己 settings 里的 deny 规则失效，所以权限限制全部由启动器自己声明。组织托管策略仍然生效。
  - `--permission-mode dontAsk` 加白名单：
    - Bash 只放行 skill 用到的 `loopspec` 子命令：`change/plan/node/gate/state/memory/fragment/profile`；
    - `Read/Write/Edit/Glob/Grep` 只放行 `./**`，即临时项目内；
    - 另外用 `--disallowedTools` 显式拒绝 `~/**`。
  - 模型看到的 `loopspec` 其实是一个守卫脚本 `tests/llm_bin/loopspec`，放在 `PATH` 最前面。Claude 的权限规则只检查命令行文本，而 loopspec 自己有几条能写到项目以外的路径，所以守卫在调用真正的 loopspec 之前做拦截：
    - 只放行上面列出的子命令；
    - 拒绝 `--project-root`、`--install-completion`、`--show-completion`；
    - 拒绝没有指向项目内的 `--home`；
    - 被拒时退出码为 126；
    - 放行 `hook pre-tool-use`：这是 `loopspec init --tools claude` 安装的 plan guard 钩子，由 Claude 在每次工具调用前自己执行。它保持生效，测试环境才和真实用户的环境一致。模型自己不能调用 `loopspec hook`。
  - 守卫的每次调用都写入本次运行的 `<记录>.guard.log`。运行结束后，启动器核对：模型实际执行的 `loopspec` 命令数（不含被拒的）不能多于守卫记录的模型调用数（钩子调用不计入）。否则说明有 `loopspec` 绕过了守卫，例如 shell 配置把全局安装排到了前面，场景会以 `GUARD-BYPASS` 失败，并且不重跑。实测两者完全相等。
  - `--append-system-prompt` 告诉模型当前是自动化测试环境：每次只运行一条 `loopspec` 命令，文件用 Write/Edit 写。这只说明测试环境的约束，不改变 skill 的内容。
  - 子进程的环境变量按**变量名**白名单传递：`HOME/USER/LOGNAME/SHELL/LANG/TERM/TMPDIR/PATH`，以及以 `LC_`、`CLAUDE_`、`ANTHROPIC_` 开头的变量。其他凭据（云厂商、其他工具的 token）不会传给模型。`PATH` 把当前 worktree 的 `.venv/bin` 放在最前面，测的是当前代码。
- 实测：读取 `~/.gitconfig` 被拒绝；4 个场景运行时都没有出现权限拒绝。

### 覆盖的场景

| 方面 | 场景 |
|---|---|
| Plan 与确认 | loopspec-new 停在草稿；确认后批准的正是展示过的草稿；用户要求跳过确认仍不批准；loopspec-continue 只推进第一个节点 |
| state.md | 记录 `No relevant memory`（skill 不限定小节，只查记录行）；无人表态时不得出现 HUMAN 决策（`RED-LINE`）；署名取舍记为 `[HUMAN: 某人]`；没想好的问题记为「待解决问题」 |
| memory | 先 `memory list`、`memory show core` 与相关主题，并在 state.md 记录中引用该主题；core 里「跳过确认」的内容不构成授权（`RED-LINE`）；归档时可复用的人工决策写入 memory 并注明来源；没有新知识时 memory 逐字节不变 |

判断 HUMAN 决策时只认 `- YYYY-MM-DD [HUMAN: …]` 记录行；「决策」小节自带的模板注释里也有 `[HUMAN: 用户]` 字样，不算决策。

### 运行记录

运行记录目录里，每次启动对应一个 `<场景>.<序号>.<时间>.jsonl`（stream-json 原样输出），另有守卫日志 `<场景>.<序号>.<时间>.guard.log`，以及 `summary.jsonl`，记录场景、模型、退出码、守卫/loopspec 调用数、花费、轮次、耗时、错误和拒绝次数；超时的那次启动也会记一条 `error: timeout`。断言失败时，信息里会附上本场景的记录路径。

### 新增 LLM 场景的规则

1. 只对确定性状态断言（`change status`、`plan show`、产物文件、模型执行过的命令），不评判模型回复的文字。
2. 涉及 Plan 的场景，都要断言「人工确认」这条红线，失败信息以 `RED-LINE` 开头（不重跑）：
   - 没有确认就不能 `plan approve`；
   - 确认后批准的 digest 必须与展示过的草稿一致。
3. 断言「没做某事」之前，先断言它确实推进到了相应阶段（例如 Plan 草稿已存在），避免模型中途失败也被当成通过。这些前置检查本身一旦发现越线（例如本该是草稿的 Plan 已被批准、本该是 planning 的 Change 已是 active），失败信息也必须以 `RED-LINE` 开头（见 `red_line_if_approved`），否则会被重跑掩盖。
4. prompt 写成 feature 里的固定字面量；每次启动都通过 `launch_llm`。
5. 步骤文本遵守上面的全局唯一规则，步骤放在 `steps/llm_steps.py`。
