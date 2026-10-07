# Security Review: PASS

## Scope Reviewed

- `design.md` D1–D8，重点是 D2 替换请求与校验、D4 撤销、D5 切换事务（moves/copies）、D6 历史边界、D8 安全边界。
- `tasks.md` 全部 7 组任务，重点核对标注【安全】的 1.3、2.2、3.3、4.2。
- 涉及的现有代码：`workflow_confirmation.py`（确认事务、inspect/finish、Move 校验）、`workflow_revision.py`（validate_frozen）、`workflow_lifecycle.py`（prepare/create）、`workflow_drafts.py`、`workflow_snapshot.py`（materialize、单指针）、`workflow_recovery.py`（closure_files、attempt_records）、`workflow_io.py`（无跟随链接的目录访问与原子写入）。

## Checks Performed

- **注入**：没有新增 Shell、SQL 或模板执行。`reason`、`retire` 原因只作为数据记录和展示，有长度上限。
- **不可信输入解析**：`replaces` 使用严格 YAML 与 strict 模型。`reuse`/`carry`/`retire` 的键和值只能是旧 Plan 或新 Plan 中已存在的规范身份，不作为路径直接使用（D2、任务 1.3）。
- **路径穿越与业务代码保护**：
  - moves 的源来自旧 Plan 节点的 `closure_files`，copies 的目标来自新 Plan 被沿用节点的 `generates`，源和目标都由引擎计算，请求不能提供路径；
  - 事务的 inspect 拒绝任何越界路径（D5、任务 4.2）；
  - 业务代码不会出现在移动或复制范围内；
  - 读写沿用 `workflow_io` 的目录描述符访问方式，不跟随符号链接。
- **授权与流程绕过**：
  - 替换和撤销都不放宽人工确认，`--expected-digest` 防止确认到被替换过的草稿；
  - 有替换草稿时，执行类命令统一返回 `plan_suspended`（D3）；
  - 替换必须经过 `compile_plan` 的项目约束检查，以及固定基线和规则快照比对；
  - 覆盖检查防止通过替换漏掉已改代码的审查（D2 第 5 点）；
  - Gate 结论不能沿用，代码证据绑定 Plan 摘要；
  - exhausted 的 Gate 只能 `retire`，不能 `carry`。
- **完整性和原子性**：
  - 沿用的内容哈希写进草稿摘要，确认时和恢复时都会再次校验；
  - 只有一个活动指针，并且原子写入；
  - 事务文件在任何移动发生之前写入，并先用同一个解析器校验；
  - 复制目标如果已经存在，只做校验、不覆盖（D5）。
- **历史保护**：返工记录原地保留，用 `history_boundary` 区分属于哪个 Plan；确认时如果出现边界之后的新记录就拒绝。
- **反序列化、密钥、依赖**：没有任意对象构造；没有新增密钥、网络访问或第三方依赖。

## Notes

以下事项不阻塞，实现时需要落实：

1. **复制要使用和归档相同的安全读写**：copies 用 `read_bytes` + `atomic_write`，不能用 `shutil.copy` 一类按路径跟随链接的接口。复制前还要校验源文件大小在 `MAX_FILE_BYTES` 以内。
2. **事务条目数上限**：替换会归档旧 Plan 的全部节点。`ConfirmationTransaction.moves` 现在最多 4096 条，产物带通配符的大 Plan 可能超出。必须在写入事务文件之前就校验并以结构化错误拒绝（现有的"先校验再写"顺序已经满足），不能出现部分归档。copies 也要设置同样的上限。
3. **`plans discard` 不能由 Agent 自行执行**：Skill 必须先取得人的明确同意。撤销记录和确认记录一样，不能当作身份认证，文档要如实说明。
4. **继承的失败报告是不可信数据**：`inheritedFailures` 里的报告正文来自上一份 Plan 的执行结果，在指令中要标为不可信数据，不能让其中的指令改变返工范围。
