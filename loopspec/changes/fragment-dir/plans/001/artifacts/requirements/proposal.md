## 背景

registry 模式下，fragment 定义只存在于全局快照（`$LOOPSPEC_REGISTRY_STORE/<来源>/<commit>/fragments/<name>/`），项目里没有 `loopspec/fragments/`。fragment 指令会引用同一目录下的辅助文件：`references/*.md`、`scripts/*`，或只写文件名（如 `qa-testcases` 的 clarify 指令引用 `doc-writing-rules.md` §0、`case-writing-rules.md` §4）。`node instructions` 只返回指令正文；`fragment` 字段是 Plan 里的实例 id（如 `qa`），不是 fragment 名，也没有任何字段给出 fragment 目录，模型因此找不到这些文件。实测 aftership-channels 锁定的快照 7b6cc1b 中有 42 个文件、83 处这类引用。

用户决定（2026-11-20）：在 node 命令里带上 fragment 的绝对路径。

## 用户场景

- MODEL 执行 `loopspec node instructions -c <change> -n <node>`，从输出读到 `fragmentDir`，把指令里的 `references/x.md`、`scripts/y.sh`、`doc-writing-rules.md` 按 `fragmentDir` 解析后读取或执行。
- 本地模式（fragment 在项目里）同样给出 `fragmentDir`，行为一致。

## 范围

1. `node instructions` 的 payload（`--json` 与文本报告）新增：
   - `fragmentName`：节点定义所在的 fragment 名（嵌套 fragment 时为实际定义节点的那个，例如 `be/code/implement` 为 `backend-code`）。
   - `fragmentDir`：该 fragment 目录的绝对路径；registry 定义指向已校验的快照目录，本地定义指向 workflow home 下的 `fragments/<name>`。
   - `instructionPath`、`templatePath`：节点指令、模板文件的绝对路径（没有时不输出）；Gate 节点的 pass/fail 模板绝对路径放在 `templatePaths`。
2. 文本报告 NODE 节显示上述字段；INSTRUCTION 节说明写明「指令中的相对路径与只写文件名的引用相对 fragmentDir」。
3. `continue` skill 与 `docs/{zh,en}`（cli-reference、agent-protocol、release-notes）同步说明。

## 非目标

- 不改写指令文本中的路径前缀，不提供旧路径映射表。
- 不修改上游 registry 内容（如缺失的 `fragments/README.md` §4）。
- 不改变快照文件的权限（只读化另行讨论）。
- `fragment` 字段语义不变（仍为实例 id）。

## 验收条件

- [ ] registry 模式项目：`node instructions --json` 返回的 `fragmentDir` 是快照中存在的目录，`fragmentName` 等于节点定义所在 fragment；`instructionPath`、`templatePath` 存在且内容与 `instruction`、`template` 字段逐字节相同。
- [ ] 本地模式：`fragmentDir` 为 `<home 绝对路径>/fragments/<name>` 且存在。
- [ ] 嵌套 fragment（如 bugfix 流程中的 `be/code/implement`）的 `fragmentName` 为 `backend-code`。
- [ ] Gate 节点给出 `templatePaths.pass/fail`，分别与 `templates.pass/fail` 内容一致。
- [ ] 文本报告中 `fragmentDir:`、`fragmentName:`、`instructionPath:` 以 `key: value` 行出现，INSTRUCTION 节说明提到 fragmentDir。
- [ ] 原有字段与 JSON 结构不变（只新增键）；全部测试、`make test-llm` 通过。

## 风险

- 模型直接读取快照文件，不再经过 CLI 的逐文件哈希校验；快照在物化时已校验、存于用户私有目录。记录为剩余风险。
- 暴露本机绝对路径：只在本机 CLI 输出中出现，与 `resolvedOutputPath` 同类。
