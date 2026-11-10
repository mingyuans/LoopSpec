# language: zh-CN
@registry
功能: 用 loopspec registry update / apply 从团队注册表同步流程目录
  registry update 只读地对比本地 fragments/profiles 与远端注册表，生成一份同步计划；
  registry apply 按计划落盘，本地改动冲突必须显式裁决，同步后的条目会标明来源版本。

  场景: 未配置注册表时更新报错
    当 用户检查注册表更新
    那么 命令失败，错误码为 "registry_not_configured"

  场景: 检查更新只生成计划，不写同步锁文件
    假如 工作流 home 配置了打过 "v1.0.0" 标签的本地注册表
    当 用户检查注册表更新
    那么 命令成功
    并且 返回了同步计划编号
    并且 工作流 home 中没有 "registry.lock.yaml"

  场景: 本地改动的文件未裁决时拒绝应用，裁决保留本地后应用成功
    假如 工作流 home 配置了打过 "v1.0.0" 标签的本地注册表
    并且 本地修改了 "fragments/qa-testing/test.instruction.md"
    并且 已生成一份注册表同步计划
    当 用户应用该同步计划
    那么 命令失败，错误码为 "registry_conflict_unresolved"
    当 用户应用该同步计划并裁决 "fragments/qa-testing/test.instruction.md" 保留本地
    那么 命令成功
    并且 输出字段 "applied" 为 "true"
    并且 "fragments/qa-testing/test.instruction.md" 仍是本地修改的内容

  场景: 应用后Fragment 列表标明同步来源版本
    假如 工作流 home 配置了打过 "v1.0.0" 标签的本地注册表
    并且 已生成一份注册表同步计划
    并且 该同步计划已被应用
    当 用户列出所有 Fragment
    那么 命令成功
    并且 Fragment "design" 的注册表来源版本为 "v1.0.0"
