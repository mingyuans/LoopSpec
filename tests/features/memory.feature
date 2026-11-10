# language: zh-CN
@memory
功能: 用 loopspec memory list / show 查阅项目记忆
  memory 由 Agent 直接新建、编辑 home/memory/<topic>.md 维护，CLI 只读不写；
  memory list 只把合法命名的 Markdown 文件列为主题并给出标题、适用时机提示与大小，支持分页，
  可选列出被忽略的条目及原因；memory show 返回主题全文并标明其为不可信数据，路径越界一律拒绝。
  主题一经新建或更新，list、show 与 change status 的 MEMORY 段立即反映最新内容；
  change archive 只搬动 Change，不读写 memory，记忆跨 Change 保留。

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

  场景: 新建的主题立即出现在索引中并可查看全文
    假如 记忆目录中有主题 "testing"
    当 Agent 新建记忆主题 "release"，标题为 "发布流程"、适用时机为 "发版前。"
    并且 用户列出记忆主题
    那么 命令成功
    并且 记忆主题列表为 "release,testing"
    并且 主题 "release" 的标题为 "发布流程"
    并且 主题 "release" 的提示为 "发版前。"
    并且 主题 "release" 的大小与文件字节数一致
    当 用户查看记忆主题 "release"
    那么 命令成功
    并且 返回的内容与主题 "release" 文件完全一致

  场景: 更新主题后索引与全文都反映最新内容
    假如 记忆主题 "testing" 的内容含适用时机 "修改 CLI 行为时。"
    当 Agent 把主题 "testing" 的适用时机改为 "排查回归时。" 并追加条目 "- 先跑 make test"
    并且 用户列出记忆主题
    那么 命令成功
    并且 主题 "testing" 的提示为 "排查回归时。"
    并且 主题 "testing" 的大小与文件字节数一致
    当 用户查看记忆主题 "testing"
    那么 命令成功
    并且 返回的内容与主题 "testing" 文件完全一致
    并且 返回的内容包含 "- 先跑 make test"
    并且 返回的内容不包含 "修改 CLI 行为时。"

  场景: 新建并更新 core 后 change status 内联最新的 core
    假如 已新建 Change "AFD1111"
    当 查询 Change "AFD1111" 的状态
    那么 命令成功
    并且 Change 状态中没有 core
    当 Agent 新建记忆主题 "core"，内容为 "- 规则一：先读 tests/README.md"
    并且 查询 Change "AFD1111" 的状态
    那么 命令成功
    并且 Change 状态内联的 core 包含 "- 规则一：先读 tests/README.md"
    当 Agent 在主题 "core" 末尾追加 "- 规则二：步骤文本全局唯一"
    并且 查询 Change "AFD1111" 的状态
    那么 命令成功
    并且 Change 状态内联的 core 包含 "- 规则二：步骤文本全局唯一"
    并且 Change 状态内联的 core 与主题 "core" 文件完全一致

  场景: 命名不合法的新文件不会成为主题
    当 Agent 在记忆目录新建文件 "Core.md"
    并且 Agent 在记忆目录新建文件 "a b.md"
    并且 用户以 --all 列出记忆主题
    那么 命令成功
    并且 记忆主题列表为 ""
    并且 被忽略的条目 "Core.md" 原因为 "invalid_name"
    并且 被忽略的条目 "a b.md" 原因为 "invalid_name"

  场景: 归档 Change 不改动记忆，后续 Change 仍能看到 core 与主题
    假如 Change "AFD1111" 的文档流程已全部完成
    并且 记忆目录中有主题 "core,testing"
    并且 记下归档前的记忆目录
    当 归档 Change "AFD1111"
    那么 命令成功
    并且 记忆目录与归档前逐字节一致
    当 新建 Change "AFD2222"
    那么 命令成功
    当 查询 Change "AFD2222" 的状态
    那么 命令成功
    并且 Change 状态内联的 core 与主题 "core" 文件完全一致
    并且 Change 状态的记忆索引包含主题 "testing"
