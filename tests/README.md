# tests 目录约定

本目录有两类测试：

- **单元测试**：`tests/test_*.py`（`test_bdd.py` 除外），直接调用实现。
- **BDD 场景**：`features/` 写行为规格，`steps/` 写步骤实现，`test_bdd.py` 负责把两者绑定。

新增或修改 BDD 场景时，按本文的规则保持一致。

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
uv run pytest tests/test_bdd.py -q             # 全部 BDD 场景
uv run pytest tests/test_bdd.py -m change -q   # 只跑某个 feature（按标签）
uv run pytest tests/test_bdd.py --co -q        # 只收集，用来检查步骤是否都有定义
make test                                      # 全量（含单元测试，耗时较长）
make lint                                      # ruff + mypy
```
