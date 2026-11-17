# language: zh-CN
@graph
功能: 用 loopspec graph 把 Profile 或 Plan 画成依赖图
  graph 把 Profile 或某个 Change 的 Plan 渲染成自包含的 HTML 依赖图，按层标出可并行的节点、
  依赖与 on_fail 回退，活动 Plan 还会标出每个节点的状态。
  有图形界面时在浏览器打开；远程或无图形界面时不打开，只给出文件路径与 file:// 链接。

  场景: Profile 渲染为 HTML 并标出前后端可并行的层
    当 用户在无图形界面的终端为 Profile "large-feature" 生成依赖图
    那么 命令成功
    并且 输出字段 "kind" 为 "profile"
    并且 依赖图的可并行层包含 "4"
    并且 依赖图 HTML 包含 "fe/code/implement"
    并且 依赖图 HTML 包含 "be/code/implement"
    并且 依赖图文件位于 workflow home 的 ".cache/graph/profile-large-feature.html"

  场景: 草稿 Plan 的依赖图带 digest 但没有运行状态
    假如 隔离项目中有一个缺陷修复流程的草稿 Plan
    当 用户在无图形界面的终端为 Change 当前的 Plan 生成依赖图
    那么 命令成功
    并且 依赖图 HTML 包含草稿 Plan 的 digest
    并且 依赖图中没有任何节点带运行状态
    并且 依赖图 HTML 包含 "on_fail ×3"

  场景: 已批准 Plan 的依赖图标出节点状态
    假如 隔离项目中有一个已批准的缺陷修复 Plan
    当 用户在无图形界面的终端为 Change 的 Plan "001" 生成依赖图
    那么 命令成功
    并且 依赖图 HTML 包含 'data-id="requirements/proposal"'
    并且 依赖图中节点 "requirements/proposal" 的状态为 "ready"
    并且 依赖图中节点 "be/code/implement" 的状态为 "blocked"

  场景: 远程 SSH 会话不打开浏览器，只给出文件链接
    当 用户在 SSH 远程会话中为 Profile "bugfix" 生成依赖图
    那么 命令成功
    并且 输出字段 "opened" 为 "false"
    并且 输出字段 "reason" 为 "remote session (SSH)"
    并且 输出的 url 是依赖图文件的 file:// 链接
    并且 没有调用浏览器

  场景: 默认输出给人看的文本，远程会话提示拷贝文件
    当 用户在 SSH 远程会话中以文本输出为 Profile "bugfix" 生成依赖图
    那么 命令成功
    并且 文本输出包含 "Graph written: "
    并且 文本输出包含 "URL: file://"
    并且 文本输出包含 "Not opened (remote session (SSH))."
    并且 文本输出包含 "scp <host>:"

  场景: 文本输出模式下的错误也是文本
    当 用户以文本输出只用 --plan 生成依赖图
    那么 命令以退出码 1 结束
    并且 文本输出包含 "Error [option_conflict]: --plan 必须与 --change 一起使用"

  场景: 有图形界面时用浏览器打开依赖图
    当 用户在有图形界面的本机为 Profile "bugfix" 生成依赖图
    那么 命令成功
    并且 输出字段 "opened" 为 "true"
    并且 浏览器打开的正是输出的 url

  场景: 用 --output 写到指定文件
    当 用户把 Profile "bugfix" 的依赖图写到 "out/flow.html"
    那么 命令成功
    并且 文件 "out/flow.html" 是依赖图 HTML

  场景: --profile 与 --change 同时给出或都不给时拒绝执行
    当 用户同时用 --profile 与 --change 生成依赖图
    那么 命令失败，错误码为 "option_conflict"
    当 用户不指定 Profile 也不指定 Change 生成依赖图
    那么 命令失败，错误码为 "option_conflict"
    当 用户只用 --plan 生成依赖图
    那么 命令失败，错误码为 "option_conflict"
    并且 没有写出任何依赖图文件

  场景: 不存在的 Change 报 change_not_found 且不写文件
    当 用户在无图形界面的终端为 Change "NOPE1" 的当前 Plan 生成依赖图
    那么 命令失败，错误码为 "change_not_found"
    并且 没有写出任何依赖图文件

  场景: 没有未结束的 Plan 时报 plan_not_found
    假如 隔离项目中有一个还没有 Plan 的 Change
    当 用户在无图形界面的终端为 Change 当前的 Plan 生成依赖图
    那么 命令失败，错误码为 "plan_not_found"
