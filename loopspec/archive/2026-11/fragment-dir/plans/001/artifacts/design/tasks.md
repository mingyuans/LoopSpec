## 1. 实现

- [x] 1.1 `ResourceBundle.location()` 与 `DefinitionBundle.location()`。
- [x] 1.2 `workflow_runtime.instructions()` 输出 `fragmentName`、`fragmentDir`、`instructionPath`、`templatePath`、`templatePaths`。
- [x] 1.3 文本渲染器 NODE 节与 INSTRUCTION 说明。

## 2. 测试

- [x] 2.1 单测：本地模式、嵌套 fragment、Gate 模板、registry 模式。
- [x] 2.2 BDD 场景。
- [ ] 2.3 `make test-llm`。

## 3. 文档与 skill

- [x] 3.1 continue skill；cli-reference、agent-protocol、release-notes（zh/en）。

## 4. 检查

- [ ] 4.1 ruff、mypy、`pytest -n 2` 全部通过。
