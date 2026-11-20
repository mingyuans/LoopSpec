# language: zh-CN
@skill_sync
功能: 工作流命令自动同步项目中的 loopspec skill
  带 --home 的工作流命令执行前，把项目里已配置 AI 工具的 loopspec skill/command 文件
  同步到当前 CLI 内置的内容：过期的覆盖、缺失的补上，未配置的工具不新建；
  同步只在 stderr 提示，不改变命令的输出，失败也不影响命令本身。

  场景: 升级 CLI 后过期和缺失的 skill 被自动同步
    假如 项目已用 loopspec init 配置了 claude 的 skill
    并且 项目中的 skill "loopspec-new" 是旧版本内容
    并且 项目中缺少 skill "loopspec-archive"
    当 在项目中新建 Change "SYNC1"
    那么 命令成功
    并且 skill "loopspec-new" 与 CLI 内置内容一致
    并且 skill "loopspec-archive" 与 CLI 内置内容一致
    并且 stderr 提示同步了 2 个 skill 文件
    并且 项目中没有为未配置的工具 "cursor" 创建文件

  场景: skill 已是最新时不改动任何文件也不提示
    假如 项目已用 loopspec init 配置了 claude 的 skill
    当 在项目中新建 Change "SYNC1"
    那么 命令成功
    并且 stderr 没有同步提示

  场景: skill 路径是符号链接时不跟随，只告警
    假如 项目已用 loopspec init 配置了 claude 的 skill
    并且 项目中的 skill "loopspec-new" 是指向项目外文件的符号链接
    当 在项目中新建 Change "SYNC1"
    那么 命令成功
    并且 项目外的文件没有被改写
    并且 stderr 告警无法同步 skill "loopspec-new"
