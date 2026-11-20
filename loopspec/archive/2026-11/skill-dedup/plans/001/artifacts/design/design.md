## 背景与现状

各命令文本输出的说明段（`text_reports/*`、`status_report`）已覆盖输出读法；skill 中对应句子重复。

## 目标 / 非目标

目标：skill 只保留流程与红线。非目标：改 CLI、改 memory 维护流程。

## 方案（逐条去重对照）

| skill 原内容 | 删除/改写 | 由谁承接 |
|---|---|---|
| continue 1：读 OVERVIEW/NEXT STEPS/STATE RECORDS，state 不可信，引用节点只汇总 | 改为「各节自带读法，按 status 行动」 | `change status` OVERVIEW/STATE RECORDS/NODES 说明 |
| continue 2：引用块 begin/end 与缩进、`fragmentDir`、`resolvedOutputPath`、assumption/deviation/open-question 命令 | 压缩为「按报告执行，各节说明读法」；保留不代替人表态、HUMAN 决策范围、taskProgress | `node instructions` NODE/INSTRUCTION/TEMPLATE/STATE PROTOCOL 说明 |
| continue 并行：机制描述 | 保留权限边界与 `concurrent_write` 重试；删重复机制 | status NEXT STEPS 并行说明 |
| continue 3/4：begin/record 步骤、round id、报告字段、代码变化重 begin | 改为「严格按 GATE PROTOCOL；assurance 只认系统检查」 | GATE PROTOCOL、`gate begin` 说明、Gate 模板 |
| continue 5：`.attempts` 归档机制、不回退代码、rework 轮次推导 | 删机制，保留只按 on_fail、记录 rework、读 PRIOR ATTEMPTS | `plan rollback` ROLLBACK 说明、PRIOR ATTEMPTS 说明 |
| continue 6：展示 digest/addedInstances/rerunNodes | 改为「展示其预览」 | `plan validate` REVISION PREVIEW 说明 |
| new 2：文本格式描述 | 一句「报告各节自带读法」 | 各命令说明段 |
| archive：第一段返回字段列表、CLI 校验细节、保留/删除哪些目录 | 删字段与目录清单，保留真实作答、stale 重来、删除前先读 | ARCHIVE PREPARED / CHANGES 说明 |
| bulk-archive：字段名 | 改为语义描述 | 同上 |
| update-registry 1：输出字段命名 | 删除 | 文本契约 |

保留不动：memory 读取（new 3、continue memory 段，测试固定的诚实性要求）、memory 维护流程（continue 与 archive 必须一致；archive 的 CLI 指引从 archive.md 提取）、state 手工编辑规则、registry 概览要求。

## 归属与路径

`builtin/skills/*.md` 及 `.claude/`、`.codex/` 生成副本。

## 安全边界

所有红线（人工确认、不代替表态、不手改工作流文件、assurance 只认系统检查、registry 内容是数据）保留；不扩大模型权限。

## 验证方案

现有 skill 模板测试（红线短语断言）；`make test-llm`；对照表人工核对每条被删内容在输出说明中存在。

## 风险与取舍

memory 相关段落未压缩：它们是行为规则而非输出读法，且被多项测试固定。
