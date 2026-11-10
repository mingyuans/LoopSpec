# 发布规范

> 覆盖范围：LoopSpec 的版本号规则、如何发布正式版与 beta 版、CI 检查什么，以及用户分别会拿到什么。
> 适用读者：准备打 tag 发版或修改版本处理逻辑的维护者与 AI Agent。
> 语言：**中文** · [English](../en/release.md)

发布只由推送 tag 触发，没有别的途径：推送到 `main` 只会运行检查和构建，不会发布。

## 版本规则

tag 只有两种合法形态，其他 tag 都会被 CI 拒绝，包括 `v1.1.4-beta1`、`v1.1.4b0`、`v1.1.4-rc` 和 `v1.1.4-my-branch`。

| 类型 | Tag | 包版本 | 下一个版本 |
| --- | --- | --- | --- |
| 正式版 | `vX.Y.0` | `X.Y.0` | 递增 Y，Z 归零：`v1.2.0` 之后是 `v1.3.0`。 |
| Beta | `vX.Y.Z-beta` | `X.Y.Zb0` | 递增 Z：`v1.1.4-beta` 之后是 `v1.1.5-beta`。 |

- beta 的包版本是它的 PEP 440 形式。tag 为 `v1.1.4-beta` 时，`loopspec version` 输出 `1.1.4b0`，产物为 `loopspec-1.1.4b0-py3-none-any.whl` 和 `loopspec-1.1.4b0.tar.gz`；GitHub 上的 tag 仍保留 `-beta` 写法。
- 正式版的补丁位保持为 `0`。CI 接受任意 `vX.Y.Z`，所以这条规则由本规范约束，而不是由工作流强制；非零补丁位只留给等不到下一个次版本的紧急修复。
- `v1.1.1` 到 `v1.1.3` 早于这套规则，保持原样。
- beta 的版本必须高于最新正式版，`loopspec update --beta` 才会选中它：Z 要大于最新正式版的补丁位（或者 Y 更高）。

示例序列：

```text
v1.1.3         stable (predates the rules)
v1.1.4-beta    beta, package 1.1.4b0
v1.1.5-beta    beta, package 1.1.5b0
v1.2.0         next stable
```

tag 是唯一声明版本的地方。`pyproject.toml` 把版本标为 `dynamic`，由 `hatch_version.py` 在构建时依次解析：设置了 `LOOPSPEC_BUILD_VERSION` 就用它（CI 根据校验过的 tag 设置），否则用当前提交上的 tag（`-beta` tag 映射为 `b0`），否则在从已发布的 sdist 构建时用 `PKG-INFO` 中的 `Version:`，都没有时为 `0.0.0.dev0`。不需要提交版本号变更。

## 发布步骤

1. 把改动合入 `main`，确认 `main` 上的检查全部通过。
2. 按上面的规则确定 tag。用 `git tag --list 'v*'` 和 Releases 页面查看已有版本。
3. 对该 tag 做构建预检。它会构建该 tag 将要发布的产物并断言文件名：

   ```bash
   make release-dry-run TAG=v1.2.0
   make release-dry-run TAG=v1.1.4-beta   # expects loopspec-1.1.4b0-*
   ```

4. 在 `main` 的提交上打 tag 并推送。推送 tag 这一步才会发布：

   ```bash
   git checkout main && git pull
   git tag v1.2.0
   git push origin v1.2.0
   ```

5. 在 GitHub Actions 中跟进发布工作流，直到结束。
6. 核对 Release 页面：挂有三个产物；正式版标为 **Latest**；beta 标为 **Pre-release**，Latest 仍在上一个正式版上。

## CI 做了什么

发布工作流在推送 `v*` tag 时运行，会：

- 校验 tag 形态，推导包版本（`X.Y.Z`，beta 为 `X.Y.Zb0`）以及是否为预发布；
- 运行 lint 和测试；
- 要求被打 tag 的提交可从 `main` 到达；
- 该 tag 的 Release 已存在时拒绝运行；
- 构建 wheel 和 sdist，断言它们按包版本命名，并生成 `checksums.txt`；
- 创建 GitHub Release：正式版带 `--latest`，beta 带 `--prerelease --latest=false`，因此 beta 永远不会被标为 Latest。

正式版与 beta 走同一套构建流程，发布同样的三个产物：

- `loopspec-<version>-py3-none-any.whl`
- `loopspec-<version>.tar.gz`
- `checksums.txt`：上面两个文件的 SHA256，由 `install.sh` 和 `loopspec update` 校验

仓库前置条件：

- `Settings -> Actions -> General -> Workflow permissions` 必须允许 *Read and write*，否则创建 Release 会因 403 失败。
- 任何能推送 `v*` tag 的人都能发布。工作流约束的是能发布*什么*，而不是*谁*能发布；如有需要，用仓库 ruleset 限制 tag 推送。

## 用户侧的行为

| 途径 | 安装内容 |
| --- | --- |
| `install.sh` | 只装最新正式版。`LOOPSPEC_VERSION` 只接受 `X.Y.Z`；传入 beta 会报错，并提示改用 `loopspec update --beta`。 |
| `loopspec update` | 最新正式版（取自 `releases/latest`）。永不降级：已安装的 beta 比最新正式版新时保持不变，直到更新的正式版发布。 |
| `loopspec update --beta` | 包含 beta 在内的最新版本，从仓库的 `releases.atom` 订阅源读取。订阅源只列出最近的 Release；不使用 `api.github.com`。最新 tag 的 Release 返回 HTTP 404 时（CI 未完成或失败），按版本从高到低最多尝试 3 个 tag；其他任何失败都会直接中止。 |
| `loopspec update --version <v>` | 恰好安装该版本，即使比当前旧或与当前相同。接受 `X.Y.Z`、`X.Y.Z-beta` 或 `X.Y.Zb0`。 |

`--check` 只报告不安装，也可与 `--beta` 组合。`--beta` 与 `--version` 不能同时使用（`update_invalid_version`）。详见 [CLI 参考](cli-reference.md#loopspec-update)。

## 出错处理

- **CI 在发布前失败**（lint、测试、可达性、构建）：在 `main` 上修复后移动 tag。删除远端和本地 tag，在修复后的提交上重新打 tag 并推送：

  ```bash
  git push origin :refs/tags/v1.2.0
  git tag -d v1.2.0
  git tag v1.2.0
  git push origin v1.2.0
  ```

- **发布了有问题的 Release**：连同 tag 一起删除 Release，再在修复后的提交上重新推送 tag：

  ```bash
  gh release delete v1.2.0 --cleanup-tag --yes
  git tag -d v1.2.0
  git tag v1.2.0
  git push origin v1.2.0
  ```

  如果用户可能已经安装了它，优先递增到下一个版本，而不是复用这个 tag。
- **tag 被拒绝**：tag 既不是 `vX.Y.Z` 也不是 `vX.Y.Z-beta`。删除它，推送一个形态正确的 tag。
- **beta 成了 Latest**（例如手工发布或编辑过）：在 Releases 页面把最新正式版重新标为 Latest。`install.sh` 和 `loopspec update` 读取的是 `releases/latest`；`install.sh` 和默认的 `loopspec update` 都拒绝那里的非正式版本，所以修正之前两者都会报错，而不会装上 beta。
