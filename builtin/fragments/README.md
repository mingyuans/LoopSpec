# 项目路径映射

内置代码审查 Fragment 的路径只是起始示例：`src/frontend/**`、`frontend/**`、`tests/frontend/**` 和对应后端目录。

每个 Fragment 是一个自包含目录：`<name>/fragment.yaml` 为定义，同目录下的 `<node>.instruction.md`、`<node>.template.md`（产物模板）与 `<node>.pass.md`/`<node>.fail.md`（Gate 模板）为它引用的资源。资源路径只能指向本目录内的文件。

启用代码模板前，按项目实际目录修改相关 Gate 的 `evidence.paths`（`backend-tests`、`frontend-tests`、`backend-pr-review`、`frontend-pr-review`、`security-review`），同时修改 `change-assurance/rules.yaml` 的 `paths`、必需能力与 `repair_fragment`。
测试与审查能力必须覆盖实际修改路径；模板不会自动推断业务代码归属。未知路径会阻止最终保障通过。

同一路径命中多条保障规则时，要求取并集。不要把业务目录配置为生成目录，也不要扩大工作流控制目录排除范围。

`loopspec init` 只补齐缺失的文件，不覆盖已有内容。已有工作区升级后会得到新的模板文件，但不会修改已有的 `fragment.yaml`；如需使用新模板，在对应节点上手动加入 `template` 或 `gate.templates` 引用。
