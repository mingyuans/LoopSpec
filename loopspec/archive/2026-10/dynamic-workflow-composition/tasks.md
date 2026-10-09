## 1. 领域模型与兼容基础——第一版本

- [x] 1.1 增加统一 Node 的直接定义/use 引用互斥模型、Fragment、Profile、Plan 请求/快照及元数据模型，拒绝未知字段、includes 与重复 YAML 键。
- [x] 1.2 为目录、编译、审批、修订、路由、证据、保障和事务失败增加结构化错误及 JSON 契约。
- [x] 1.3 实现目录约束、打开时文件身份检查、符号链接与路径替换防护、有界单次读取缓存、规范摘要与原子写入辅助函数。
- [x] 1.4 隔离旧 Schema/Change 兼容适配器，保持旧路径、五态、任务跟踪、rollback 和 archive 行为。

## 2. Fragment 编译与独立实例——第一版本

- [x] 2.1 实现 fragments/<name>/fragment.yaml 自包含目录发现、命名校验、单一 nodes 列表混合直接定义/use 引用与安全资源解析。
- [x] 2.2 实现递归引用展开与定义环检测，并限制深度、实例数量和累计资源大小。
- [x] 2.3 实现实例路径身份、本地 Node 引用解析、引用成员树与根/终端推导，同定义多次引用生成独立实例。
- [x] 2.4 展开统一 Node requires，校验执行 DAG、Node 顶层 on_fail.reset 祖先及任务跟踪关系。
- [x] 2.5 实现实例产物根、依赖产物路径呈现、模板命名空间和跨实例/控制目录输出冲突检查。
- [x] 2.6 增加单节点、混合列表、定义/use 互斥、并行、同 PR Review 多实例、递归环及恶意路径专项测试。

## 3. Profile 与 Plan 编译——第一版本

- [x] 3.1 实现 Profile 加载与 flow 依赖校验，支持串行、并行、指引、保护要求和恢复规则的静态模型。
- [x] 3.2 增加项目最低保障配置，合并 Profile 约束并检查切换模板不能自动削弱项目要求。
- [x] 3.3 实现可选 based_on 的完整 Plan 请求，以及选择理由、偏离、基础修订版和精确基线的校验。
- [x] 3.4 构建单次解析资源包与内容摘要，覆盖定义、叶子图、引用成员树、候选失败处理链、规则限额、基线、理由和落盘资源字节哈希。
- [x] 3.5 实现受保护偏离的摘要绑定人工审批；资源或结构变化使旧审批失效。
- [x] 3.6 实现 Plan 暂存、资源复核、独立版本目录、写锁和原子激活；失败不改变活动绑定。
- [x] 3.7 实现活动 Plan 加载与完整性校验，运行时不重新读取来源 Fragment/Profile。

## 4. 第一版本资源与 CLI

- [x] 4.1 提供需求、设计、实现及审查 Fragment，以及 large-feature、frontend-small-change、bugfix 模板。
- [x] 4.2 实现 fragments/profiles list/show/validate 和 profiles save，保存模板时去除状态、证据及审批。
- [x] 4.3 实现 plans validate/show/history 与 new --plan/--profile，保留互斥的旧 --schema 入口。
- [x] 4.4 实现 plan-backed status/next/instructions/rollback、引用节点五态汇总及实际叶子导航；普通未完成、证据过期和系统错误不伪造 FAIL，next 复用 status.nextSteps 的确定性选择。
- [x] 4.5 扩展 init 的缺失资源复制、项目路径映射指引和模板最低能力版本检查，V1 使用人工收尾并拒绝未支持的 V2 引用 on_fail/路由/保障能力。
- [x] 4.6 验证三类场景 Plan、原子失败、源文件变化、审批过期、并发激活和旧生命周期兼容。

## 5. Fragment 失败路由与返工——第二版本

- [x] 5.1 实现有效 Gate Failure 识别、Profile route_case 枚举校验与 Node 固定 reset；冲突/损坏结果阻塞，不接受报告指定目标或引用归属。
- [x] 5.2 校验叶子与引用 Node on_fail、Profile recovery 及最近内部优先候选处理链；支持没有局部规则或预算耗尽时传播，保持执行 DAG 与必需 Gate。
- [x] 5.3 计算上游直接/引用目标、失败 Gate、选中引用边界全部成员及下游的重置闭包，保留独立并行分支。
- [x] 5.4 实现报告、产物、代码 Gate/保障证据归档，以及 Attempts 的来源 Gate、轮次、唯一处理者、传播层级与闭包记录。
- [x] 5.5 实现返工写锁、可恢复事务记录及恢复命令，中断时阻塞 next，保留业务代码。
- [x] 5.6 实现稳定处理者/规则/Gate 历史预算与引用共享限额；测试内部优先、耗尽传播、父重置不清零、身份重命名绕过、多 Gate 串行与同一失败幂等，以及 QA 分类和中断恢复。

## 6. Git 输入与 Gate 审查证据——第二版本

- [x] 6.1 实现固定 Git 基线、仓库身份和显式基准校验，保留基线前尚未提交的改动并展示覆盖范围。
- [x] 6.2 以无 Shell、无外部 Diff 驱动/textconv 的 Git 调用采集 NUL 清单，覆盖 Index、工作树与新文件。
- [x] 6.3 规范化新增、删除、重命名、文件类型/模式和符号链接摘要，拒绝越界、超限及不支持输入。
- [x] 6.4 实现扫描一致性检查、忽略文件分类及精确控制目录排除，避免证据写入自引用和代码目录隐藏。
- [x] 6.5 实现 gate begin 固定审查输入、范围和轮次令牌，输出受限清单与只读输入上下文。
- [x] 6.6 实现 gate record 的就绪检查、一次性令牌、输入再校验、报告哈希和原子证据记录，不接受报告自报 Scope 摘要。
- [x] 6.7 验证审查期间改动、旧轮次令牌、Index/工作树不一致、路径特殊字符、并发变化和 Secret 不输出。

## 7. 全量 Diff 保障——第二版本

- [x] 7.1 实现保障规则与 Gate 能力声明及实例绑定，保留轻量 Plan 中尚未提供能力的诊断信息。
- [x] 7.2 实现实际路径命中要求的并集、当前 Scope 摘要验证，以及 missing/stale/unknown/missing_fragments 分类。
- [x] 7.3 实现 change-assurance Fragment 的确定性检查和系统证据，手写 pass.md 不构成通过。
- [x] 7.4 校验最终保障依赖全部交付分支，支持完整修复 Fragment 路由并重新经过 QA。
- [x] 7.5 在 next、完成和 archive 边界复核代码 Gate/保障证据，过期时回到 ready 并报告 evidence_stale，旧 PASS 文件不能妨碍重新审查。
- [x] 7.6 验证 FE 修复触及 BE、审查后再改代码、未知目录、多个实例证据不混用及报告写入不自失效。

## 8. Plan 修订与安全扩张——第二版本

- [x] 8.1 实现普通未来工作重组的当前/完成/失败/Attempts 节点与引用成员/恢复链冻结、预算身份历史映射和基础修订版并发检查。
- [x] 8.2 实现基于 Assurance 诊断的增加型扩张，限定新增 Fragment 并保留旧定义与固定基线。
- [x] 8.3 显式记录新增依赖影响的旧 QA/Assurance Node，只允许增加必要前置并归档其旧完成证据。
- [x] 8.4 在同一可恢复事务中激活修订并失效旧证据，默认不跨 Plan 摘要继承代码 Gate PASS。
- [x] 8.5 验证 FE Plan 升级 BE、冻结绕过、保护削弱、过期请求及归档/激活各阶段失败恢复。

## 9. Skill、文档与完整验证

- [x] 9.1 更新 new/continue/archive/bulk-archive Skill 的统一 nodes、引用汇总与唯一失败处理、四层模型、证据协议和保障边界。
- [x] 9.2 更新 builtin/skills 英文投影源并验证工具投影生成；按用户澄清，不修改 .codex/skills、.claude/skills 等本地安装目录，保留无关 AI-DLC 文件和用户修改。
- [x] 9.3 更新中英文概览、Agent 协议、CLI、配置与迁移文档，注明项目路径映射和外部提交边界。
- [x] 9.4 在临时 Git 仓库执行混合 nodes 与嵌套恢复、三类场景、QA 后端返工、FE 意外改 BE、保障过期与安全扩张端到端验证。
- [x] 9.5 运行相关专项及完整 pytest、ruff、mypy 和双语文档契约检查，修复失败。
- [x] 9.6 审查最终 Diff，核对不可信输入、目录约束、证据语义、事务恢复以及无关用户工作保护。

## 10. Fragment 目录化与模板补齐

- [x] 10.1 Fragment 改为自包含目录 `fragments/<name>/fragment.yaml`，资源相对所属目录解析并拒绝越界与符号链接；平铺定义不再识别。
- [x] 10.2 运行时与旧 Schema 对齐：产物节点返回 template，Gate 返回 templates.pass/fail。
- [x] 10.3 内置 Fragment 补齐产物模板与 Gate PASS/FAIL 模板（含 verdict/summary 头部，QA FAIL 含 route_case）；pr-review 更名为 backend-pr-review，FE/BE 测试与审查各自维护指令。
- [x] 10.4 更新内置 README、中英文组合文档与 CLI 参考，增加目录、越界、模板契约与运行时返回测试。

## 11. Flow 级 on_fail 替代 Profile recovery

- [x] 11.1 FragmentRef（Profile flow 与 Plan 请求条目）增加可选 on_fail；reset 只允许同一 flow 中的上游实例，失败时重置全部列出实例。
- [x] 11.2 处理链最外层改为 flow 实例 on_fail，保持最近内部优先、预算持久与唯一处理者。
- [x] 11.3 删除 Profile/Plan 请求的 recovery、cases，失败报告的 route_case，以及分类路由处理者与相关输出字段。
- [x] 11.4 内置 Profile 改用 flow 级 on_fail，QA 失败模板去掉 route_case；bugfix 只含需要的实现实例。
- [x] 11.5 更新 Skill、中英文文档与 CLI 参考；替换分类路由测试并运行完整 pytest、ruff、mypy。
