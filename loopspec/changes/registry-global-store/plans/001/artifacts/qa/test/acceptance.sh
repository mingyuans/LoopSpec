#!/usr/bin/env bash
set -u
LS="$1"   # loopspec executable under test
W=$(mktemp -d /tmp/lpqa/run.XXXX); cd "$W"
export LOOPSPEC_REGISTRY_STORE="$W/store"
export GIT_AUTHOR_NAME=qa GIT_AUTHOR_EMAIL=qa@example.invalid GIT_COMMITTER_NAME=qa GIT_COMMITTER_EMAIL=qa@example.invalid
j() { python3 -c "import json,sys;d=json.load(sys.stdin);print($1)"; }
ok() { echo "PASS: $*"; }; bad() { echo "FAIL: $*"; }
# registry with built-in definitions
B=$(python3 -c "import loopspec.builtin_resources as b;print(b.builtin_root())" 2>/dev/null || "$(dirname "$LS")/python" -c "import loopspec.builtin_resources as b;print(b.builtin_root())")
mkdir reg && cp -r "$B/fragments" "$B/profiles" reg/ && (cd reg && git init -q -b main && git add -A && git commit -qm init && git tag v1.0.0)
URL="file://$W/reg"
# project A
mkdir projA && cd projA && git init -q && echo x > a.txt && mkdir loopspec loopspec/changes
printf 'artifacts_dir: changes\nworkflow: {}\nregistry:\n  url: %s\n' "$URL" > loopspec/config.yaml
git add -A && git commit -qm base
C=$($LS fragment list | j "d.get('error')"); [ "$C" = registry_not_synced ] && ok "AC11 缺少 lock 报 registry_not_synced" || bad "AC11 got $C"
P=$($LS registry update | j "d['planId']")
S=$(git status --porcelain --untracked-files=all | grep -v '^?? loopspec/.cache/' ); [ -z "$S" ] && ok "AC5 update 后 git status 无新增/修改（仅 .cache 自带忽略）" || bad "AC5 status: $S"
[ -z "$(git status --porcelain)" ] && ok "AC5 .cache 被自带 .gitignore 忽略" || bad "AC5 porcelain: $(git status --porcelain)"
$LS registry apply --plan "$P" >/dev/null
S=$(git status --porcelain --untracked-files=all); [ "$S" = "?? loopspec/registry.lock.yaml" ] && ok "AC6 apply 后只新增 registry.lock.yaml" || bad "AC6 status: $S"
[ ! -e loopspec/fragments ] && [ ! -e loopspec/profiles ] && ok "AC6 项目内无 fragments/profiles" || bad "AC6 definitions in project"
U=$($LS registry update | j "d['upToDate']"); [ "$U" = True ] && ok "AC5 同版本 update 返回 upToDate" || bad "AC5 upToDate=$U"
git add -A && git commit -qm lock
cd "$W"
# fresh clone with empty store
rm -rf "$W/store"; git clone -q projA cloneB; cd cloneB
N=$($LS fragment list | j "len(d['fragments'])"); [ "$N" -ge 10 ] && ok "AC1 新 clone、空存储时 fragment list 成功（$N 个）" || bad "AC1 n=$N"
ls "$W/store"/*/ | grep -q '^[0-9a-f]\{40\}' && ok "AC1 全局存储出现该 commit 快照" || bad "AC1 no snapshot"
mkdir -p loopspec/changes
cat > loopspec/changes/req.yaml <<'R'
flow:
- id: requirements
  use: requirements
  requires: []
- id: design
  use: design
  requires: [requirements]
R
$LS change new QA1 >/dev/null
D=$($LS plan create -c QA1 -f changes/req.yaml | j "d['digest']")
$LS plan approve -c QA1 -p 001 --digest "$D" >/dev/null
I=$($LS node instructions -c QA1 -n requirements/proposal | j "d['instruction']")
E=$(cat "$W/reg/fragments/requirements/proposal.instruction.md")
[ "$I" = "$E" ] && ok "AC2 新 clone 上 plan create/approve/node instructions，指令与 registry 一致" || bad "AC2 instruction differs"
cd "$W"
# offline second checkout of same commit
mv reg reg.off; git clone -q projA cloneC 2>/dev/null || cp -r projA cloneC; cd cloneC
N=$($LS profile list | j "len(d['profiles'])"); [ "$N" -ge 1 ] && ok "AC3 registry 不可达时同 commit 第二个 checkout 仍可用" || bad "AC3"
cd "$W"; rm -rf "$W/store"; cd cloneC
C=$($LS fragment list | j "d.get('error')"); [ "$C" = registry_fetch_failed ] && ok "AC12 registry 不可达且存储为空报 registry_fetch_failed" || bad "AC12 got $C"
[ -z "$(find "$W/store" -mindepth 2 -maxdepth 2 -name '[0-9a-f]*' 2>/dev/null)" ] && ok "AC12 未留下半成品快照" || bad "AC12 partial snapshot"
cd "$W"; mv reg.off reg; cd cloneB
# tamper snapshot (re-materialize first: the previous step emptied the store)
$LS fragment list >/dev/null
F=$(ls -d "$W/store"/*/[0-9a-f]*/ | head -1); echo evil >> "$F/fragments/design/design.instruction.md"
C=$($LS fragment list | j "d.get('error')"); [ "$C" = registry_store_corrupt ] && ok "AC4 快照被篡改报 registry_store_corrupt" || bad "AC4 got $C"
rm -rf "$F"; $LS fragment list >/dev/null && ok "AC4 删除损坏快照后自动重新拉取" || bad "AC4 refetch"
# local conflict
mkdir -p loopspec/profiles && echo vendored > loopspec/profiles/bugfix.yaml
$LS change new QA2 >/dev/null 2>&1
C=$($LS plan validate -c QA2 -f changes/req.yaml | j "d.get('error')"); [ "$C" = registry_local_conflict ] && ok "AC7 本地同名 Profile 时 plan validate 报 registry_local_conflict" || bad "AC7 got $C"
C=$($LS node instructions -c QA1 -n requirements/proposal | j "d.get('error')"); [ "$C" = registry_local_conflict ] && ok "AC7 node instructions 同样报错" || bad "AC7 node $C"
rm loopspec/profiles/bugfix.yaml
$LS fragment list >/dev/null && ok "AC7 删除副本后恢复" || bad "AC7 restore"
# local-only + save
$LS profile save bugfix -c QA1 | j "d.get('error')" | grep -q profile_exists && ok "AC9 profile save 与 registry 同名失败" || bad "AC9"
[ ! -e loopspec/profiles/bugfix.yaml ] && ok "AC9 未写文件" || bad "AC9 wrote"
$LS profile save docs-only -c QA1 >/dev/null
S=$($LS profile list | j "sorted((i['name'],i['source']) for i in d['profiles'] if i['name'] in ('docs-only','bugfix'))"); [ "$S" = "[('bugfix', 'registry'), ('docs-only', 'local')]" ] && ok "AC8 本地独有与 registry 定义并存并标注来源" || bad "AC8 $S"
cd "$W"
# v1 migration with vendored copies
mkdir projV && cd projV && git init -q && mkdir -p loopspec/changes && cp -r "$W/reg/fragments" "$W/reg/profiles" loopspec/
printf 'artifacts_dir: changes\nworkflow: {}\nregistry:\n  url: %s\n' "$URL" > loopspec/config.yaml
python3 - "$W/projA/loopspec/registry.lock.yaml" loopspec/registry.lock.yaml <<'PY'
import sys,yaml
l=yaml.safe_load(open(sys.argv[1])); v={"tag":l["tag"],"commit":l["commit"]}
l["version"]=1; l["definitions"]={("fragments/"+p.split("/")[1]) if p.startswith("fragments") else p[:-5]: dict(v) for p in l["files"]}
open(sys.argv[2],"w").write(yaml.safe_dump(l))
PY
C=$($LS fragment list | j "d.get('error')"); [ "$C" = registry_local_conflict ] && ok "AC10 v1 + vendored 副本报 registry_local_conflict" || bad "AC10 got $C"
rm -rf loopspec/fragments loopspec/profiles
$LS fragment list >/dev/null && ok "AC10 删除副本后按 v1 lock 使用全局存储" || bad "AC10 v1 read"
P=$($LS registry update | j "d['planId'] if d['migration'] else None"); $LS registry apply --plan "$P" >/dev/null
V=$(python3 -c "import yaml;print(yaml.safe_load(open('loopspec/registry.lock.yaml'))['version'])"); [ "$V" = 2 ] && ok "AC10 apply 后 lock 改写为 v2" || bad "AC10 version $V"
cd "$W"
# non-registry project unchanged
mkdir projN && cd projN && git init -q && "$LS" init loopspec --tools none --json >/dev/null 2>&1
[ -e loopspec/fragments/design/fragment.yaml ] && ok "AC13 非 registry 项目 init 仍复制内置定义" || bad "AC13 init"
S=$($LS fragment list | j "set(i['source'] for i in d['fragments'])"); [ "$S" = "{'local'}" ] && ok "AC13 非 registry 项目定义来自本地" || bad "AC13 $S"
echo "WORKDIR $W"
