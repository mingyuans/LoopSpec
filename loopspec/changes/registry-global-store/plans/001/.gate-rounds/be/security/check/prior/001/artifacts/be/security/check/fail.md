---
verdict: FAIL
summary: "全局存储路径检查不拒绝中间符号链接、固定 tag 的 lock 未校验 tag 与 commit 绑定、LLM 守卫放行 registry 后可拉取任意仓库、lock/计划解析可触发未捕获的 RecursionError"
---

# 后端安全审查：失败

## 阻塞问题

- `src/loopspec/registry_store.py` `_private_dir()`：只对末级目录做 lstat，存储根路径的中间分量可以是符号链接，检查与后续创建/发布之间可被替换，快照可能被写到其他位置。
- `src/loopspec/registry_store.py` `materialize()` / `src/loopspec/registry_git.py` `fetch_commit()`：lock 中的 `tag` 只用于优先拉取，tag 指向别的 commit 时回退按 commit 拉取。registry 模式下定义内容不再出现在项目 diff 中，伪造的 lock 可以写上已发布 tag、实际指向未发布 commit，审阅者无法从 diff 发现。
- `tests/llm_bin/loopspec`：放行 `registry` 后只校验存储位置，模型可改 `config.yaml` 让 `registry update` 用宿主 git 凭据拉取任意仓库到项目内并读取。
- `src/loopspec/registry_store.py` `read_lock()` 与 `src/loopspec/registry_sync.py` `_load_plan()`：用 `yaml.safe_load` / `json.loads` 解析不可信输入，深度嵌套可触发未捕获的 `RecursionError`，`safe_load` 还会静默接受重复键。

## 审查输入

- 轮次 `001.1:be/security/check:1`，基线 `04812daa63283f7991d1c4684958e3538b816928`，23 个固定路径。
- 方法：人工审查 + Codex 只读独立审查（共 6 条，其中 2 条记为剩余风险：git 浅拉取前无磁盘配额（改动前已存在）；进程内验证缓存仅影响长驻进程，读取字节仍逐文件校验）。

## 建议修复方向

- 存储根用 `workflow_io.directory()` 逐级 O_NOFOLLOW 打开校验，再检查所有者与权限。
- 拉取锁定版本时，若 lock 带 tag，先 `ls-remote` 确认 tag 解引用后的 commit 与 lock 一致，不一致报 `registry_lock_mismatch`。
- 守卫要求 `config.yaml` 中的 registry url 等于测试注入的固定 URL。
- lock 改用有界的 `parse_yaml()`；计划解析捕获 `RecursionError` 并按 stale 处理。
