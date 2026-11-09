# language: zh-CN
@plan
功能: 用 loopspec plan 制定、确认和归档 Change 的 Plan
  plan validate 只预览编译结果，不写入任何文件；plan create 生成待人确认的草稿，
  只有拿着 plan show 展示过的摘要才能 plan approve，重复确认是幂等的；
  已确认的 Plan 不能被新建覆盖，草稿归档后新 Plan 按编号递增。

  背景:
    假如 隔离项目中有一个新建的 Change

  场景: 没有 Plan 时校验请求是只读的
    假如 已写好 "docs" 流程的 Plan 请求
    当 校验该请求
    那么 命令成功
    并且 输出字段 "mode" 为 "plan"
    并且 输出字段 "valid" 为 "true"
    并且 返回的摘要是 64 位十六进制
    并且 工作流目录中没有任何文件变化

  场景: 新建 Plan 得到草稿 001，再次新建会替换草稿
    当 用 "docs" 流程新建 Plan
    那么 命令成功
    并且 输出字段 "plan" 为 "001"
    并且 输出字段 "status" 为 "draft"
    并且 输出字段 "replacedDraft" 为 "false"
    当 用 "bugfix" 流程新建 Plan
    那么 命令成功
    并且 输出字段 "plan" 为 "001"
    并且 输出字段 "replacedDraft" 为 "true"
    并且 新草稿的摘要与上一次不同
    并且 plan show 展示的是最新草稿的摘要

  场景: 只有展示过的摘要才能批准 Plan，重复批准是幂等的
    假如 已用 "docs" 流程新建 Plan 草稿
    当 用错误的摘要批准 Plan "001"
    那么 命令失败，错误码为 "plan_changed"
    并且 Change 状态为 "planning"
    当 用 plan show 展示的摘要批准 Plan "001"
    那么 命令成功
    并且 输出字段 "revision" 为 "1"
    并且 输出字段 "status" 为 "approved"
    并且 输出字段 "alreadyApproved" 为 "false"
    并且 Change 状态为 "active"
    当 用 plan show 展示的摘要批准 Plan "001"
    那么 命令成功
    并且 输出字段 "alreadyApproved" 为 "true"
    并且 输出字段 "revision" 为 "1"

  场景: 已有确认的 Plan 时不能新建 Plan
    假如 已用 "docs" 流程新建 Plan 草稿
    并且 草稿 "001" 已按展示的摘要批准
    当 用 "docs" 流程新建 Plan
    那么 命令失败，错误码为 "plan_active"
    并且 Change 状态为 "active"

  场景: 归档草稿后新建的 Plan 编号递增
    假如 已用 "docs" 流程新建 Plan 草稿
    当 归档 Plan "001"
    那么 命令成功
    并且 输出字段 "status" 为 "archived"
    当 用 "docs" 流程新建 Plan
    那么 命令成功
    并且 输出字段 "plan" 为 "002"
    当 列出 Change 的全部 Plan
    那么 命令成功
    并且 Plan 列表依次为 "001:archived,002:draft"
