#!/usr/bin/env bash
set -u
LS="$1"; W=$(mktemp -d /tmp/lpqa3/run.XXXX); cd "$W"
export GIT_AUTHOR_NAME=qa GIT_AUTHOR_EMAIL=qa@example.invalid GIT_COMMITTER_NAME=qa GIT_COMMITTER_EMAIL=qa@example.invalid
j() { python3 -c "import json,sys;d=json.load(sys.stdin);print($1)"; }
ok() { echo "PASS: $*"; }; bad() { echo "FAIL: $*"; }
setup() {  # $1 project dir, $2 change name, $3 finish(1/0)
  mkdir -p "$1" && cd "$1" && git init -q && echo x > a.txt && git add -A && git commit -qm init
  "$LS" init loopspec --tools none --json >/dev/null
  mkdir -p loopspec/changes && cat > loopspec/changes/req.yaml <<'R'
flow:
- id: requirements
  use: requirements
  requires: []
- id: qa
  use: qa-testing
  requires: [requirements]
  on_fail: {reset: [requirements], max_retries: 2}
R
  "$LS" change new "$2" >/dev/null
  D=$("$LS" plan create -c "$2" -f changes/req.yaml | j "d['digest']")
  "$LS" plan approve -c "$2" -p 001 --digest "$D" >/dev/null
  P=loopspec/changes/$2/plans/001/artifacts
  mkdir -p $P/requirements $P/qa/test; echo req > $P/requirements/proposal.md
  printf -- '---\nverdict: FAIL\nsummary: x\n---\n' > $P/qa/test/fail.md
  "$LS" plan rollback -c "$2" -p 001 >/dev/null
  if [ "$3" = 1 ]; then echo req > $P/requirements/proposal.md; printf -- '---\nverdict: PASS\nsummary: ok\n---\n' > $P/qa/test/pass.md; fi
}
M=$(date +%Y-%m)
setup "$W/p1" QA1 1
[ -d loopspec/changes/QA1/plans/001/.attempts/001 ] && ok "前置：返工后存在 .attempts" || bad "no attempts"
[ "$("$LS" change status QA1 --json | j "d['status']")" = complete ] && ok "前置：Change complete" || bad "not complete"
R=$("$LS" change archive QA1 --dry-run); [ "$(echo "$R" | j "d['dropped']")" = "['plans/001/.attempts', 'plans/001/artifacts/qa/test/pass.md']" ] && ok "AC3 dry-run 列出将删除路径" || bad "AC3 $R"
[ -d loopspec/changes/QA1/plans/001/.attempts/001 ] && ok "AC3 dry-run 未删除" || bad "AC3 deleted"
R=$("$LS" change archive QA1); [ "$(echo "$R" | j "d['dropped']")" = "['plans/001/.attempts', 'plans/001/artifacts/qa/test/pass.md']" ] && ok "AC2 结果列出已删除路径" || bad "AC2 $R"
A=loopspec/archive/$M/QA1
if [ ! -e $A/plans/001/.attempts ] && [ ! -e $A/plans/001/artifacts/qa ] && [ -f $A/state.md ] && [ -f $A/plans/001/plan.yaml ] && [ -f $A/plans/001/artifacts/requirements/proposal.md ]; then ok "AC1 归档无 .attempts/Gate 报告，state/plan/需求产物保留"; else bad "AC1"; fi
[ ! -e loopspec/changes/QA1 ] && ok "AC1 原 Change 目录已移走" || bad "AC1 src"
setup "$W/p2" QA2 0
R=$("$LS" change archive QA2); [ "$(echo "$R" | j "d['error']")" = archive_unsafe ] && [ -d loopspec/changes/QA2/plans/001/.attempts ] && ok "AC8 拒绝归档时不删除" || bad "AC8 $R"
R=$("$LS" change archive QA2 --force); [ "$(echo "$R" | j "(d['forced'], d['dropped'])")" = "(True, ['plans/001/.attempts'])" ] && [ ! -e loopspec/archive/$M/QA2/plans/001/.attempts ] && ok "AC4 --force 同样删除" || bad "AC4 $R"
setup "$W/p3" QA3 1
R=$("$LS" change archive --all); [ "$(echo "$R" | j "[a['dropped'] for a in d['archived']]")" = "[['plans/001/.attempts', 'plans/001/artifacts/qa/test/pass.md']]" ] && [ -z "$(find loopspec/archive -name .attempts -o -name pass.md)" ] && ok "AC5 --all 每项不含 .attempts" || bad "AC5 $R"
echo "WORKDIR $W"
