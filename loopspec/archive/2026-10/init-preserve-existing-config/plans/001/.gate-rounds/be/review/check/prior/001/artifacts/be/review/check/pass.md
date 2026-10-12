---
verdict: PASS
summary: "init 资源确认逻辑正确覆盖首次/已存在/交互/非交互/--json/--update-resources 各分支，与 proposal 一致，测试覆盖充分"
---

# 后端代码审查：通过

## 审查输入
轮次 `001.1:be/review/check:1`，基线 `6e17a2c`；范围：`src/loopspec/cli.py`、`src/loopspec/workflow_resources.py`、`tests/test_cli.py`。warnings: null。

## 审查要点
- 正确性：`install = update_resources or not resources_present(path)`，仅在“已存在 + 交互 + 非 JSON”时询问；`presenter is not None` 与 `as_json` 等价，沿用既有 picker 的判定方式，JSON 路径永不读 stdin。
- 边界：目录不存在/为空 → 首次安装；只有一个目录非空 → 已存在；符号链接不计为已存在，交由 `install_resources` 原有 `unsafe_path` 拒绝。EOF/空输入 → 拒绝。
- 错误处理：`install_resources` 的 `LoopspecError` 仍经 `_fail` 输出；跳过分支无新错误路径。
- 输出契约：JSON 新增 `resourcesUpdate`，`copiedWorkflowResources` 语义不变（跳过时为 `[]`）；人类输出新增一行提示，现有“无 JSON 字段名泄漏”测试通过。
- 可维护性：`RESOURCE_KINDS` 消除 `("fragments", "profiles")` 重复；注释说明意图，风格与周边一致。
- 测试覆盖：13 个新用例覆盖 AC1–AC9 及空目录场景（含参数化的 n/回车/EOF、y/YES）；文档 en/zh 同步，`docs-check` 通过。

## 剩余风险
- 交互提示在欢迎页之前出现（未带 `--tools` 的交互首屏），仅当已存在资源时发生，属可接受的展示顺序。
- 未在真实 TTY 手工验证提示渲染。
