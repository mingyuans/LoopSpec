---
verdict: PASS
summary: "返工后复审：版本白名单、仅 https（含重定向）、大小与超时上限、强制 SHA256、无 shell 子进程均保持不变；新增的 OSError 映射不泄露敏感信息，未发现阻塞问题"
---

# 后端安全审查：通过

## 审查输入

- 轮次 `001.1:be/security/check:2`，基线 `b1d59372a81aae5dabef4a4a39f7403a440c0e17`，scopeDigest `d129a2e07303…`。没有 warnings。
- 路径：`src/loopspec/cli.py`、`src/loopspec/errors.py`、`src/loopspec/self_update.py`、`tests/test_self_update.py`、`tests/test_workflow_cli.py`。

## 检查项

- **注入**：安装器仍通过 `subprocess.run(argv_list)` 调用，没有 `shell=True`、`os.system`、`eval` 或 `exec`；新增的测试也断言了不使用 shell。argv 只包含常量和由已校验版本号组成的临时路径。CLI 中新增的提示文案 `loopspec update --version X` 只用于输出；能走到这里说明 `X` 已经通过版本白名单。
- **输入校验**：`--version` 与 checksums 中的版本都要经过 `VERSION_PATTERN.fullmatch`（仅 ASCII 数字，拒绝换行）；digest 必须是 64 位 hex，且恰好一行精确匹配。
- **传输**：起始 URL 与重定向目标都必须是 https；使用默认 TLS 证书校验；30 秒超时；分块读取并设上限（64 KiB / 50 MiB）。
- **完整性**：用 `hmac.compare_digest` 比较 SHA256；安装的是已校验的本地文件；没有跳过开关；缺少 checksum 条目时不下载 wheel。
- **路径穿越**：wheel 写在 `TemporaryDirectory`（0700）内，文件名由已校验版本号拼成，用完即删。
- **敏感信息与错误处理**：本轮新增的 `OSError` 映射只输出 `strerror`（例如 “No space left on device”）或安装器名，最坏情况包含本地临时路径。不读取环境变量，不回显响应体；异常用 `from None` 截断，traceback 不会泄漏到输出。
- **认证/授权、反序列化、数据库**：不涉及。
- **依赖来源**：只用标准库，`pyproject.toml` 与 `uv.lock` 未改动。

## 剩余风险

- 信任边界与 install.sh 相同：没有签名校验，不能防 Release 本身被攻破；文档已说明。
- `uv`/`pipx` 按 PATH 解析；系统代理设置会被遵循（TLS 仍校验证书）。
- 远端返回的非法版本串经 `repr` 转义后回显，最长约 64 KiB，只影响可读性。
