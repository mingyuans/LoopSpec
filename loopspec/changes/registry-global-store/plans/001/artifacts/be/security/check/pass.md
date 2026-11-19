---
verdict: PASS
summary: "第 5 轮：前几轮安全问题仍保持修复，本轮增量（tag 绑定持久化、配置探测、来源切换输出、共享 bundle、lock 体积与错误码）未引入新的安全问题"
---

# 后端安全审查：通过

## 审查输入

- 轮次 `001.1:be/security/check:5`，基线 `04812daa63283f7991d1c4684958e3538b816928`，23 个固定路径。
- 方法：人工审查本轮相对上次安全 PASS 的增量，并确认前几轮修复点仍在（符号链接、tag→commit 绑定、固定 tag、有界解析、守卫 fixture 限制）。

## 审查结论

- tag 绑定持久化：仅在 `verify_tag` 在线成功后写入 `<store>/<source-id>/tags/<tag>`；tag 名经 `check_tag` 校验；读写均经目录 fd 与 O_NOFOLLOW，位于当前用户私有、0700、无符号链接的存储内；内容按 commit 完全相等比较。绑定只缓存一次已发生的验证，实际读取的定义仍逐文件按 lock hash 校验。
- `registry_spec()` 探测：只检查是否声明 `registry` 或原文是否含该词，不执行、不回显配置内容；声明了 registry 时仍走严格加载。
- `sourceChanged`/`previousRegistry`：回显的是经 `RegistrySpec` 校验（拒绝内嵌凭据）的旧来源。
- `instructions()` 共用一个 bundle，消除一次响应内混用两个 lock 版本的可能。
- `lock_bytes()` 在 update 阶段校验目标 lock，超大 lock 映射为 `config_invalid`，均无新的输入面。

## 剩余风险

- 已接受设计：读取定义的命令在缓存缺失时按项目配置联网并使用本机 git 凭据（文档已提示）。
- 既有问题：git 浅拉取在内容限额生效前不限制磁盘写入。
- 威胁模型一致：其他本机用户若可重命名用户 home 的祖先目录，存在路径竞态。
- 已持久化的 tag 绑定在上游之后移动 tag 时不会自动失效；内容仍受 lock hash 保护，新的 tag 位置会在下次 `registry update` 时生成新计划。
