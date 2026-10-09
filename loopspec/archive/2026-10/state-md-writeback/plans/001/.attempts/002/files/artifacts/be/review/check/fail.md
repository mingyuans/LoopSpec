---
verdict: FAIL
summary: "代码部分无阻塞问题，但 new.md 插入新步骤后 continue.md 仍引用 loopspec-new 的 steps 3-8，重新规划会漏掉第 9 步批准"
---

# 后端代码审查：失败

## 阻塞问题

- `builtin/skills/continue.md` 第 11 行（`unplanned` 分支）与第 19 行（步骤 7 替换 Plan）：仍写 "plan the whole task with the `loopspec-new` skill (steps 3-8)"。本次在 `builtin/skills/new.md` 插入新的第 3 步（填写 `state.md`），原步骤 3–8 顺延为 4–9，规划的完整范围现在是 steps 3-9；按 3-8 执行会漏掉第 9 步"人确认后 plan approve"。需改为 steps 3-9，并同步 `.claude/skills/loopspec-continue/SKILL.md`；建议补一个测试，校验 `continue` 引用的 `new` 步骤区间与 `new.md` 中 approve 步骤编号一致。

## 审查输入

- 轮次：`001.1:be/review/check:1`；基线 `ac4ff4fe7213e03f2c1e717c5190ef583f216a15`；scopeDigest `8a7f4073…`；warnings：无。
- 证据范围：`src/loopspec/{status_report,workflow_journal,workflow_changes,workflow_cli,workflow_io,workflow_plans}.py` 及对应测试；另按设计"归属与路径"人工核对了被 `excluded_paths` 排除的 `builtin/skills/*.md` 与 `docs/**`，上述阻塞问题即来自该部分。

代码部分审查结论（不阻塞）：

- 正确性：五个命令的事件均在提交点之后追加，失败路径、`alreadyApproved`、重复 archive 不追加；`status()` 四个分支都带 `state` / `planState` / `untrustedData`，`planState` 取 `openPlan`；`run()` 仅 `change status` 使用文本渲染，退出码不变。
- 边界：空内容、末尾无换行、`\r\n`、非 UTF-8、截断、缺失 / 不可读 / 硬链接均有用例；`_nodes()` 仅在 `nodes` 非空时调用。
- 错误处理：`record()` 与 `state_view()` 吞掉 IO 异常并以 `warnings` / `error: "unreadable"` 显式呈现，不掩盖命令结果。
- 可维护性：渲染器只读 payload，键集合常量供覆盖测试使用。
- 测试覆盖：T1–T23 与硬链接用例齐全；glob 产物节点的续行渲染没有真实 payload 用例（内置 Fragment 无 glob 产物），见下。

## 建议修复方向

- 修正两处步骤区间并同步已安装副本；在 `tests/test_skill_templates.py` 增加区间一致性断言。
- 可顺带为 `status_report` 的 glob 续行补一个以构造 payload 直接调用 `render_status_report()` 的单元用例。
