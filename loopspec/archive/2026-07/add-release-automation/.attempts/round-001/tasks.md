> 标注说明：**[SEC]** 标记涉及外部输入、凭据、权限或第三方依赖的任务，供 `security` 节点重点审阅。

## 1. 版本号单一入口

- [ ] 1.1 新增 `scripts/check_version.py`：用 `tomllib` 读 `pyproject.toml` 的 `project.version`，用 `ast` 解析 `src/loopspec/__init__.py` 的 `__version__`（不 import 该包）；仅用标准库，不新增依赖
- [ ] 1.2 **[SEC]** 在该脚本中加入版本号格式校验，正则 `^[0-9]+\.[0-9]+\.[0-9]+([._-]?(a|b|rc|alpha|beta|dev|post)[0-9]+)?$`；非法即非零退出，防止畸形字符串被拼进 tag/URL
- [ ] 1.3 一致且合法时把版本号打到 stdout 并以 0 退出；漂移或非法时把两处实际值打到 stderr 并非零退出
- [ ] 1.4 新增 `tests/test_check_version.py`：覆盖一致、漂移、格式非法、以及"未安装依赖也能取值"（不 import 包）四个场景

## 2. 安装脚本骨架与安全形态

- [ ] 2.1 新增 `install.sh`（`#!/bin/sh` + `set -eu`），全部逻辑封装进函数，文件末尾才调用入口函数——防止 `curl | sh` 传输中断时执行半个脚本
- [ ] 2.2 **[SEC]** 用 `mktemp -d` 创建临时目录（不使用固定可预测路径），`trap` 在 `EXIT`/`INT`/`TERM` 时清理
- [ ] 2.3 **[SEC]** 统一下载函数：`curl -fsSL --proto '=https' --tlsv1.2`，仅走 HTTPS、禁止协议降级、失败返回非零；确认脚本中无 `eval`、无 `sudo`、不写系统级目录
- [ ] 2.4 `chmod +x install.sh`

## 3. 安装脚本的版本解析与输入校验

- [ ] 3.1 **[SEC]** 实现版本号格式校验函数（与 1.2 同一正则），并对 `LOOPSPEC_VERSION` 与 API 提取出的 `tag_name` 分别调用；校验通过后才允许参与 URL/文件名拼接
- [ ] 3.2 `LOOPSPEC_VERSION` 已设置时直接使用该值，不发起 GitHub API 请求
- [ ] 3.3 **[SEC]** 未设置时请求 `https://api.github.com/repos/mingyuans/LoopSpec/releases/latest`，用 `sed` 抽取 `tag_name`（不依赖 `jq`），剥掉 `v` 前缀后走 3.1 的校验
- [ ] 3.4 查询失败（网络错误 / API 速率限制）时非零退出，并提示可用 `LOOPSPEC_VERSION=x.y.z` 跳过该查询
- [ ] 3.5 用校验后的版本号拼出 wheel 与 `checksums.txt` 的下载 URL（`.../releases/download/v$V/loopspec-$V-py3-none-any.whl`）

## 4. 安装脚本的完整性校验与安装

- [ ] 4.1 **[SEC]** 把 wheel 与 `checksums.txt` 下载到临时目录，按 `command -v` 探测 `sha256sum` 或 `shasum -a 256` 校验 wheel 的 SHA256
- [ ] 4.2 **[SEC]** 校验失败即中止并非零退出；两种校验工具都不存在时同样中止非零退出——不实现任何跳过校验的开关、环境变量或降级路径
- [ ] 4.3 **[SEC]** 安装后端按 `uv tool install --force` → `pipx install --force` 顺序探测，参数传入**本地已校验的 wheel 路径**而非远端 URL（否则校验的字节与安装的字节不同源）
- [ ] 4.4 **[SEC]** 两种后端都缺失时打印 uv 的官方安装命令并非零退出：不自动替用户安装 uv/pipx，不回退到 `pip install --user`
- [ ] 4.5 安装后执行 `loopspec version` 自检；`command -v loopspec` 找不到时打印 PATH 补全提示（uv 场景另提 `uv tool update-shell`）但仍以 0 退出

## 5. GitHub Actions 工作流

- [ ] 5.1 新增 `.github/workflows/release.yml`：`on.push.branches: [main]` + `on.workflow_dispatch`；**[SEC]** 顶层声明 `permissions: contents: read`
- [ ] 5.2 **[SEC]** 所有第三方 action pin 到 commit SHA 并附版本注释：`actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1`（v7.0.1）、`astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9`（v9.0.0）
- [ ] 5.3 `verify` job：checkout → setup-uv（开启 cache）→ `python scripts/check_version.py` → `uv sync` → `ruff check` + `mypy` → `pytest` → `sh -n install.sh` + `shellcheck install.sh` → `uv build`
- [ ] 5.4 **[SEC]** `release` job：`needs: verify`，单独声明 `permissions: contents: write`（全工作流唯一持写权限者）；仅使用自动注入的 `GITHUB_TOKEN`，不声明任何额外 secret
- [ ] 5.5 `release` job 用 `gh release view "v$VERSION"` 判定：已存在则往 `$GITHUB_STEP_SUMMARY` 写明"跳过 + 版本号"并以**成功**结束；查询本身出错（非"明确不存在"）时失败，不误判为已存在/不存在
- [ ] 5.6 未发布时重新 `uv build`，用 `sha256sum` 对自己产出的 wheel 与 sdist 生成 `checksums.txt`（格式需可被 `sha256sum -c` / `shasum -a 256 -c` 直接校验）
- [ ] 5.7 **[SEC]** 用预装的 `gh release create "v$VERSION" dist/* checksums.txt --target "$GITHUB_SHA" --title "v$VERSION" --generate-notes` 发布；不引入第三方发布 action，不使用 artifact 上传/下载 action 跨 job 传产物
- [ ] 5.8 检查工作流全部步骤不把 token 写入日志、文件或命令行参数

## 6. 本地任务入口

- [ ] 6.1 `Makefile` 新增 `release-dry-run`：跑 `scripts/check_version.py` → `sh -n install.sh` →（`shellcheck` 存在则跑，缺失则打印提示并跳过、不失败）→ `uv build`
- [ ] 6.2 把 `release-dry-run` 加进 `.PHONY`

## 7. README

- [ ] 7.1 重写 "Install" 一节为面向用户：一行式 `curl -fsSL <raw install.sh URL> | sh`；"先下载、审阅、再执行"的两步替代命令；手动 `uv tool install` / `pipx install`；更新（同一条命令）；卸载（`uv tool uninstall loopspec` / `pipx uninstall loopspec`）；Windows 用户直接用 `uv tool install`
- [ ] 7.2 新增 "Releases" 一节：说明发布由版本号驱动（抬版本号才发）、Release 资产清单（wheel / sdist / `checksums.txt`）、**[SEC]** 以及仓库设置前置条件（`Settings → Actions → General → Workflow permissions` 需允许 `Read and write`，否则 `gh release create` 会 403）
- [ ] 7.3 把 `make install` 移到 "Development" 一节，并补上 `make release-dry-run`

## 8. 验证

- [ ] 8.1 本地跑 `make lint` 与 `make test`，全绿
- [ ] 8.2 本地跑 `make release-dry-run`，确认版本一致性校验与构建通过；另手动制造一次版本漂移确认它会失败，然后改回
- [ ] 8.3 用 `sh -n install.sh` 校验语法；`shellcheck` 可用时跑一遍并修掉告警（或加带理由的行内 disable）
- [ ] 8.4 交叉核对 workflow 与 `install.sh` 中的资产文件名与 spec 的命名契约一致（`loopspec-<version>-py3-none-any.whl` / `loopspec-<version>.tar.gz` / `checksums.txt`）
