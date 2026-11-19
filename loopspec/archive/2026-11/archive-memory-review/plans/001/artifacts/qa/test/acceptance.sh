#!/usr/bin/env bash
set -u
LS="$1"; W=$(mktemp -d /tmp/lpqa4/run.XXXX); cd "$W"
export GIT_AUTHOR_NAME=qa GIT_AUTHOR_EMAIL=qa@example.invalid GIT_COMMITTER_NAME=qa GIT_COMMITTER_EMAIL=qa@example.invalid
j() { python3 -c "import json,sys;d=json.load(sys.stdin);print($1)"; }
ok() { echo "PASS: $*"; }; bad() { echo "FAIL: $*"; }
setup() {  # $1 dir $2 change $3 finish
  mkdir -p "$1" && cd "$1" && git init -q && echo x > a.txt && git add -A && git commit -qm init
  "$LS" init loopspec --tools none --json >/dev/null
  mkdir -p loopspec/changes && printf 'flow:\n- id: requirements\n  use: requirements\n  requires: []\n- id: qa\n  use: qa-testing\n  requires: [requirements]\n  on_fail: {reset: [requirements], max_retries: 2}\n' > loopspec/changes/req.yaml
  "$LS" change new "$2" >/dev/null
  D=$("$LS" plan create -c "$2" -f changes/req.yaml | j "d['digest']"); "$LS" plan approve -c "$2" -p 001 --digest "$D" >/dev/null
  P=loopspec/changes/$2/plans/001/artifacts; mkdir -p $P/requirements $P/qa/test; echo req > $P/requirements/proposal.md
  [ "$3" = 1 ] && printf -- '---\nverdict: PASS\nsummary: ok\n---\n' > $P/qa/test/pass.md
  return 0
}
M=$(date +%Y-%m)
setup "$W/p1" QA1 1
B=$(find loopspec/changes/QA1 -type f | sort | xargs sha256sum | sha256sum)
R=$("$LS" change archive QA1); ID=$(echo "$R" | j "d['archiveId']")
[ ${#ID} = 64 ] && echo "$R" | j "d['memoryReview']['instructions']" | grep -q "Memory maintenance procedure" && ok "AC1 第一段返回 archiveId 与审阅指引" || bad "AC1 $R"
[ "$(find loopspec/changes/QA1 -type f | sort | xargs sha256sum | sha256sum)" = "$B" ] && [ ! -e loopspec/archive ] && ok "AC1 第一段未改动 Change、未归档" || bad "AC1 changed"
[ -f loopspec/.cache/archive/$ID.json ] && ok "AC1 凭据写入 .cache/archive" || bad "AC1 ticket"
[ "$("$LS" change archive --confirm $ID | j "d['error']")" = memory_review_required ] && ok "AC2 缺 --memory/--note 拒绝" || bad AC2
[ "$("$LS" change archive --confirm $ID --memory updated --note "x" | j "d['error']")" = memory_review_missing ] && ok "AC4 updated 但 memory 无变化拒绝" || bad AC4
echo "# Lesson" > loopspec/memory/qa-lesson.md
[ "$("$LS" change archive --confirm $ID --memory none --note "x" | j "d['error']")" = memory_review_mismatch ] && ok "AC4 none 但 memory 有变化拒绝" || bad AC4b
[ -d loopspec/changes/QA1 ] && ok "AC2/AC4 拒绝时未移动" || bad "moved"
R=$("$LS" change archive --confirm $ID --memory updated --note "记录 QA 经验"); [ "$(echo "$R" | j "d['memoryReview']['changedTopics']")" = "['qa-lesson']" ] && ok "AC5 确认成功并返回变化 topic" || bad "AC5 $R"
S=loopspec/archive/$M/QA1/state.md; grep -q "归档前 memory 审阅.*结论：updated.*qa-lesson.*记录 QA 经验" $S && ok "AC5 state.md 记录审阅结论" || bad "AC5 state"
[ ! -e loopspec/.cache/archive/$ID.json ] && ok "AC5 凭据已消费" || bad "AC5 ticket"
[ "$("$LS" change archive --confirm $ID --memory updated --note x | j "d['error']")" = archive_ticket_not_found ] && ok "AC2 凭据不能重复使用" || bad reuse
"$LS" change archive QA1 --dry-run >/dev/null 2>&1; [ $? = 2 ] && ok "AC7 --dry-run 不再接受" || bad AC7
setup "$W/p2" QA2 1
ID=$("$LS" change archive QA2 | j "d['archiveId']"); echo edited >> loopspec/changes/QA2/plans/001/artifacts/requirements/proposal.md
[ "$("$LS" change archive --confirm $ID --memory none --note x | j "d['error']")" = archive_ticket_stale ] && ok "AC3 两段之间内容变化报 stale" || bad AC3
[ "$("$LS" change archive QA2 --confirm $ID --memory none --note x | j "d['error']")" = option_conflict ] && ok "AC6 --confirm 与需求名互斥" || bad AC6
setup "$W/p3" QA3 0
ID=$("$LS" change archive QA3 --force | j "d['archiveId']"); R=$("$LS" change archive --confirm $ID --memory none --note "放弃的需求，无可复用结论")
[ "$(echo "$R" | j "d['archived'][0]['forced']")" = True ] && ok "AC6 --force 两段归档" || bad "AC6f $R"
setup "$W/p4" QA4 1; "$LS" change new QA5 >/dev/null
R=$("$LS" change archive --all); ID=$(echo "$R" | j "d['archiveId']")
[ "$(echo "$R" | j "([c['changeName'] for c in d['changes']], [s['changeName'] for s in d['skipped']])")" = "(['QA4'], ['QA5'])" ] && ok "AC6 --all 第一段只收 complete" || bad "AC6a $R"
R=$("$LS" change archive --confirm $ID --memory none --note "批量：无新结论"); [ "$(echo "$R" | j "[a['changeName'] for a in d['archived']]")" = "['QA4']" ] && ok "AC6 --all 第二段归档" || bad "AC6b $R"
echo "WORKDIR $W"
