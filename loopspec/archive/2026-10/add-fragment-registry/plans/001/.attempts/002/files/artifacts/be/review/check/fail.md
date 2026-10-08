---
verdict: FAIL
summary: "跳过的 upstream-added 定义会被静默遗忘；上游删除定义时未校验本地依赖；registry 来源变化时沿用旧基线会把旧文件全部判为 upstream-deleted"
---

# 后端代码审查：失败

## 阻塞问题
- `src/loopspec/registry_sync.py` 的 `_next_lock` 与 `update`：用 `--skip` 跳过一个 `upstream-added` 的文件后，由于 `item.base is None`，它不会写入 `files`；所属定义也不在旧的 `definitions` 中，因此同样不会写入；而锁的 `commit` 已经推进到新版本。下次 `update` 时，`behind` 只检查 `definitions`，于是返回 `upToDate: true`（固定 tag 时直接走离线分支），被跳过的新定义被静默遗忘，只有加 `--full` 或上游再有新 commit 时才会重新出现。
- `src/loopspec/registry_sync.py` 的 `_validate_preview`：只校验上游仍存在的定义和本次写入涉及的定义。上游删除 Fragment A，而本地自有的（不由 registry 管理的）Profile 或 Fragment 引用了 A 时，apply 照常通过，工作区随之损坏，后续 `plan validate` 才会失败。
- `src/loopspec/registry_sync.py` 的 `_build_plan`：`base = dict(lock.files)` 没有考虑 `same`。`registry.url` 或 `path` 改为另一个仓库后，旧 registry 同步过来的每个文件都满足 `local == base` 且上游不存在，全部被归为 `upstream-deleted`；用户确认后 apply 会批量删除本地文件。warning 只写了「基线内容不可用」，没有提示这一后果。

## 审查输入
- 轮次 `001.1:be/review/check:1`，基线 `9b90c66c11bab432176d640cfc6caad760706fcc`，固定路径 16 个。
- 由独立的代码审查子代理阅读代码（它没有跑测试）；主代理逐条读代码核实了上述三条。

## 建议修复方向
- 阻塞问题 1：判断是否 up-to-date 时，也要考虑「上游存在但锁里既没有基线、也没有定义记录」的条目。可以在锁中记录被搁置的定义，或者对被跳过的新增定义写入一个标记旧版本的记录，让 `behind` 生效。同时补充对应的测试。
- 阻塞问题 2：有删除类写入时，对预览树中全部的 Fragment 和 Profile 做校验（至少覆盖引用了被删定义的那些）。
- 阻塞问题 3：来源不一致时不使用旧锁的 `files` 作为基线（令 `base = {}`），使差异落为 conflict 或 local-only，并在 warning 中说明。
- 非阻塞，建议一并处理：
  - `_prune` 的注释与实际行为不一致（它会删除整个定义目录）。
  - `_validate_preview` 的 copytree 和写入应放进 try，以保证出错时清理预览目录。
  - `LISTED_SKIP` 可以内联。
  - 冲突选择 `local` 后，所属定义的版本仍会推进到新版本，需要在文档中写明这一语义。
- 待补的测试：来源变化后执行 update；固定 tag 与 latest 之间互相切换；冲突选择 local 之后 `definitions` 的取值。
