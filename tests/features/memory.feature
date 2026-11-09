# language: zh-CN
@memory
功能: 用 loopspec memory list / show 查阅项目记忆
  memory list 只把 home/memory 下的 Markdown 文件列为主题并给出适用时机提示，支持分页，
  可选列出被忽略的条目及原因；memory show 返回主题全文并标明其为不可信数据，路径越界一律拒绝。

  场景: 没有记忆目录时列表成功且为空
    当 用户列出记忆主题
    那么 命令成功
    并且 输出字段 "total" 为 "0"
    并且 记忆主题列表为 ""

  场景: 只列出 Markdown 主题，--all 报告被忽略的文件
    假如 记忆主题 "testing" 的内容含适用时机 "修改 CLI 行为时。"
    并且 记忆目录中有非 Markdown 文件 "notes.txt"
    当 用户列出记忆主题
    那么 命令成功
    并且 记忆主题列表为 "testing"
    并且 主题 "testing" 的提示为 "修改 CLI 行为时。"
    并且 输出中没有 ignored 字段
    当 用户以 --all 列出记忆主题
    那么 命令成功
    并且 被忽略的条目 "notes.txt" 原因为 "not_markdown"

  场景: 按 offset 与 limit 分页
    假如 记忆目录中有主题 "t0,t1,t2,t3,t4"
    当 用户以 limit "2"、offset "2" 列出记忆主题
    那么 命令成功
    并且 记忆主题列表为 "t2,t3"
    并且 输出字段 "nextOffset" 为 "4"

  场景: 负数 offset 被拒绝
    假如 记忆目录中有主题 "t0"
    当 用户以 offset "-1" 列出记忆主题
    那么 命令失败，错误码为 "memory_bad_range"

  场景: 查看主题返回全文并标明不可信数据
    假如 记忆主题 "testing" 的内容含适用时机 "排查回归时。"
    并且 记忆目录中有主题 "core"
    当 用户查看记忆主题 "testing"
    那么 命令成功
    并且 输出字段 "path" 为 "memory/testing.md"
    并且 返回的内容与主题 "testing" 文件完全一致
    并且 输出字段 "untrustedData" 非空
    当 用户查看记忆主题 "core"
    那么 命令成功
    并且 返回的内容与主题 "core" 文件完全一致

  场景: 不存在的主题与越界路径被拒绝
    假如 记忆目录中有主题 "core"
    当 用户查看记忆主题 "missing"
    那么 命令失败，错误码为 "memory_not_found"
    当 用户查看记忆主题 "../x"
    那么 命令失败，错误码为 "unsafe_path"
