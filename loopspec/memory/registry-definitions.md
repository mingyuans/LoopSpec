# registry 模式下定义文件的位置

适用时机：代码或 agent 需要知道 fragment/profile 文件在磁盘上的位置时（registry 模式下项目内没有 `fragments/`、`profiles/`）。

- 定义文件的读取与定位都要经过 `definition_bundle(home)`：`read()` 校验路径与 registry 哈希，`location()` 给出实际位置（registry 定义在已校验的全局快照，其余在 home）。只能对定义内的文件路径（`fragments/<name>/<file>`）取位置；`fragments/<name>` 这个目录路径不被 `owning_key` 识别为 registry 定义，会被当成 home 下的路径。要取 fragment 目录，先定位其中的文件再向上取父目录。来源：fragment-dir（2026-11-20，实现时发现并修正，见 `workflow_runtime.fragment_paths`、`tests/test_fragment_paths.py`）。
- fragment 指令会用相对路径（`references/…`、`scripts/…`）或只写文件名引用同目录下的辅助文件；`node instructions` 的 `fragmentDir` 给出该目录的绝对路径，只写文件名的文件可能在 `references/` 等子目录。`fragment` 字段是 Plan 实例 id，不是 fragment 名（用 `fragmentName`）。来源：同上；aftership-channels 快照 7b6cc1b 实测，LLM E2E「指令引用的辅助文件按 fragmentDir 在注册表快照中找到」通过。
