# 实施报告

## 已完成任务

tasks.md 的 25 项任务全部完成。

- 1.1–1.3：版本 3 Change 生命周期允许未规划、草稿与活动绑定为空；独立草稿 ID、自包含缓存和摘要保存；旧活动 Plan 摘要与 Schema 兼容读取，未知/损坏现代格式不得降级。
- 2.1–2.4：默认 new 只建 Change；plans create 保存任务草稿，plans show 优先草稿并支持 --active；plans validate 只读，所有新 Plan 都需明确确认，不再使用模板偏离审批文件。
- 3.1–3.5：plans approve 支持可选精确摘要/说明，消费展示草稿的缓存并复核当前政策、原基线、冻结边界和预算；确认记录、失效归档和活动绑定使用可恢复事务。重复确认幂等，recover 不能制造批准。
- 4.1–4.4：首次未批准的 status/next 无执行叶子、isComplete 为 false；执行/Gate/保障/返工/完成归档阻塞。已有活动图保持可执行，待确认修订单独展示。recompose 只建草稿；安全扩张批准前不动旧产物，批准后重绑代码证据并重跑受影响 QA/保障。
- 5.1–5.4：Profile 回归参考模板定位，移除对外 protected/deviations 权限；四份 builtin Skill 英文源和双语文档同步，英文文档正文保持英文。临时投影验证，不刷新真实安装目录。
- 6.1–6.5：新增生命周期/确认测试，迁移旧入口回归夹具；验证缓存、摘要、路径、政策变化、中断/并发、预算、三类模板及全量保障。完整检查和实施安全复审通过。

## 文件改动

### 实现

新增：

- src/loopspec/workflow_changes.py
- src/loopspec/workflow_drafts.py
- src/loopspec/workflow_lifecycle.py
- src/loopspec/workflow_confirmation.py

更新已有工作流实现：

- src/loopspec/cli.py
- src/loopspec/workflow_cli.py
- src/loopspec/workflow_models.py
- src/loopspec/workflow_planning.py
- src/loopspec/workflow_snapshot.py
- src/loopspec/workflow_recovery.py
- src/loopspec/workflow_revision.py
- src/loopspec/workflow_archive.py

### 资源与文档

- builtin/profiles/manual-v1.yaml、large-feature.yaml、frontend-small-change.yaml、bugfix.yaml
- builtin/skills/new.md、continue.md、archive.md、bulk-archive.md
- README.md
- docs/en/README.md、agent-protocol.md、cli-reference.md、configuration.md、workflow-composition.md、workflows/secure-spec-driven.md
- docs/zh/README.md、agent-protocol.md、cli-reference.md、configuration.md、workflow-composition.md、workflows/secure-spec-driven.md

### 验证与本需求记录

- 新增 tests/test_workflow_lifecycle.py、tests/test_workflow_confirmation.py。
- 更新 tests/test_workflow_cli.py、test_workflow_revision.py、test_workflow_runtime.py、test_workflow_recovery.py、test_workflow_assurance.py、test_workflow_diff.py、test_workflow_e2e.py、test_cli.py、test_status_report.py、test_skill_templates.py。
- 保留并运行 tests/test_docs_consistency.py、test_scaffold.py 的双语结构、英文语言、投影及用户文件保护检查。
- loopspec/changes/plan-draft-approval/approval/approved.md、tasks.md、state.md、security/implementation-review.md、apply/report.md。

没有删除业务文件。上一已完成变更的实现/文档和用户既有未提交修改继续保留，没有覆盖其报告或将用户文件计为本轮新增功能。

## 真实测试与检查

最终结果：

```text
env -u NO_COLOR make test
977 passed in 359.73s (0:05:59)

make lint
uv run ruff check src tests hatch_version.py
All checks passed!
uv run mypy src hatch_version.py
Success: no issues found in 49 source files

.venv/bin/pytest -q tests/test_docs_consistency.py tests/test_skill_templates.py tests/test_scaffold.py --tb=short
89 passed in 3.03s

git diff --check
退出码 0，无输出。
```

其他实际检查：

- 生命周期/确认/模型专项：52 passed in 12.28s。
- 文档、Skill、投影、CLI 与旧状态专项：206 passed in 15.99s。
- 使用项目 init 在独立临时目录仅生成 Claude 投影；Skill 创建规范提供的 quick_validate.py 对 new/continue/archive/bulk-archive 均返回 Skill is valid!。
- 临时 AFD1111 真实 CLI 验证 new 后 unplanned、草稿后 draft；两阶段 next 都 isComplete: false、instances: []、node: null，草稿阶段只引导展示，没有自动批准。
- 完整测试包含独立临时 Git 仓库中的 large-feature、frontend-small-change、bugfix，从展示草稿及模拟真实确认到代码 Gate、QA、Assurance 的全链路；QA 后端返工保留 FE，同时强制后端测试/安全/PR 审查重跑。

中间失败与修正如实保留：

1. 文档仍在补齐时启动的首轮完整测试：4 failed, 965 passed in 377.68s。失败为 create/approve 双语命令章节/选项契约尚未存在，已补齐并通过专项及最终完整回归。
2. 旧专项出现旧错误文本断言和 tracked Schema 夹具选错显式 Schema 的失败；修正断言/夹具，不恢复默认 new 的旧语义。
3. 新恢复遗漏产物测试的模拟 finish 没有复原，出现 `Expected regex: '遗漏'`、`Actual message: '模拟已批准但尚未归档'`。首次专项为 1 failed, 17 passed in 64.54s；修正前已启动的 make test 为 1 failed, 976 passed in 384.81s，等价 pytest 为 1 failed, 976 passed in 371.93s。复原真实函数后单项 1 passed in 8.70s；最终完整回归 977 项通过。
4. make lint/test 首次在沙箱中无法读取既有 uv 缓存：`error: failed to open file .../uv/sdists-v9/.git: Operation not permitted (os error 1)`。按权限机制获准重跑后通过；没有安装新依赖。
5. 临时目录刚初始化、AFD1111 尚未创建时，next 返回 change_not_found；随后实际执行 new 和 plans create 后，两阶段规划输出通过。没有将未创建需求误记为实现失败。

完整测试临时移除进程的外部 NO_COLOR 环境变量，避免既有终端颜色测试受环境影响；不修改项目显示逻辑或用户环境配置。

## 设计偏离与兼容选择

无实质设计偏离。

- 选择将 recompose 保留为创建草稿的兼容别名，不再直接激活。
- 旧保护/偏离模型及旧事务仅用于已有快照/历史兼容；现代公开输出与新请求不以它们提供权限，新 Plan 不可携带这些旧权限字段。
- 本地确认记录不认证调用者身份。项目政策在活动 Plan 中保持冻结，本轮未实现运行中政策迁移。

## 工作保护与后续事项

- 未修改真实 .codex/skills、项目 .claude/skills 或全局安装投影。四份 Skill 的源代码在英文 builtin/skills；要刷新安装投影需后续明确操作。
- 保留用户 .gitignore、AI-DLC 目录/配置及 add-schema-sources 变更；未提交、发布、安装替换 CLI 或自动归档。
- BREAKING：自动化需改为 new → plans create → 人工确认 → plans approve → next。旧 Schema 创建显式加 --schema；既有变更继续兼容执行。
- 实施安全复审见 security/implementation-review.md。生产级审查质量、身份认证与外部提交约束仍由独立系统承担，不由本地确认记录宣称保证。
