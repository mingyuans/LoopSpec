# language: zh-CN
@init
功能: 用 loopspec init 初始化工作流目录
  命令创建配置、记忆目录与内置的 Fragment/Profile；重复执行不会覆盖用户的定制，
  并可按需为 AI 工具在项目根目录生成技能与 Hook；生成的技能写明 Agent 何时、如何维护 memory。

  背景:
    假如 一个尚未初始化的项目目录

  场景: 首次初始化安装配置与内置资源
    当 用户以 JSON 模式初始化工作流目录
    那么 命令成功
    并且 输出字段 "resourcesUpdate" 为 "installed"
    并且 工作流目录中有 config.yaml 和空的 memory 目录
    并且 工作流目录中有内置的 Fragment 与 Profile

  场景: 重复初始化默认跳过已有资源
    假如 工作流目录已初始化，且删除了 Profile "bugfix"
    当 用户以 JSON 模式初始化工作流目录
    那么 命令成功
    并且 输出字段 "resourcesUpdate" 为 "skipped"
    并且 Profile "bugfix" 仍不存在

  场景: 指定 --update-resources 只补回缺失资源而不覆盖定制
    假如 工作流目录已初始化，且删除了 Profile "bugfix"
    并且 Profile "large-feature" 已被用户定制
    当 用户以 JSON 模式初始化工作流目录并更新资源
    那么 命令成功
    并且 输出字段 "resourcesUpdate" 为 "installed"
    并且 本次只复制了 "profiles/bugfix.yaml"
    并且 Profile "large-feature" 保持用户定制的内容

  场景: 为 claude 在项目根目录生成技能与 Hook
    当 用户以 JSON 模式初始化工作流目录并配置工具 "claude"
    那么 命令成功
    并且 项目根目录下有 ".claude/skills/loopspec-new/SKILL.md"
    并且 工作流目录内没有 ".claude"
    并且 "claude" 的 Hook 状态为 "created"

  场景: 未知的工具名被拒绝
    当 用户以 JSON 模式初始化工作流目录并配置工具 "not-a-real-tool"
    那么 命令失败，错误码为 "config_invalid"

  场景: 为 claude 生成的归档与继续技能带有 memory 维护规则
    当 用户以 JSON 模式初始化工作流目录并配置工具 "claude"
    那么 命令成功
    并且 技能 "loopspec-archive" 只在用户要求归档时复查 memory，且先预览归档
    并且 技能 "loopspec-continue" 只在约定事件发生时更新 memory，且不作为推进前提
    并且 技能 "loopspec-archive" 与 "loopspec-continue" 的 memory 维护流程逐字相同
