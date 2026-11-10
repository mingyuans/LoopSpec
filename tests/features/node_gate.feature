# language: zh-CN
@node_gate
功能: 用 node instructions 与 gate begin/record 执行节点并提交 Gate 结论
  node instructions 只为活动 Plan 中可执行的叶子节点返回指令与产物路径；
  代码 Gate 必须先 gate begin 固定审查范围，再凭轮次编号和报告 gate record；
  保障节点由系统检查、不接受报告，全部通过后 Change 完成。

  场景: 引用节点不能直接执行
    假如 隔离项目中有一个已批准的缺陷修复 Plan
    当 获取节点 "requirements" 的执行指令
    那么 命令失败，错误码为 "reference_not_executable"

  场景: 只有草稿 Plan 时没有可执行节点
    假如 隔离项目中只有一个草稿状态的缺陷修复 Plan
    当 获取节点 "requirements/proposal" 的执行指令
    那么 命令失败，错误码为 "plan_not_active"

  场景: 就绪叶子节点返回指令与解析后的产物路径
    假如 隔离项目中有一个已批准的缺陷修复 Plan
    当 获取节点 "requirements/proposal" 的执行指令
    那么 命令成功
    并且 输出字段 "status" 为 "ready"
    并且 返回非空的执行指令
    并且 解析后的产物路径为活动 Plan 目录下的 "artifacts/requirements/proposal.md"

  场景: 代码 Gate 先 begin 再凭轮次与报告记录 PASS
    假如 隔离项目中有一个已批准的缺陷修复 Plan
    并且 后端代码已修改且流程推进到 "be/tests/check"
    当 不带轮次与报告记录 Gate "be/tests/check"
    那么 命令失败，错误码为 "option_required"
    当 开始 Gate "be/tests/check" 的审查轮次
    那么 命令成功
    并且 返回了审查轮次编号
    当 写入结论为 "PASS" 的报告 "artifacts/reports/be-tests.yaml" 并以该轮次记录 Gate "be/tests/check"
    那么 命令成功
    并且 输出字段 "verdict" 为 "PASS"
    并且 输出字段 "evidenceRecorded" 为 "true"
    并且 节点 "be/tests/check" 状态为 "done"

  场景: 保障节点不接受报告，全部通过后 Change 完成
    假如 隔离项目中有一个已批准的缺陷修复 Plan
    并且 后端代码已修改且流程推进到 "assurance/check"
    当 带报告记录 Gate "assurance/check"
    那么 命令失败，错误码为 "option_conflict"
    当 不带轮次与报告记录 Gate "assurance/check"
    那么 命令成功
    并且 输出字段 "verdict" 为 "PASS"
    并且 输出字段 "recorded" 为 "true"
    并且 Change 已完成
