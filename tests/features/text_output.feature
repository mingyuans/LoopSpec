# language: zh-CN
@text_output
功能: loopspec 命令默认输出写给 LLM 的文本报告，--json 切回 JSON
  工作流命令默认输出纯文本报告（顶格 === 分节、说明段、沿用 JSON 字段名的 key: value，
  多行内容缩进引用），带 --json 时输出与之前相同的 JSON；失败时文本模式输出 === ERROR === 报告。

  场景: Agent 从 node instructions 的文本中读到指令正文与产物路径
    假如 隔离项目中有一个已批准的缺陷修复 Plan
    当 以默认格式获取节点 "requirements/proposal" 的执行指令
    那么 命令成功
    并且 输出是以 "=== NODE ===" 开头的文本报告
    并且 文本中有 "INSTRUCTION" 与 "TEMPLATE" 两节，正文逐行缩进四个空格
    并且 文本中有 "resolvedOutputPath" 字段，值为活动 Plan 目录下的 "artifacts/requirements/proposal.md"

  场景: 带 --json 时输出与文本同一份数据的 JSON
    假如 隔离项目中有一个已批准的缺陷修复 Plan
    当 以 --json 获取节点 "requirements/proposal" 的执行指令
    那么 命令成功
    并且 输出字段 "status" 为 "ready"

  场景: 文本模式下失败输出 ERROR 报告
    当 以默认格式查看不存在的需求 "NOPE1" 的 Plan
    那么 退出码为 1，输出是 "=== ERROR ===" 报告且错误码为 "change_not_found"
