---
verdict: PASS
summary: "7 处写入统一改为 write_yaml，读取与证据逻辑未动；剩余 write_json 只用于真正的 .json 文件；新用例覆盖格式与旧文件兼容，986 passed"
---

# 后端代码审查：通过

## 审查输入

- 轮次：`001.1:be/review/check:1`；基线 `21f17e1789cd2b114e56006000f5c0b7e138a27c`；scopeDigest `d43569a0…`；warnings：无。
- 路径：`src/loopspec/workflow_assurance.py`、`src/loopspec/workflow_evidence.py`、`tests/test_gate_file_format.py`。

## 审查要点

- 正确性：`workflow_evidence.py` 4 处、`workflow_assurance.py` 3 处由 `write_json` 改为 `write_yaml`，参数（路径、`model_dump()` / 诊断 dict、`exclusive=True`）逐一未变；导入同步替换，无残留未用导入。
- 完整性：全仓剩余 `write_json` 只有 `registry_sync.py` 写 `.cache/.../plan.json`，扩展名与内容一致，不在本次范围。
- 兼容：读取仍走 `parse_yaml()`；Y5 把 `begin.yaml` / `evidence.yaml` 改回旧版紧凑 JSON 后状态仍为 done、`gate record` 仍成功。
- 边界：`exclusive=True` 的 round 文件在 `write_yaml` 中同样经 `atomic_write(exclusive=True)`，防覆盖语义不变。
- 测试覆盖：Y1（begin + round）、Y2（代码证据）、Y3+Y4（保障三文件 + 全目录无 JSON 单行）、Y5（旧文件兼容）；`make test` 986 passed。
- 可维护性：改动为纯替换，无新抽象。

## 剩余风险

- `write_yaml()` 在对象被重复引用时会写出 YAML 别名并被 `StrictLoader` 拒绝，属既有约束（见安全审查），当前载荷不触发。
- `write_json()` 现只剩一个调用方，可在后续评估是否保留。
