# 需求记录

需求背景、跨 Plan 的决策与更替原因。
人与 LLM 可直接编辑；`loopspec change status` 原样输出全文，引擎不解析。

## 背景

<!-- 用户原始诉求、要解决的问题、现状与触发原因。由 new skill 在创建 Plan 前填写。 -->

用户已在 workflow home 中配置好 fragments/profiles（手工定制或经 registry 同步），之后只想刷新 AI 工具的 loopspec skills，于是重新执行 `loopspec init`。但 `init` 会无条件调用 `install_resources`（`src/loopspec/workflow_resources.py`），把内置 fragments/profiles 写回 workflow home，影响用户已有的配置，属于非预期行为。

现状：`init` 每次都会执行 `install_resources`；它按文件补齐缺失的内置资源（已存在的同名文件不改写），因此用户删除/重命名过的内置 Fragment、Profile 或其中的文件会被重新写回，与用户定制或 registry 同步的目录混在一起。

## 目标 / 非目标

<!-- 本需求的范围边界，明确不做的事。 -->

目标：
- `loopspec init` 检测到 workflow home 下 `fragments/` 或 `profiles/` 已存在（且非空）时，不再静默写入内置资源，而是先向用户确认是否更新。
- 交互终端：提示确认，默认“不更新”；用户确认后才执行原有的资源安装逻辑。
- 非交互 / `--json`：不能阻塞等待输入，默认跳过资源更新，并在输出中明确说明已跳过；提供显式 CLI 选项（如 `--update-resources`）在非交互场景下强制更新。
- 首次 init（目录不存在或为空）行为保持不变：直接安装内置资源。
- skills/commands 刷新与 hooks 安装行为不受影响。
- JSON 输出与终端摘要能体现资源是否被跳过。

非目标：
- 不改变 `install_resources` 自身的“仅补齐缺失文件”语义，也不新增强制覆盖为内置版本的模式。
- 不改动 registry 同步（`update-registry`）流程、`config.yaml` 生成逻辑。

## 关键决策

<!-- 每条一行：- YYYY-MM-DD（确认人）：决策内容；理由。
只追加；推翻旧决策时新增一条并注明取代哪条。 -->

- 2026-10-12（用户）：已存在 fragments/profiles 时交互默认 N、非交互/--json 默认跳过、新增 `--update-resources` 强制更新；保留 install_resources 仅补齐缺失文件的语义。

## 参考

<!-- 相关 issue / PR / 已归档 Change。 -->

## Plan 记录

<!-- 引擎在此之后追加 Plan 归档事件；LLM 可在事件行下补充更替原因。 -->
