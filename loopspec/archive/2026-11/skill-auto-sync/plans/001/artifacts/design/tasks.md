## 1. 实现

- [x] 1.1 `scaffold.expected_files()` 与 `scaffold_tools()` 复用。验证：`tests/test_scaffold.py`。
- [x] 1.2 `skill_sync.sync_project_skills(home)`：已配置工具、项目根内文件、内容比较、fd 安全写入、skipped 记录。验证：`tests/test_skill_sync.py`。
- [x] 1.3 `HOME` 回调触发、stderr 提示、异常不影响命令。验证：单测（默认与显式 --home、hook/version/init 不触发）。
- [x] 1.4 Diff 排除内容与模板一致的 managed 普通文件。验证：`tests/test_workflow_diff.py`。

## 2. 文档与测试

- [x] 2.1 中英文 cli-reference、configuration、release-notes。验证：docs 一致性测试。
- [x] 2.2 BDD 端到端场景；全量测试与 LLM E2E 回归。验证：`make test` 等价命令、`make test-llm`。
