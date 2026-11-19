# language: zh-CN
@registry
功能: 用 loopspec registry update / apply 从团队注册表锁定流程目录
  registry 模式下，fragments/profiles 存放在用户级全局存储，项目只提交 registry.lock.yaml；
  registry update 只读地生成同步计划，registry apply 确认后只更新 lock；
  新 clone 按 lock 自动拉取同一版本，项目内与 registry 同名的定义直接报错。

  场景: 未配置注册表时更新报错
    当 用户检查注册表更新
    那么 命令失败，错误码为 "registry_not_configured"

  场景: 检查更新只生成计划，不写同步锁文件
    假如 工作流 home 配置了打过 "v1.0.0" 标签的本地注册表
    当 用户检查注册表更新
    那么 命令成功
    并且 返回了同步计划编号
    并且 工作流 home 中没有 "registry.lock.yaml"

  场景: 应用后项目只保留锁文件，Fragment 列表标明来源版本
    假如 工作流 home 配置了打过 "v1.0.0" 标签的本地注册表
    并且 已生成一份注册表同步计划
    并且 该同步计划已被应用
    当 用户列出所有 Fragment
    那么 命令成功
    并且 Fragment "design" 的注册表来源版本为 "v1.0.0"
    并且 工作流 home 中没有 "fragments"
    并且 工作流 home 中没有 "profiles"

  场景: 新 clone 只有锁文件时自动拉取锁定版本
    假如 工作流 home 配置了打过 "v1.0.0" 标签的本地注册表
    并且 已生成一份注册表同步计划
    并且 该同步计划已被应用
    并且 注册表全局存储被清空
    当 用户列出所有 Fragment
    那么 命令成功
    并且 Fragment "design" 的注册表来源版本为 "v1.0.0"

  场景: 进行中的 Plan 从全局存储读取节点指令
    假如 工作流 home 配置了打过 "v1.0.0" 标签的本地注册表
    并且 已生成一份注册表同步计划
    并且 该同步计划已被应用
    并且 需求 "AFD1111" 已确认一份只含需求与设计的 Plan
    当 用户获取节点 "requirements/proposal" 的指令
    那么 命令成功
    并且 返回的指令与注册表中 "fragments/requirements/proposal.instruction.md" 一致

  场景: 项目内存在与注册表同名的定义时报错，删除后恢复
    假如 工作流 home 配置了打过 "v1.0.0" 标签的本地注册表
    并且 已生成一份注册表同步计划
    并且 该同步计划已被应用
    并且 项目内保留了 Profile "bugfix" 的副本
    当 用户列出所有 Fragment
    那么 命令失败，错误码为 "registry_local_conflict"
    当 用户删除项目内的 "profiles/bugfix.yaml" 后列出所有 Fragment
    那么 命令成功

  场景: 缺少锁文件时读取定义报错
    假如 工作流 home 配置了打过 "v1.0.0" 标签的本地注册表
    当 用户列出所有 Fragment
    那么 命令失败，错误码为 "registry_not_synced"
