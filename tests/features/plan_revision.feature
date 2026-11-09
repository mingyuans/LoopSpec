# language: zh-CN
@plan_revision
功能: 用 plan validate/approve -f 修订 Plan，用 plan rollback 返工
  已批准的 Plan 可以基于当前修订号原地修订：先只读预览，再凭预览摘要确认，过期请求被拒绝；
  Gate 判定失败后按它自己的 on_fail 回滚，并在 change history 中留下记录。

  场景: 预览修订是只读的并列出新增实例
    假如 已批准的文档流程 Plan 中 requirements 节点已完成
    当 以基准修订号 "1" 预览新增 "notes" 实例的修订
    那么 命令成功
    并且 输出字段 "mode" 为 "revision"
    并且 输出字段 "revision" 为 "2"
    并且 新增实例列表为 "notes"
    并且 工作流目录中没有任何文件变化
    并且 Plan 当前修订号为 "1"

  场景: 凭预览摘要确认修订后修订号变为 2
    假如 已批准的文档流程 Plan 中 requirements 节点已完成
    并且 已以基准修订号 "1" 预览新增 "notes" 实例的修订
    当 凭预览摘要确认该修订
    那么 命令成功
    并且 输出字段 "revision" 为 "2"
    并且 Plan 当前修订号为 "2"
    并且 节点 "requirements/proposal" 状态为 "done"
    并且 节点 "notes/proposal" 状态为 "ready"

  场景: 基于过期修订号的修订请求被拒绝
    假如 已批准的文档流程 Plan 中 requirements 节点已完成
    当 以基准修订号 "2" 预览新增 "notes" 实例的修订
    那么 命令失败，错误码为 "stale_revision"
    并且 Plan 当前修订号为 "1"

  场景: 没有失败的 Gate 时不能回滚
    假如 隔离项目中有一个已批准的缺陷修复 Plan
    当 回滚 Plan "001"
    那么 命令失败，错误码为 "no_failed_gate"

  场景: 失败的 Gate 按自身 on_fail 回滚并记入历史
    假如 隔离项目中有一个已批准的缺陷修复 Plan
    并且 后端代码已修改且 "qa/test" Gate 判定失败
    当 回滚 Plan "001"
    那么 命令成功
    并且 输出字段 "gate" 为 "qa/test"
    并且 重置范围包含 "be/code/implement"
    并且 重置范围包含 "be/tests/check"
    并且 重置范围包含 "qa/test"
    并且 节点 "be/code/implement" 状态为 "ready"
    并且 节点 "qa/test" 状态为 "blocked"
    当 查看 Change 历史
    那么 命令成功
    并且 历史中只有一条针对 "qa/test" 的 "rollback" 记录

  场景: 返工次数用尽后回滚被拒绝
    假如 隔离项目中有一个最多返工一次的 QA Plan
    并且 "qa/test" Gate 判定失败并已回滚一次
    并且 requirements 节点重做后 "qa/test" Gate 再次判定失败
    那么 节点 "qa/test" 状态为 "exhausted"
    当 回滚 Plan "001"
    那么 命令失败，错误码为 "retries_exhausted"
