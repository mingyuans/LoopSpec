---
verdict: PASS
summary: "update 命令的版本输入白名单校验、仅 https（含重定向）、大小与超时限制、强制 SHA256 校验、无 shell 子进程均已落实，未发现阻塞问题"
---

# 后端安全审查：通过

## 审查输入

- 轮次 `001.1:be/security/check:1`，基线 `b1d59372a81aae5dabef4a4a39f7403a440c0e17`，scopeDigest `c5c49cb7ee09…`。
- 路径：`src/loopspec/cli.py`、`src/loopspec/errors.py`、`src/loopspec/self_update.py`、`tests/test_self_update.py`、`tests/test_workflow_cli.py`。没有 warnings。

## 检查项

- **命令注入**：安装器通过 `subprocess.run(argv_list, check=False)` 调用，未使用 `shell=True`、`os.system`、`eval` 或 `exec`（grep 确认）。argv 中唯一的外部成分是 wheel 路径，它由 `TemporaryDirectory` 与已校验的版本号拼成。
- **输入校验**：`--version` 与 checksums 中解析出的版本都经过 `VERSION_PATTERN.fullmatch` 才进入 URL、文件名或 argv。实测 `[0-9]` 只匹配 ASCII（全角数字被拒），`fullmatch` 也拒绝末尾的 `\n`。单测覆盖了 `;`、`..`、`$(id)`、`$IFS`、空串。digest 必须是 64 位 hex，并与 wheel 文件名精确匹配且恰好一行。
- **传输安全**：起始 URL 必须是 https；`_build_opener()` 实测只挂载 `_HttpsOnlyRedirectHandler`（替换默认重定向处理器），重定向目标不是 https 时抛错，因此 `file://`、`ftp://`、`http://` 都无法经重定向到达。TLS 使用 urllib 默认上下文，会校验证书。超时 30 秒；分块读取，超过上限（64 KiB / 50 MiB）立即中止，不会无界占用内存。
- **完整性**：用 `hmac.compare_digest` 比较 SHA256；安装的是已校验的本地临时文件，而不是让安装器自己去拉 URL；没有跳过校验的选项。缺少 checksum 条目时在下载 wheel 之前就失败。
- **路径穿越**：写入路径固定为 `TemporaryDirectory()/loopspec-<已校验版本>-py3-none-any.whl`，版本号白名单不含 `/`、`..`，不可能写到目录之外；临时目录权限为 0700，用完即删。
- **敏感信息**：不读取环境变量（代码中没有 `environ`），请求不携带任何本地信息。错误消息只包含常量拼接的 URL、HTTP 状态码，或用 `repr` 转义后的版本串，不回显响应体，也不会把终端控制字符原样输出。
- **认证/授权、反序列化、数据库**：不涉及。响应只作为 UTF-8 文本按行切分或作为字节计算哈希，没有 pickle、yaml 等反序列化。
- **依赖来源**：只用标准库（`urllib`、`hashlib`、`hmac`、`subprocess`、`tempfile`），没有新增第三方依赖；`pyproject.toml` 与 `uv.lock` 未改动。

## 剩余风险

- **信任边界与 install.sh 相同**：checksums.txt 和 wheel 来自同一个 GitHub Release，能防传输损坏和被替换，不能防 Release 或仓库本身被攻破（没有签名校验）。已在中英文文档中如实说明。
- **PATH 解析**：`uv`/`pipx` 按 PATH 解析，与 install.sh 一致。PATH 被篡改的环境不在本命令的防护范围内。
- **代理**：urllib 会遵循系统的 `https_proxy` 等代理设置；代理链路上仍校验 TLS 证书，属预期行为。
- **非法版本串回显**：远端可构造长达 64 KiB 的非法版本串，被 `repr` 转义后回显在错误中，只影响可读性，不构成注入。可后续截断，不阻塞。
