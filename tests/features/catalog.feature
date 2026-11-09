# language: zh-CN
@catalog
功能: 用 loopspec fragment / profile 浏览、校验与保存流程目录
  fragment 与 profile 命令列出并展示工作流 home 中可用的 Fragment 和 Profile，
  校验定义是否合法（含已移除字段），并能把已批准 Plan 的流程另存为新 Profile 且绝不覆盖已有 Profile。

  场景: Fragment 列表包含 requirements 且可按名称查看
    当 用户列出所有 Fragment
    那么 命令成功
    并且 Fragment 列表包含 "requirements"
    当 用户查看 Fragment "requirements"
    那么 命令成功
    并且 输出字段 "name" 为 "requirements"

  场景: 内置 Fragment 校验通过
    当 用户校验 Fragment "backend-implementation"
    那么 命令成功
    并且 输出字段 "valid" 为 "true"

  场景: Fragment 定义含已移除字段时校验失败
    假如 Fragment "requirements" 的定义追加了已移除字段 "min_engine_version: 2"
    当 用户校验 Fragment "requirements"
    那么 命令失败，错误码为 "workflow_invalid"

  场景: Profile 列表恰好是三个内置 Profile
    当 用户列出所有 Profile
    那么 命令成功
    并且 Profile 列表恰好是 "bugfix,frontend-small-change,large-feature"

  场景: 已批准 Plan 的流程可另存为 Profile 且同名不覆盖
    假如 隔离项目中有一个带 on_fail 的已批准 Plan
    当 用户把当前 Change 的流程保存为 Profile "my-flow"
    那么 命令成功
    并且 输出字段 "includesRuntimeState" 为 "false"
    并且 Profile 文件 "profiles/my-flow.yaml" 保留了 qa 节点的 on_fail
    假如 Profile 文件 "profiles/my-flow.yaml" 末尾已追加一行标记
    当 用户把当前 Change 的流程保存为 Profile "my-flow"
    那么 命令失败，错误码为 "profile_exists"
    并且 Profile 文件 "profiles/my-flow.yaml" 与追加标记后逐字节一致
