#!/usr/bin/env bash
set -u
OLD="$1"; NEW="$2"; W=$(mktemp -d /tmp/lpqa5/run.XXXX); cd "$W"
export GIT_AUTHOR_NAME=qa GIT_AUTHOR_EMAIL=qa@example.invalid GIT_COMMITTER_NAME=qa GIT_COMMITTER_EMAIL=qa@example.invalid
ok() { echo "PASS: $*"; }; bad() { echo "FAIL: $*"; }
echo "old CLI: $($OLD version)"
mkdir proj && cd proj && git init -q && echo x > a.txt
"$OLD" init loopspec --tools claude --json >/dev/null && git add -A && git commit -qm "init with old CLI"
grep -q -- "--dry-run" .claude/skills/loopspec-archive/SKILL.md && ok "前置：旧 CLI 生成的归档 skill 含 --dry-run" || bad "precondition"
rm .claude/skills/loopspec-continue/SKILL.md
"$NEW" change new QA1 >out.json 2>err.txt; code=$?
python3 -c "import json;d=json.load(open('out.json'));assert d['changeName']=='QA1'" && [ $code = 0 ] && ok "AC1 命令输出 JSON 与退出码不变" || bad "AC1 stdout $code"
grep -q "synced .* skill file(s)" err.txt && ok "AC1 stderr 报告同步：$(grep -o 'synced [0-9]* skill file(s)' err.txt)" || bad "AC1 stderr: $(cat err.txt)"
mkdir -p ../ref && (cd ../ref && git init -q && "$NEW" init loopspec --tools claude --json >/dev/null)
diff -r .claude/skills ../ref/.claude/skills >/dev/null && diff -r .claude/commands ../ref/.claude/commands >/dev/null && ok "AC1 skill/command 与新 CLI init 生成的完全一致（含补回删除的 loopspec-continue）" || bad "AC1 content differs"
! grep -q -- "--dry-run" .claude/skills/loopspec-archive/SKILL.md && ok "AC1 归档 skill 已是两段式" || bad "AC1 archive skill"
"$NEW" memory list >/dev/null 2>err2.txt; [ ! -s err2.txt ] && ok "AC2 已一致时无提示" || bad "AC2 $(cat err2.txt)"
[ ! -e .cursor ] && [ ! -e .codex ] && ok "AC3 未配置工具未创建" || bad AC3
"$NEW" version >/dev/null 2>&1; echo "stale" > .claude/skills/loopspec-new/SKILL.md; "$NEW" version >/dev/null 2>&1
grep -q "^stale$" .claude/skills/loopspec-new/SKILL.md && ok "AC3 version 不触发同步" || bad "AC3 version synced"
echo "WORKDIR $W"
