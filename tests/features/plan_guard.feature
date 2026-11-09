# language: zh-CN
@plan_guard
功能: 用 loopspec hook pre-tool-use 守护已批准的 Plan
  AI 工具在写文件前调用此 Hook；直接改写已批准 Plan 的 plan.yaml
  或伪造一份已批准的 Plan 会被拒绝，其余操作静默放行。

  场景: 写入已批准的 plan.yaml 被拒绝
    假如 隔离项目中有一个已批准的文档流程 Plan
    当 AI 工具用 "Write" 写入已批准 Plan 的 plan.yaml
    那么 命令成功
    并且 Hook 拒绝该操作，理由提到 "plan approve"

  场景: 编辑已批准的 plan.yaml 被拒绝
    假如 隔离项目中有一个已批准的文档流程 Plan
    当 AI 工具用 "Edit" 编辑已批准 Plan 的 plan.yaml
    那么 命令成功
    并且 Hook 拒绝该操作，理由提到 "plan approve"

  场景: 非 JSON 输入、只读访问与无关路径的写入都被静默放行
    假如 隔离项目中有一个已批准的文档流程 Plan
    当 Hook 收到非 JSON 的输入
    那么 Hook 静默放行
    当 AI 工具用 "Read" 读取已批准 Plan 的 plan.yaml
    那么 Hook 静默放行
    当 AI 工具用 "Write" 写入 "src/x.py"
    那么 Hook 静默放行

  场景: 草稿 Plan 可以被编辑
    假如 隔离项目中有一个草稿状态的文档流程 Plan
    当 AI 工具用 "Edit" 编辑草稿 Plan 的 plan.yaml
    那么 Hook 静默放行

  场景: Bash 原地修改已批准的 plan.yaml 被拒绝，只读命令放行
    假如 隔离项目中有一个已批准的文档流程 Plan
    当 AI 工具执行 Bash 命令 "sed -i '' s/a/b/" 作用于已批准 Plan 的 plan.yaml
    那么 Hook 拒绝该操作，理由提到 "plan approve"
    当 AI 工具执行 Bash 命令 "cat" 作用于已批准 Plan 的 plan.yaml
    那么 Hook 静默放行

  场景: 新建一份状态为 approved 的 plan.yaml 被拒绝
    假如 隔离项目中有一个已批准的文档流程 Plan
    当 AI 工具用 "Write" 新建 Plan "002" 的 plan.yaml，内容状态为 "approved"
    那么 Hook 拒绝该操作，理由提到 "only loopspec plan approve"
