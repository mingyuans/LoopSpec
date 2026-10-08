---
verdict: PASS
summary: "上一轮三项阻塞（跳过的新增定义被遗忘、删除时未校验本地依赖、换来源时沿用旧基线）经独立复审与 6 个实验确认已修复，registry 测试 108 passed，无新阻塞问题"
---

# 后端代码审查：通过

## 审查输入
- 轮次 `001.1:be/review/check:2`，基线 `9b90c66c11bab432176d640cfc6caad760706fcc`，固定路径 16 个。
- 独立子代理复审，跑了 registry 测试（108 passed），并在 scratchpad 里另写 6 个实验（6 passed）；主代理核对了结论。

## 审查要点
- **正确性**：
  - `classify` 的全部分支都正确，包括两边都删除时为 unchanged。
  - `_next_lock` 在 local-modified、local-only、conflict（选 local 或 upstream）、skip 等情况下的取值都正确。
  - `held`：跳过 upstream-added 或 upstream-deleted 后，下次 update 会重新列出这些条目；与上游新 commit 叠加时同样正确；全部接受后 `held` 清空，再次 update 得到 upToDate。latest 与固定 tag 下都成立。
  - 固定 tag 与 latest 之间切换正确。
- **边界**：
  - 来源变化时不使用旧基线：旧来源独有的文件为 local-only，新来源独有的为 upstream-added，两边不同的为 conflict，不规划任何删除；apply 后旧来源的定义不再被跟踪。
  - 上游删除被本地 Fragment 或 Profile 依赖的定义时，apply 在写入前被拒绝。
  - 本地原本就坏的定义，以及名称不是 kebab 的本地 profile，都不阻塞同步。
- **错误处理**：预览校验失败时零写入、锁不变、预览目录已清理（`try/finally`）；`_prune` 的注释与行为一致。
- **数据访问**：所有读写都经 `workflow_io` 的安全接口；写入范围限于确认过的条目。
- **测试覆盖**：上一轮列出的测试缺口（跳过新增、来源变化、tag 切换、冲突选 local 后的版本、本地依赖被删）均已补齐。

## 剩余风险
以下均为非阻塞，建议作为后续改进：
- 依赖被删时报错难懂：例如本地 `fragments/mine` 引用了被删除的 `extra`，报错是 `unsafe_path` 加「路径不存在…」，没有点名 `extra`；提示语「在 registry 中修复」也不适用于本地自有的定义。建议对不由 registry 管理的定义换用专门的提示，并列出被删除的定义。
- 来源变化的 warning（`registry_sync.py`）和 `configuration.md` 都写着「所有差异按冲突处理」，而实际分类见上文；文档也没有写 apply 之后旧来源的定义不再被跟踪。
- 只跳过一个被删 Fragment 的部分文件（例如保留 `notes.md`、接受删除 `fragment.yaml`）时，会留下没有定义文件的孤儿目录，而锁里仍记着它的旧版本。建议在 skill 或文档中提示：跳过删除时要跳过该定义的全部文件。
- 本地改坏了一个由 registry 管理的定义时，它会阻塞所有 apply，而提示语指向 registry（这是原有行为）。
- 每个定义都新建一个 `WorkflowCatalog`，按目前的规模可以忽略。
