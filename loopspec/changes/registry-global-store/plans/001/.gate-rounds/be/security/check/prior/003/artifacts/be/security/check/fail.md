---
verdict: FAIL
summary: "第 3 轮：上轮 3 条已修复，但守卫按 token 猜测 --home 可被 --note 的值误导，固定 tag 的项目允许 lock 省略 tag 从而跳过 tag 校验"
---

# 后端安全审查：失败

## 阻塞问题

- `tests/llm_bin/loopspec` `configured_registry_url()`：按 token 猜测 `--home`，`plan create --note --home=<dir>` 中的值会被当成 home，守卫检查了另一个目录，而真实 CLI 使用默认 home 的 registry，可绕过 fixture 白名单。
- `src/loopspec/registry_store.py` `pinned()`：`config.yaml` 固定了 `registry.version`（tag）时，仍接受 `tag: null` 的 lock；配合已缓存的未发布 commit 快照与匹配 hash，可跳过 tag→commit 校验。

## 审查输入

- 轮次 `001.1:be/security/check:3`，基线 `04812daa63283f7991d1c4684958e3538b816928`。
- 上轮 3 条已修复：先检查后创建存储目录；已缓存快照的未验证 tag 在线校验；守卫用 CLI 自己的解析器读配置。
- 剩余风险（不阻塞）：若其他本机用户能重命名 store 的祖先目录，检查与后续按路径创建之间存在竞态；与代码库其余部分「用户 home 祖先可信」的威胁模型一致。读命令隐式联网为已接受设计；git 浅拉取前无磁盘配额为既有问题。

## 建议修复方向

- 守卫对默认 home 与所有可能的 `--home` 候选都检查 registry，任一不符即拒绝。
- `config.yaml` 固定 tag 时，lock 的 `tag` 必须等于该 tag，否则 `registry_lock_mismatch`。
