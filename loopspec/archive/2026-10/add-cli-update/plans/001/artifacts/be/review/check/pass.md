---
verdict: PASS
summary: "返工后复审：上一轮的阻塞问题（安装阶段 OSError 未映射）已修复，并有对应测试；状态逻辑、checksum 解析、重定向、临时文件生命周期、JSON 输出纯净性均正确，无阻塞问题"
---

# 后端代码审查：通过

## 审查输入

- 轮次 `001.1:be/review/check:2`，基线 `b1d59372a81aae5dabef4a4a39f7403a440c0e17`，scopeDigest `d129a2e07303…`。没有 warnings。
- 路径：`src/loopspec/cli.py`、`src/loopspec/errors.py`、`src/loopspec/self_update.py`、`tests/test_self_update.py`、`tests/test_workflow_cli.py`。
- 由独立审查 agent 读代码，结论经人工核实；测试结果引用本轮之前 be/tests/check 第 2 轮（同一 scopeDigest）的 `make test` 1141 passed。

## 审查要点

- **上一轮阻塞问题（attempt 1）**：`run_update` 安装段中，`installer` 在 `try` 前初始化为 None。暂存 wheel 时出现 `OSError` 报 `update_install_failed`；安装器启动时出现 `FileNotFoundError` 报 `update_installer_missing`；其他 `OSError` 报 `update_install_failed`。`pick_installer` 抛出的是 `LoopspecError`，不会被 `except OSError` 吞掉；用 `from None` 截断异常链。已修复，并有参数化测试覆盖。
- **正确性**：
  - 未固定版本且版本相同时不下载；
  - `--check` 只读，固定版本时也成立；
  - 固定版本总是安装；
  - checksums 只认两列的行，去掉 `*` 前缀，精确匹配恰好一行，digest 为 64 位 hex；
  - 缺少条目时在下载 wheel 之前失败；
  - 安装器退出后才清理临时 wheel。
- **重定向**：`_HttpsOnlyRedirectHandler` 替换了默认处理器，抛出的 `URLError` 会被 `https_fetch` 映射；`urlsplit` 会把 scheme 转成小写，相对重定向由 urllib 先 join 再判断。
- **错误处理**：`https_fetch` 的网络异常统一映射，超出大小上限时抛出的 `UpdateFetchFailedError` 不会被后面的 except 重复捕获；所有失败路径都走 `{error,message,fix}`，退出码为 1。
- **JSON 输出**：stdout 只输出一个 JSON 文档，安装器的输出走 stderr，测试已验证 runner 绑定。
- **一致性**：与 install.sh 一致（先 uv 后 pipx、先校验后安装、仅 https、版本先校验再使用）；符合仓库的错误类与文档一致性约定。
- **测试覆盖**：60 个用例覆盖解析、状态、校验、安装器、网络、CLI 等路径。

## 剩余风险

- 如果 `TemporaryDirectory` 清理阶段出现 `FileNotFoundError`，会被报成 `update_installer_missing`，概率极低，可接受。
- 重定向只单测了 `redirect_request`，没有基于真实 `OpenerDirector` 的集成测试。
- 版本只做字符串相等比较（不引入 `packaging`），installer 在下载后才检测（与 install.sh 一致），`VERSION_PATTERN` 与 install.sh 一样偏宽：均为已知并接受的取舍。
