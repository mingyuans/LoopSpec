---
verdict: PASS
summary: "新增字段只是由已批准 Plan 节点定义推出的绝对路径，先经 bundle.read 校验；无新增读写或用户输入路径"
---

# 后端安全审查：通过

## 审查输入

- 轮次 `001.1:be/security/check:1`；审查 `workflow_io.ResourceBundle.location`、`registry_store.DefinitionBundle.location`、`workflow_runtime.fragment_paths`、文本渲染器与 skill 改动。

## 检查项与结论

- **路径来源**：路径只来自已编译、已批准 Plan 的节点定义（`instruction`/`template`/Gate 模板），且在 `instructions()` 中已先经 `bundle.read()`（`relative_path` 拒绝绝对路径与 `..`；registry 文件核对 lock 哈希）后才计算位置；没有接收命令行或文件内容中的路径。
- **registry 位置**：registry 定义指向 `snapshot.resolve()`（快照由 `_private_dir` 逐级 O_NOFOLLOW 建立、物化时完整校验）；本地定义指向 `home.resolve()`。
- **输出**：只增加路径字符串；文本模式经 `sanitize`；不新增文件写入、网络或子进程。
- **skill 指引**：让模型按 `fragmentDir` 读取辅助文件，读取内容仍是 fragment 定义内容，未改变其可信级别。

## 剩余风险

- 模型直接读快照文件时不经过 CLI 的逐文件哈希校验；快照位于用户私有目录且物化时已校验。快照只读化可另行处理。
- 输出暴露本机绝对路径，与已有 `resolvedOutputPath` 同类，仅在本机 CLI 输出中。
