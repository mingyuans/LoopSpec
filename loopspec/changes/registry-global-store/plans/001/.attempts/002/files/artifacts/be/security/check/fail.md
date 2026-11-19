---
verdict: FAIL
summary: "第 2 轮：RecursionError 已修复；存储目录仍先创建后检查符号链接、已缓存快照不校验 lock tag 绑定、LLM 守卫的逐行 config 扫描可被合法 YAML 绕过"
---

# 后端安全审查：失败

## 阻塞问题

- `src/loopspec/registry_store.py` `_private_dir()`：先按绝对路径 `os.mkdir` 缺失目录，再做 O_NOFOLLOW 检查；中间分量是符号链接时，返回 `unsafe_path` 之前已在链接目标下创建了目录。
- `src/loopspec/registry_store.py` `materialize()` 缓存命中路径：只核对来源、commit 与文件 hash，不核对 lock 的 `tag` 是否已被验证指向该 commit；本机已有某 commit 快照时，伪造 lock 可借已发布 tag 名使用它。
- `tests/llm_bin/loopspec` `configured_registry_url()`：逐行扫描 config.yaml，与 CLI 的 YAML 解析不一致（如流式映射 `registry: {url: ...}`），可漏识别 registry 从而跳过 fixture URL 与存储位置检查。

## 审查输入

- 轮次 `001.1:be/security/check:2`，基线 `04812daa63283f7991d1c4684958e3538b816928`。
- 方法：人工复核 + Codex 只读复核。已修复：lock/计划解析 RecursionError。
- 已接受风险（不阻塞，来自 HUMAN 决策「缺失时自动拉取」）：读取定义的普通命令在缓存缺失时会按项目配置访问 registry 远端，可能触发本机 git 凭据认证；文档需明确说明。

## 建议修复方向

- 存储目录从最深的已存在祖先起用 `workflow_io.directory(..., create=True)` 逐级 O_NOFOLLOW 打开并创建。
- 快照 manifest 记录发布时已验证的 tag；命中缓存且 lock 的 tag 不在其中时，先在线校验 tag→commit，失败即报错。
- 守卫用被测 CLI 自己的 `load_config` 解析 registry url，解析失败或配置了 registry 却不等于 fixture URL 时拒绝。
