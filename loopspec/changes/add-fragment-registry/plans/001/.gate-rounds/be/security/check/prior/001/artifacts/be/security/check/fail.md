---
verdict: FAIL
summary: "缓存中预置的 repo.git/config 可导致命令执行；远端文件名可携带 shell 元字符注入 agent 命令；cat-file --batch 的 stdin 写入可能在超时控制之外死锁"
---

# 后端安全审查：失败

## 阻塞问题
- `src/loopspec/registry_git.py` 的 `RegistryRepo.ensure`：只要 `<home>/.cache/registry/repo.git/HEAD` 存在就复用该仓库，后续所有 git 调用都以它为 `--git-dir`，因此仓库自带的 config 会生效（`core.sshCommand`、`credential.helper=!cmd`、`include.path`、`url.*.insteadOf`、`objects/info/alternates` 等）。`is_file()` 与 `cwd=` 还会跟随符号链接。恶意项目可以用 `git add -f` 提交一个预置的缓存仓库，受害者执行 `registry update` 时就会执行任意命令。复审时在 scratchpad 中复现过：设置 `core.sshCommand` 后，marker 文件被创建。
- `src/loopspec/registry_git.py` 的 `_registry_path` 只调用 `workflow_io.relative_path`，允许 `$( )`、反引号、`;`、引号、空格与双向控制字符（如 U+202E）；`registry_sync.py` 中 lock 的 `FILE_RE` 与本地扫描也没有限制字符集。这类路径会进入计划，再由 agent 按 skill 放进 `--skip` / `--resolve` 参数，通过 Bash 工具执行时会被 shell 展开，导致命令注入。
- `src/loopspec/registry_git.py` 的 `run_git`：有 stdin 时先阻塞写完全部请求，才进入带超时的读取循环。`cat-file --batch` 的请求最多约 84KB，超过 pipe 缓冲区；git 在读 stdin 的同时向 stdout 写出内容，stdout 写满后两边互相等待而死锁，这时超时不生效。

## 审查输入
- 轮次 `001.1:be/security/check:1`，基线 `9b90c66c11bab432176d640cfc6caad760706fcc`，固定路径 16 个（与测试 Gate 相同）。
- 由一个只读子代理独立审查，主代理逐条复核：B1 读代码确认，并采信子代理的实测；B2 用 `_registry_path` 对三个示例路径做了实测，全部通过校验。

## 建议修复方向
- 阻塞问题 1：每次 update 都丢弃并以 O_NOFOLLOW 重建私有裸仓库，不复用磁盘上已有的 git 目录，也不信任它的 config、alternates 或链接。
- 阻塞问题 2：路径的每一级只允许 `[A-Za-z0-9._-]+`，并在远端读树、lock 的 `FILE_RE`、本地扫描与 `PlanEntry.path` 四处统一校验；不合法的名称计入 warning 或 unsupported，且不回显原名。
- 阻塞问题 3：stdin 改为在独立线程或同一个 selector 中写入，让超时覆盖整个过程；`_read_blobs` 对截断或格式异常的输出返回 `registry_invalid`。
- 非阻塞，建议一并处理：
  - `PlanEntry.path` 校验格式，并在任何写入之前就构建好下一版 lock（防止伪造 plan.json 写到 fragments/profiles 之外）。
  - 增加 `-c http.followRedirects=false`；ssh URL 的用户名部分禁止以 `-` 开头。
  - skill 第 2 步展示 instruction、template、guidance 文件的内容 diff，并提醒用户审阅 `registry.lock.yaml` 的 diff（伪造的基线哈希可以把冲突伪装成上游变更）。
- 接受、不处理的项：GIT_SSH_COMMAND 等由用户自己控制的环境变量保持继承；`fetch --depth=1` 的体积只受超时限制；`_remove`、`copytree` 与 apply 中「检查哈希后再写入」之间存在本地 TOCTOU 窗口；`file://` 保留（用于本地或单仓场景与测试）。
