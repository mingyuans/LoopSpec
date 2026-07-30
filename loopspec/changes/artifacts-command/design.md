## Context

`loopspec` 今天能报出产物路径的只有两条代码路径，两条都以「当前那一个 schema、在当前那一个目录里」为前提：

| 代码位置 | 给出什么 | 边界在哪 |
| --- | --- | --- |
| `cli._node_output_summary` → `status` 的 `nodes[].existingOutputPaths` | 单个 schema 每个节点的现存产物 | `_load_change_context` 用 `resolve_schema_for_existing_change` 解析出**一个** schema；change 目录不存在时先以 `change_not_found` 失败 |
| `instructions._context_files` → `contextFiles` | 同上，按节点分组 | 同上。函数注释写明目的是「让一个节点无需猜文件名即可读到整个 change」，但「整个 change」止于当前 schema |

`.workflow.yaml`（`models.WorkflowMetadata`）只有 `schema` 与 `created` 两个字段。把 change 迁到另一条工作流的受支持做法就是改这里的 `schema`——于是前一个 schema 名被覆盖，历史无处可查。而 `config.py:schema_path_for` 把每个 schema 的产物根落在 `change_dir / schemas[*].path` 下，两条工作流的产物很可能根本不在同一个目录层级里，当前 schema 的节点模式匹配不到前一段的文件。

归档把问题放大一层：`_archive_one` 用 `shutil.move` 把整个 change 目录搬到 `<home>/archive/<YYYY-MM>/<change>/`。`ArchiveConflictError` 只保证**同一月份**内不重名，因此同名 change 允许在多个月份各有一份。一段工作做完、归档、下一段接着做——这是接力最常见的形态，而此时前一段的产物不在 `status` / `instructions` 能看见的任何路径下。

`history` 补不上这个缺口：它读的是 `attempts.list_rounds(change_dir)`，即**当前位置内部**的 `.attempts/round-NNN/`。回退轮次与 schema 接力、目录归档是三个正交的维度。

约束：不引入新依赖；不改既有命令的 `--json` 结构；不改归档布局；已归档的历史 change 必须立即可用（不能依赖任何需要迁移的新字段）。

**本轮（第 2 轮）的额外约束**来自 security 门禁第 1 轮的两条阻塞项：对外报告的每一条路径都必须真正收口在 workflow home 之内（不能只收口位置目录，符号链接会绕过它）；读取旧数据时任何元数据的损坏都必须降级为 warning，不能以未捕获异常终止。两者分别落为 D11 与扩展后的 D9。

## Goals / Non-Goals

**Goals:**

- 一条命令给出一个 change 名下**全部**产物的绝对路径，跨越位置（活跃 + 全部归档月份）、schema（接力过的全部工作流）、轮次（`.attempts`）三个维度。
- 对存量数据零迁移生效，包含几个月前归档的 change。
- 与 `status` 对同一 schema 的产物判断**逐字一致**——同一套解析规则，不另起一套。
- 只读：任何状态的 change 上执行都不改变磁盘。
- 清单完整性可验证：不因为 schema 被改名/删除，或文件不匹配任何模式，就让文件从清单里静默消失。
- 输出面收口可验证：报告出来的每一条路径都在 workflow home 之内，且这一点由**单一判定点**保证而非分散的调用约定。
- 读旧数据永不崩：任何一份元数据损坏都只影响它自己那部分信息，其余产物路径照常给出。

**Non-Goals:**

- 不给 `.workflow.yaml` 加 schema 历史字段（见 D1）。
- 不改 `status` / `instructions` / `history` 的响应结构。把跨 schema 能力塞进 `contextFiles` 会改变一个每轮都被调用的响应的语义与体积，风险与收益不成比例；`artifacts` 作为独立命令让调用方自己决定何时付这份成本。
- 不改 `attempts.list_rounds` 的行为（见 D12）。
- 不读产物内容、不做摘要、不判断状态。本命令只回答「有哪些文件」。
- 不做跨 workflow home 的发现——这也正是 D11 判定的边界依据。
- 不支持 `--schemas` 的通配符或 `all`/`none` 之类的关键字：省略即全部，语义已经完整。

## Decisions

### D1 — schema 归属靠探测，不靠元数据历史

**决定**：不给 `.workflow.yaml` 增加 schema 历史。改为对每个被考察 schema，用它的 artifact root + 它各节点的产物模式去匹配磁盘上真实存在的文件，匹配到即归属。

**为什么不是加字段**（考虑过 `schemas: [{name, from, to}]` 形式的历史列表）：加字段需要写迁移，而且对**已经归档**的 change 永远补不上——归档目录里那份 `.workflow.yaml` 是几个月前写的，没有任何机制能回填它。而已归档的前序产物恰恰是本需求最核心的场景。探测法零迁移，对最老的历史数据同样有效。

**代价**：归属是「对当前 schema 定义的一次投影」，不是历史事实。改动某 schema 的 `generates` 会改变历史 change 的归类结果。这个代价由 D6 的未认领文件兜住——文件不会消失，只会从「某 schema 的产物」变成「未认领」。

### D2 — 位置枚举与顺序

**决定**：位置 = 活跃目录 `<home>/<artifacts_dir>/<change>/` ∪ `<home>/archive/*/<change>/`。按「归档月份升序在前、活跃在最后」排列。

归档目录下的直接子目录**不校验**是否形如 `YYYY-MM`，月份原样报告。理由：人工整理过归档目录（比如按季度合并）不应该让产物凭空消失，而本命令的全部价值就在于不让文件消失。放宽格式不放宽安全：位置目录本身仍要过 D11 的收口判定。

顺序是契约：接力阅读的自然顺序是从最早那段读到当前那段，把活跃位置放末尾让消费方可以顺序读取而不必自己重排。

### D3 — 新模块 `artifacts.py`，CLI 只做参数与渲染

**决定**：发现逻辑全部放进新模块 `src/loopspec/artifacts.py`，以 dataclass 返回结构化结果；`cli.py` 只负责解析参数、把 dataclass 转成 JSON 载荷、以及人类可读渲染。

`cli.py` 已经 798 行，是仓库里最大的文件；把三层嵌套的发现逻辑塞进去会让它继续膨胀，也让发现逻辑无法脱离 `CliRunner` 单测。`rollback.py` / `instructions.py` / `state.py` 都是这个形状——逻辑在模块里，CLI 是薄壳。

**不复用 `_load_change_context`**：它做三件与本命令冲突的事——解析**单个** schema、要求 change 目录存在、以及 `artifact_dir.mkdir(parents=True, exist_ok=True)`。最后一条对只读命令是硬伤：查一个归档的 change 会在归档目录里创建目录。因此 `artifacts` 走自己的加载路径。

### D4 — 产物解析完全复用 `outputs.resolve_outputs`

**决定**：每个 (schema, 节点) 的产物解析调用既有的 `outputs.resolve_outputs(artifact_root, pattern)`，模式来自既有的 `outputs.node_output_patterns(node)`。

这不只是省代码：`status` 与 `instructions.contextFiles` 用的是同一对函数，复用它们就让「`artifacts` 报的路径与 `status` 报的路径一致」成为结构性事实，而不是两处实现需要人工保持同步的巧合。glob 展开、`.attempts` 排除、`state.md`/`.workflow.yaml` 保留规则也随之免费获得。

注意这两个函数都对结果调用 `.resolve()`，因此它们的返回值**可能落在 workflow home 之外**（符号链接）。收口由 D11 在输出边界统一负责，而不是靠改动这两个被 `status` 共用的函数。

### D5 — 被考察的 schema 集合

**决定**：

```
显式点名 → 就是点名的那些，加载失败即失败（schema_not_found / schema_invalid）
未点名   → config.yaml 候选（schemas[*].name ∪ {schema}）∪ 各位置 .workflow.yaml 自报的 schema
           集合内加载失败的 → 降级为 warning 并跳过
```

**为什么纳入自报但已不在候选中的 schema**：从 `config.yaml` 删掉一条候选是完全正常的维护动作，如果因此让历史 change 的产物消失，命令就不可信了。

**为什么点名失败要硬失败**：显式点名一个不存在的东西是调用方的错误。静默返回空结果会让「这个 schema 没产物」和「这个 schema 名字打错了」不可区分——对一个供 agent 消费的命令，这种歧义比报错糟得多。

**每个 schema 应用于每个位置**（笛卡尔积），而不只是自报它的那个位置：接力的前一个 schema 在后一个位置里也可能留有产物。

### D6 — 未认领文件必须报告

**决定**：遍历每个位置目录，凡真实存在、通过 `outputs` 的候选判定（即不在 `.attempts/` 下、不是 `state.md` / `.workflow.yaml`）、通过 D11 收口、且未被任何被考察 schema 认领的文件，进入该位置的 `unclassifiedFiles`。

**为什么不额外过滤隐藏文件**（考虑过排除 `.DS_Store` 之类）：任何额外的隐式过滤都在「所有产物路径」这个承诺上开一个看不见的洞。沿用 `outputs._is_artifact_candidate` 同一条规则，判断标准在整个代码库里只有一处。代价是 macOS 上的 `.DS_Store` 会作为未认领文件出现——噪音是可见的，而静默丢文件不是。

### D7 — 人类可读模式不走 `_emit`

**决定**：不带 `--json` 时用 `presentation.Presenter` 渲染分节摘要（每个位置一节：类型/月份/路径、每个 schema 的文件计数、轮次数、未认领计数、末尾总计与 warning 计数），完整路径明细只在 `--json` 里给。

`loopspec-cli` 能力已有的要求是「人类可读模式 SHALL NOT 直接转印 `--json` 载荷的字段名与原始数据结构」，而 `cli._emit` 的非 JSON 分支正是逐字段打印 `key: value`，嵌套结构会以 Python 容器字面量的形式泄漏出来。本命令的载荷是三层嵌套，用 `_emit` 会把整个 dict repr 摔在终端上。

`Presenter` 另外买到一份安全保证：它把所有值当字面量渲染（rich markup 从不解析）并把控制字符改写为可见形式，因此 change 目录里一个名为 `[red]out.md` 的产物不会被吃掉，也无法注入光标控制序列。

### D8 — 输入侧的路径安全

**决定**：两个外部输入，各自在被用作路径分量之前校验。

1. **change 名**过 `paths.is_safe_relative_path`，不合法即 `InvalidChangeNameError`。本命令要把它拼进活跃目录**与多个归档月份目录**，比现有命令多几个拼接点。
2. **`--schemas` 的每一段**过 `models.KEBAB_RE`，不合法即 `ConfigValidationError`。采纳 security 第 1 轮的非阻塞建议：schema 名在 `config.yaml` 中本就受这条正则约束（`ConfigSchemaRef.name`），用同一条规则同时排除 `../../etc`、绝对路径，以及 `a/b` 这类虽落在 home 内、但绕过了候选命名约定的取值。比「安全相对路径」更严且与既有约束一致。

现有 `paths.change_root` 只对 `artifacts_dir` 做了安全校验，change 名是直接拼的（`artifacts_root(...) / change_name`），`status` 等命令靠 `is_dir()` 兜底。新命令不沿用这个薄弱点。

### D11 — 输出侧的路径收口：单一判定点，逃出即降级

**决定**（第 1 轮阻塞项 (a) 的修复）：新增一个内部判定 `_contained(home_resolved, path) -> bool`，语义为「`path` 解析后等于 home 或位于 home 之下」。**所有**对外报告的路径，在进入任何返回结构之前都必须通过它——共三个入口：

| 入口 | 路径来源 | 为什么会逃出 |
| --- | --- | --- |
| D4 的 schema 产物 | `outputs.resolve_outputs`（内部 `.resolve()`） | 声明的产物本身是符号链接，或 glob 命中符号链接 |
| D12 的轮次文件 | `.attempts/round-NNN/` 目录遍历 | 轮次目录里的符号链接 |
| D6 的未认领文件 | 位置目录全量遍历 | 目录内任意符号链接，如 `notes.md -> /etc/shadow` |

逃出的路径**不报告**，并计一条 warning。warning 只指名它相对于 change 目录的名字，不打印解析后的目标——否则修复本身又把 home 外的路径打印了出来。

**为什么是「跳过 + warning」而不是整体失败**：与 D9 的降级风格一致。一个被符号链接污染的 change 目录仍然应该能列出它其余的真实产物；让整条查询失败会把一个局部异常放大成完全不可用。

**为什么放在输出边界而不是各调用点**：第 1 轮阻塞项的根因正是「检查只覆盖了位置目录」这种分散式收口——三个入口里漏掉任何一个，声明就不成立。单一判定点让「输出的每条路径都在 home 内」成为可以逐点核对的结构性事实，也让后续新增入口时漏检查这件事更容易在评审中被看见。

**与 D2 的关系**：位置目录本身仍然要过同一个判定（一个指向 home 外的 `archive/2026-07` 符号链接会被整体拒绝），因此放宽月份目录名的格式校验不会放宽安全边界。

### D9 — 元数据损坏一律降级为 warning（本轮扩展到 `_meta.yaml`）

**决定**（第 1 轮阻塞项 (b) 的修复）：本命令读取的**每一份**元数据都按同一模式处理——缺失、无法解析、或解析出来的顶层不是映射，都降级为一条 warning 并按「该份元数据不可用」继续，绝不让整条查询失败。覆盖两份：

- **位置的 `.workflow.yaml`**：`config.read_metadata` 会抛 `ConfigValidationError`；缺失或损坏 → 该位置自报 schema 为空。
- **轮次的 `.attempts/round-NNN/_meta.yaml`**：缺失或损坏 → 该轮的 gate/verdict 为空，但**该轮目录下的文件仍然照常报告**（见 D12）。

本命令的价值恰在于读取旧的、可能已归档的位置。一份几个月前写的、格式已过时的元数据不应该让当前查询失败——产物路径本身仍然准确可用。硬失败会让这个命令在最需要它的场景下最不可用。

### D12 — 轮次收集自己实现，不改也不复用 `attempts.list_rounds`

**决定**：`artifacts.py` 自己遍历 `.attempts/round-*`，而不调用 `attempts.list_rounds`。

两个独立理由：

1. **它会吞掉没有 `_meta.yaml` 的轮次目录**（`if not meta_path.is_file(): continue`）。对 `history` 那是合理的——没有元数据就没有历史可讲；但对本命令那意味着**丢文件**，与 D6 的完整性目标直接冲突。缺元数据的轮次仍要报告，轮次号从目录名解析，gate/verdict 留空。
2. **它对损坏的元数据没有防护**：`yaml.safe_load` 之后直接 `meta.get(...)`，顶层不是映射时抛 `AttributeError`，格式非法时抛 `yaml.YAMLError`——都不是 `LoopspecError`，会绕过 `_fail` 的统一错误契约以 traceback 终止。

**为什么不就地加固 `attempts.list_rounds`**：它同时被 `history` 与 `instructions.priorAttempts` 复用，改它的返回集合（开始包含无元数据的轮次）会连带改变那两条已发布的响应契约——而本变更的 Non-Goals 明确不动它们。加固点因此留在 `artifacts.py` 一侧；`list_rounds` 自身的健壮性是一个独立问题，记为后续跟进而非本变更的范围。

### D10 — `--schemas` 的解析

**决定**：逗号分隔，逐段 `strip()`，丢弃空段，去重并保留首次出现顺序——与 `tools_cli.resolve_tools_arg` 的形状一致。但**不**支持 `all` / `none` 关键字：省略即全部，而「一个 schema 都不考察」没有任何意义。

取值给了但 strip 后一段不剩（`--schemas ""`、`--schemas ","`）→ `ConfigValidationError`。这与「省略」必须区分开：调用方显式传了参数说明它有意图，静默当成「全部」会掩盖上游的变量拼接 bug。每一段还要过 D8 的 `KEBAB_RE`。

### 安全面自查（供 security 门禁）

- **输入面**：两个外部输入，均在用作路径分量前校验——change 名过 `is_safe_relative_path`，`--schemas` 每段过 `KEBAB_RE`（D8）。
- **输出面**：报告出来的每一条路径都经过 D11 的单一收口判定，解析后逃出 workflow home 的一律不报告并计 warning；warning 文本本身也不打印 home 外的目标路径。位置目录同样经过该判定。这条声明与实际机制一致：三个路径入口（schema 产物、轮次文件、未认领文件）逐一接入同一判定点。
- **写入面**：无。命令为只读，且刻意绕开 `_load_change_context` 的 `mkdir`（D3），由前后目录快照对比的测试守住。
- **不受信输入的反序列化**：两份元数据均经 `yaml.safe_load`（无任意对象构造），且缺失/非法/顶层非映射三种情况全部降级为 warning（D9），不存在未捕获异常路径。
- **注入面**：无外部命令执行、无 SQL、无模板渲染。终端输出经 `Presenter` 转义（D7）。
- **敏感数据**：只输出路径，从不读取产物内容，因此 change 目录内即便存在敏感文件也不会泄露其内容。
- **authn/authz**：不涉及。纯本地文件系统读取，权限由操作系统决定。
- **遍历成本**：D6 要对每个位置做一次全目录遍历。位置数受归档月份数限制，change 目录是文档规模，不构成放大风险。

## Risks / Trade-offs

- **[归属会随 schema 定义漂移]** → 改 `generates` 会让历史 change 的产物换归属。由 D6 兜底：文件从「某 schema 的产物」变成「未认领」，绝不消失。文档在命令小节中明确说明归属是投影而非历史事实。
- **[多 schema 认领同一文件]** → 两个都不设 `path` 又都声明 `proposal.md` 的 schema 会各自认领同一文件。如实报告两处认领 + 一条 warning，汇总清单去重。不替调用方猜归属。
- **[符号链接指向 home 外的产物会被静默跳过]** → D11 的自觉取舍。这类链接在 change 目录里本就不是正常用法，而 warning 会指名是哪个文件被跳过，因此「静默」只限于路径本身不出现在清单里，事实本身仍被报告。
- **[`list_rounds` 的健壮性问题仍在]** → D12 只在 `artifacts.py` 一侧加固，`history` / `instructions` 遇到损坏的 `_meta.yaml` 仍会以 traceback 终止。这是本变更范围外的既有缺陷，明确记为后续跟进，不在此顺手改动一个被两条已发布响应契约共用的函数。
- **[响应体积]** → 三层嵌套，位置 × schema × 节点。对文档规模的 change 可接受；人类可读模式（D7）默认给聚合计数而不是全量路径，避免终端被淹。
- **[`.DS_Store` 等噪音进入未认领清单]** → D6 的自觉取舍：可见的噪音优于静默丢文件。
- **[新增一处需与文档同步的面]** → `tests/test_docs_consistency.py` 会自动要求新命令有小节、每个 `--option` 出现在本小节、两语言首列标识符一致，漏写在 `make test` 阶段即失败。
- **[与 `status` 的产物判断漂移]** → 由 D4 结构性排除：两者调用同一对函数，不存在两份实现。唯一的差异是 D11 会额外剔除逃出 home 的路径，这是有意为之的收紧，并由 warning 明示。

## Migration Plan

纯新增，无迁移。命令上线即对全部存量 change（含已归档）可用；不改任何磁盘布局与既有响应结构，回滚等价于移除该命令。

## Open Questions

- `attempts.list_rounds` 对损坏 `_meta.yaml` 的加固（影响 `history` 与 `instructions.priorAttempts`）留作后续独立变更，本次不动。
