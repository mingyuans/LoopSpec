# language: zh-CN
@change
功能: 用 loopspec change 管理 Change 的整个生命周期
  change new 只在安全的名字下创建 Change，重复执行时复用已有 Change；
  change status / next 根据 Plan 推导出 Change 所处阶段和下一步；
  change archive 只归档已完成的 Change，未完成的 Change 必须由人明确要求强制归档。

  场景: 新建 Change 后重复执行会复用同一个 Change
    当 新建 Change "AFD1111"
    那么 命令成功
    并且 输出字段 "status" 为 "unplanned"
    并且 输出字段 "reusedChange" 为 "false"
    当 新建 Change "AFD1111"
    那么 命令成功
    并且 输出字段 "reusedChange" 为 "true"

  场景: 不安全的 Change 名被拒绝且不创建任何目录
    当 新建 Change "../x"
    那么 命令失败，错误码为 "invalid_change_name"
    并且 工作流目录下没有出现任何 Change 目录

  场景: 查询不存在的 Change 报错
    当 查询 Change "NOPE1" 的状态
    那么 命令失败，错误码为 "change_not_found"

  场景: Change 状态随 Plan 推进，change next 与状态报告给出相同的下一步
    假如 已新建 Change "AFD1111"
    当 查询 Change "AFD1111" 的状态
    那么 输出字段 "status" 为 "unplanned"
    当 用文档流程为 Change "AFD1111" 创建 Plan 草稿
    那么 命令成功
    当 查询 Change "AFD1111" 的状态
    那么 输出字段 "status" 为 "planning"
    当 用 plan show 展示的摘要批准 Plan "001"
    那么 命令成功
    当 查询 Change "AFD1111" 的状态
    那么 输出字段 "status" 为 "active"
    当 依次完成 Change "AFD1111" 文档流程的全部节点
    并且 查询 Change "AFD1111" 的状态
    那么 输出字段 "status" 为 "complete"
    并且 输出字段 "isComplete" 为 "true"
    并且 状态报告的下一步是 "loopspec change archive AFD1111"
    当 查询 Change "AFD1111" 的下一步
    那么 命令成功
    并且 change next 的下一步与最近一次状态报告一致
    当 查询 Change "AFD1111" 的历史
    那么 命令成功
    并且 输出字段 "plan" 为 "001"

  场景: 未完成的 Change 默认拒绝归档，强制归档后才移走
    假如 隔离项目中有一个已批准的文档流程 Plan
    当 归档 Change "AFD1111"
    那么 命令失败，错误码为 "archive_unsafe"
    并且 Change "AFD1111" 仍在活动目录中
    当 强制归档 Change "AFD1111"
    那么 命令成功
    并且 输出字段 "forced" 为 "true"
    并且 输出字段 "moved" 为 "true"
    并且 Change "AFD1111" 已不在活动目录中

  场景: 已完成的 Change 归档到当月目录
    假如 Change "AFD1111" 的文档流程已全部完成
    当 归档 Change "AFD1111"
    那么 命令成功
    并且 输出字段 "complete" 为 "true"
    并且 输出字段 "forced" 为 "false"
    并且 Change "AFD1111" 已移动到当月归档目录
    当 查询 Change "AFD1111" 的产物
    那么 命令成功
    并且 产物位置是当月归档目录

  场景: 同时指定 Change 名和 --all 归档会冲突
    假如 已新建 Change "AFD1111"
    当 以 Change 名 "AFD1111" 加 --all 归档
    那么 命令失败，错误码为 "option_conflict"
    并且 Change "AFD1111" 仍在活动目录中
