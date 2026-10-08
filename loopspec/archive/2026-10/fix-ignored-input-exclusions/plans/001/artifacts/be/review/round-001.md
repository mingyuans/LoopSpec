---
verdict: FAIL
summary: "assurance 报告摘要拼接告警路径没有长度上限，长路径会让 FAIL 报告超过 FailureReport 的 16384 字符限制，导致 change status 无法解析"
---

# 后端代码审查：需要修改

## 阻塞问题
- `src/loopspec/workflow_assurance.py` 的 `warning_text()` 把最多 20 个被忽略路径原样拼进系统报告的 `summary`，没有长度上限。`FailureReport.summary` 的 `max_length=16384`（`workflow_models.py`），而单个 Git 路径可以有数千字符。20 个长路径加上 FAIL 文案就会超限，此后 `change status` 解析 `fail.md` 时报 `invalid_verdict`，status、rollback、archive 全部不可用，而且这份报告由系统写入，用户无法手工修正。需要保证告警文本在任何输入下都不让 `summary` 超限，并补一个长路径的回归测试。

## 审查输入
- 轮次 `001.1:be/review/check:1`，基线 `7531fb87`，scopeDigest `1d4bd78b2170…`，9 个文件
- 本轮 `warnings` 为空

## 建议修复方向
- 给告警文本设一个远小于 16384 的总长度上限，超出时截断并注明剩余条数；`ignoredTotal` 仍然如实给出。
- 非阻塞：`_exclusions()` 中 `cache = ".cache" if home in (None, ".") else ...` 的 `None` 分支不会被用到（后面有 `home is not None` 判断），可以顺手简化。
