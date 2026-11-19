---
verdict: FAIL
summary: "固定 tag 改名指向同一 commit 时 update 误报 upToDate 导致项目卡死；非 registry 项目因严格加载 config 产生回归；另有来源切换预览、指令混版本、lock 体积与错误码问题"
---

# 后端代码审查：失败

## 阻塞问题

- `src/loopspec/registry_sync.py` `update()`：`registry.version` 改为指向同一 commit 的另一个 tag 时，按 commit 相等返回 `upToDate`，而 `pinned()` 要求 lock.tag 等于配置的 tag，项目所有读取都报 `registry_lock_mismatch` 且无法通过 update 修复。
- `src/loopspec/registry_store.py` `registry_spec()`：为判断是否 registry 模式而严格校验整个 `config.yaml`；非 registry 项目若保留旧字段，`fragment show`、`node instructions`、`init` 等原本不读配置的命令改为 `config_invalid`，属于回归。
- `src/loopspec/registry_sync.py` `_build_plan()`：来源切换时警告称「旧来源的定义全部列为删除」，但内容相同的文件不会出现在 `files`，预览与警告不一致，来源切换缺少结构化字段。
- `src/loopspec/workflow_runtime.py` `instructions()`：instruction、template、Gate 模板各自重新解析 lock，`apply` 恰在其间执行时一次响应可能混用两个版本。
- `src/loopspec/registry_sync.py` `_build_plan()`：未在发布计划前检查将写入的 lock 是否超出 `parse_yaml` 上限，可能生成永远无法 apply 的计划。
- `src/loopspec/registry_store.py` `read_lock()`：超过读取上限的 lock 抛 `resource_limit`，HEAD 与文档承诺为 `config_invalid`。

## 审查输入

- 轮次 `001.1:be/review/check:1`，基线 `04812daa63283f7991d1c4684958e3538b816928`。方法：人工审查 + Codex 只读独立审查（8 条）。
- 不采纳：普通项目列表新增 `source` 字段（向后兼容的新增字段，文档已说明）。
- 剩余风险：`plan approve` 与 `registry apply` 并发交错可能让新批准的 Plan 引用被删除的资源，运行时会明确报资源缺失。

## 建议修复方向

- update 快速路径同时比较 commit 与 tag（固定版本时 lock.tag 必须等于配置）。
- registry 模式探测只用有界 YAML 看是否存在 `registry` 键，存在时才严格校验。
- update 输出 `sourceChanged` 与 `previousRegistry`，修正警告文字。
- `instructions()` 用同一个 bundle 读取全部资源。
- `_build_plan()` 先用 `lock_bytes()` 校验目标 lock；`read_lock()` 把读取上限错误映射为 `config_invalid`。
