# CLI reference

> Scope: every command and option, the JSON output contract and every error code.
> Audience: humans and agents looking up a command.
> Language: **English** · [中文](../zh/cli-reference.md)

## Conventions

- Commands are `loopspec <resource> <verb>`, with singular resources: `change`, `plan`, `node`, `gate`, `fragment`, `profile`. Only `version` and `init` stand alone.
- `-c/--change` names a Change, `-p/--plan` a three-digit Plan number, `-n/--node` a leaf node or Gate path, `-f/--file` a request file relative to the workflow home, `--digest` the digest a human confirmed, `--note` an optional note. `change` commands take the Change name as an argument.
- Every command except `version` and `init` accepts `--home` (default `./loopspec`) and prints JSON. The one exception is `change status`, which prints a plain-text report for an LLM by default and JSON only with `--json`. On failure it prints `{"error": <code>, "message": <text>, "fix": <next action>}` and exits with status 1; usage errors exit with status 2.
- Execution commands (`node`, `gate`, `plan rollback`) act only on the active Plan. Without one they fail with `plan_not_active` and a `fix` naming the next planning step. Every command takes effect in a single write, so an interrupted command leaves the Change as before or as after; rework files still to be archived are moved first by the next writing command.

## loopspec version

Prints the installed version. `--json` prints `{"version": "..."}`.

## loopspec init

```bash
loopspec init [PATH] [--tools all|none|<ids>] [--project-root <dir>] [--json]
```

Creates the workflow home at `PATH` (default `./loopspec`): `config.yaml` (`artifacts_dir: changes` and an empty `workflow`), `changes/`, and the built-in `fragments/` and `profiles/`, copying only files that are missing. `--tools` writes agent Skills and `/lpsx:*` commands for the listed tools; without it, an interactive terminal shows a picker and anything else configures none. `--project-root` sets where tool directories go (default: the parent of the home). Output is a human summary unless `--json` is given.

## loopspec change new

```bash
loopspec change new <change>
```

Creates an unplanned Change: `.workflow.yaml` (format 4, no Plan, no baseline), a sectioned `state.md` template and `plans/`. Nothing is compiled or executable. Re-running on an existing Change returns it with `reusedChange: true`. Options: `--home`.

## loopspec change status

```bash
loopspec change status <change> [--json]
```

By default prints a plain-text report for an LLM to read: sections start with a `=== SECTION ===` line at column zero, with no Markdown, no colour and the same bytes on every terminal. The section order is fixed: `OVERVIEW`, `STATE RECORDS`, `PLANS`, `NODES` (with an active Plan), `GATE FAILURES` (when a Gate failed), `PENDING ROLLBACK` (when a rollback is due) and `NEXT STEPS`, each opening with a short explanation. `STATE RECORDS` quotes the change-level `state.md` and the current Plan's (the active Plan, or the draft while planning) verbatim, every line indented by four spaces and marked as untrusted data; archived Plans' `state.md` is left out, while `PLANS` still lists every Plan. On failure it prints an `=== ERROR ===` report and exits with status 1.

With `--json` it returns `status` (`unplanned`, `planning`, `active`, `complete`), `baseline`, `repository`, `activePlan`, `openPlan`, a summary of every Plan, and `nextSteps` with the single next command. With an active Plan it adds `plan`, `revision`, `digest`, `nodes` (each with `status`, output paths, `reason` for stale evidence, `gate` details for failures and `taskProgress` for tracked nodes), `instances` (reference summaries) and `pendingRollback`, plus `warnings` when the diff was computed to recheck evidence and ignored paths are not excluded. In every state it also returns `state` (the change-level `state.md`), `planState` (the current Plan's `state.md` with its `plan` number, `null` when unplanned) and `untrustedData` (an untrusted-data notice). `state` and `planState` look like `{path, content, truncated}`: `content` is `null` when the file is missing, an unreadable file (symlink, not a regular file) adds `error: "unreadable"`, and a file over 64 KiB keeps its first and last 32 KiB with `truncated: true`. Options: `--json`, `--home`.

## loopspec change next

```bash
loopspec change next <change>
```

Same logic as `change status`, returning only `status`, `isComplete`, the node to work on and `nextSteps`. Options: `--home`.

## loopspec change history

```bash
loopspec change history <change> [-p <NNN>]
```

Lists the rework records in `.attempts/` of the active Plan, or of the open or latest Plan, or of the Plan given with `--plan`: `seq`, `kind`, `gate`, `reset`, archived `files`, and for revisions the target digest and revision. Options: `--plan`, `--home`.

## loopspec change artifacts

```bash
loopspec change artifacts <change>
```

Lists every artifact the Change owns, grouped by location (the active Change and any archived copies) and by Plan, archived Plans included. Read-only. Options: `--home`.

## loopspec change archive

```bash
loopspec change archive <change> [--force] [--dry-run]
loopspec change archive --all [--older-than <days>] [--dry-run]
```

Moves the Change directory to `archive/<YYYY-MM>/<change>`. It first re-derives the status, including code evidence and assurance; only a `complete` Change is archived. `--force` archives an unfinished Change when the human explicitly abandons it; the result says `forced: true` and that it was archived unfinished. `--dry-run` reports without moving. `--all` archives every complete Change, skipping the rest with a reason; `--older-than` limits it to Changes created at least that many days ago. `--all` cannot be combined with `--force` or a name. Options: `--all`, `--older-than`, `--force`, `--dry-run`, `--home`.

## loopspec plan validate

```bash
loopspec plan validate -c <change> -f <request>
```

Read-only. Without an approved Plan it compiles the request and checks project constraints, returning `spec` and `digest`. With an approved Plan it treats the request as a revision: checks `base_revision` and the freeze rules and returns the new `digest`, `addedInstances` and `rerunNodes` to show the human. Options: `--change`, `--file`, `--home`.

## loopspec plan create

```bash
loopspec plan create -c <change> -f <request> [--note <text>]
```

Compiles the request against the current Fragments and `config.yaml`. With no open Plan it creates the next numbered draft Plan and, the first time, fixes the Change baseline and repository. With an open draft it replaces that draft's `spec` (and `note` when given). With an approved Plan it fails with `plan_active`. A new draft gets a sectioned Plan-level `state.md` template. After a draft is created or replaced it appends one event line to the Plan-level `state.md` (see the [overview](overview.md)); a failed append does not change the result and only adds `warnings: ["state_append_failed: <path>"]` to the output. Options: `--change`, `--file`, `--note`, `--home`.

## loopspec plan show

```bash
loopspec plan show -c <change> [-p <NNN>]
```

Returns `meta`, `spec`, `baseline` and `repository` of the open Plan, or of the Plan given with `--plan`. This is what a human reviews before approval. Options: `--change`, `--plan`, `--home`.

## loopspec plan list

```bash
loopspec plan list -c <change>
```

Lists every Plan with its number, status, revision, note and timestamps. Options: `--change`, `--home`.

## loopspec plan approve

```bash
loopspec plan approve -c <change> -p <NNN> --digest <digest>
loopspec plan approve -c <change> -p <NNN> -f <revision-request> --digest <digest>
```

Run only after a human explicitly confirmed what they were shown. Without `--file` it approves the draft: it recompiles the draft's flow, requires both the stored and the recompiled digest to equal `--digest`, checks the repository, sets `revision: 1` and makes the Plan active. With `--file` it applies a revision of the active Plan: recompiles the request, requires its digest to equal `--digest`, checks `base_revision` and the freeze rules, archives the re-run nodes' files and replaces `spec`. Repeating an approval that already took effect returns `alreadyApproved: true` and appends nothing. After an approval or revision takes effect it appends one event line to the Plan-level `state.md` (see the [overview](overview.md)); a failed append does not change the result and only adds `warnings: ["state_append_failed: <path>"]` to the output. Options: `--change`, `--plan`, `--digest`, `--file`, `--home`.

## loopspec plan archive

```bash
loopspec plan archive -c <change> -p <NNN> [--note <text>]
```

Marks the open draft or approved Plan `archived` and clears the Change's pointers; the Change becomes `unplanned`. The Plan directory and business code are left untouched. Archiving an approved Plan requires the human's explicit consent first. After it takes effect it appends one event line to both the Plan-level and the change-level `state.md` (see the [overview](overview.md)); a failed append does not change the result and only adds `warnings: ["state_append_failed: <path>"]` to the output. Options: `--change`, `--plan`, `--note`, `--home`.

## loopspec plan rollback

```bash
loopspec plan rollback -c <change> -p <NNN>
```

For an effective FAIL in the active Plan, applies that Gate's own `on_fail`: archives the artifacts, reports and evidence of its `reset` nodes, the Gate and everything downstream into `.attempts/<NNN>/` (`kind: rollback`). Business code is not reverted. Fails with `retries_exhausted` when the Gate has no `on_fail` or no retries left, and `no_failed_gate` when nothing failed. After it takes effect it appends one event line to the Plan-level `state.md` (see the [overview](overview.md)); a failed append does not change the result and only adds `warnings: ["state_append_failed: <path>"]` to the output. Options: `--change`, `--plan`, `--home`.

## loopspec node instructions

```bash
loopspec node instructions -c <change> -n <node>
```

Returns what an agent needs to execute one ready (or done) leaf node of the active Plan: the live `instruction`, `template` or Gate `templates`, `outputPath` and `resolvedOutputPath`, `dependencies`, and `priorAttempts` (earlier rework records and FAIL reports, marked untrusted). Code Gates add `gateProtocol` with the `gate begin` and `gate record` commands; the assurance node adds its `gate record` command. It takes the Change's write lock and first finishes archiving files of effective rework records, so new outputs never overwrite files still to be archived. Options: `--change`, `--node`, `--home`.

## loopspec gate begin

```bash
loopspec gate begin -c <change> -n <gate>
```

Only for a ready code Gate. Pins the content of its `evidence.paths` relative to the baseline and returns a one-time `roundId` and the files in scope (paths, kinds and digests, never content). When paths ignored by Git are not listed in `workflow.excluded_paths`, it also returns `warnings` (`ignoredPaths`, at most 20, and `ignoredTotal`); reviewers should record them in the report summary. Options: `--change`, `--node`, `--home`.

## loopspec gate record

```bash
loopspec gate record -c <change> -n <gate> --round <roundId> --report <artifacts/...>
loopspec gate record -c <change> -n <assurance-node>
```

For a code Gate, `--round` and `--report` are required. The report lives under the Plan's `artifacts/` and its header holds only `verdict` and `summary`. The round must be unused and the pinned code unchanged; then the PASS or FAIL report and evidence bound to the Plan digest are written, and the same `warnings` are returned. For the assurance node both options are refused: the CLI checks the full diff against the assurance rules and writes the system PASS or FAIL with diagnostics. Warnings never change the verdict; they go into the system report's `summary` and the diagnostics' `warnings`. With `unknown_paths: warn` in the assurance rules, changed paths matching no rule are reported there as warnings too. Ignored files never count toward the diff or evidence digests. Options: `--change`, `--node`, `--round`, `--report`, `--home`.

## loopspec fragment list

Lists the Fragments in the workflow home. Each entry carries `registry`: `{syncedTag, syncedCommit}` for a definition recorded in `registry.lock.yaml`, otherwise `null` (also when the lock is missing or malformed). Options: `--home`.

## loopspec fragment show

`loopspec fragment show <name>` returns one Fragment definition. Options: `--home`.

## loopspec fragment validate

`loopspec fragment validate <name>` expands the Fragment and checks dependencies, resources, outputs and `on_fail` (including `on_fail_conflict`). Options: `--home`.

## loopspec profile list

Lists the Profiles in the workflow home. Each entry carries `registry`: `{syncedTag, syncedCommit}` for a definition recorded in `registry.lock.yaml`, otherwise `null` (also when the lock is missing or malformed). Options: `--home`.

## loopspec profile show

`loopspec profile show <name>` returns one Profile. Options: `--home`.

## loopspec profile validate

`loopspec profile validate <name>` compiles its flow and returns the build order, instances and each Gate's resulting `on_fail`. Options: `--home`.

## loopspec profile save

```bash
loopspec profile save <name> -c <change>
```

Saves the active Plan's `spec.flow`, `on_fail` included, as `profiles/<name>.yaml`. No execution state is saved and an existing Profile is never overwritten. Options: `--change`, `--home`.

## loopspec registry update

```bash
loopspec registry update [--full]
```

Plans a sync of `fragments/` and `profiles/` from the `registry` in `config.yaml`; it writes only `<home>/.cache/registry/`. First `git ls-remote` resolves the target (`latest` or the fixed tag). When that commit equals the lock's and no definition lags behind, it returns `upToDate: true` without fetching; a fixed tag that is already synced runs no git at all. Otherwise it fetches the commit into a private bare repository (never checked out), compares every registry definition with the local copies against the lock, and stages upstream and base contents for review. Each file gets a `status`: `upstream-added`, `upstream-modified`, `upstream-deleted` (pending, need confirmation), `conflict` (must be resolved), `local-modified`, `local-deleted`, `local-only` (kept as they are). Symlinks and submodules are listed in `unsupported` and never written. Returns `registry`, `upToDate`, `baseCommit`, `baseTag`, `upstreamCommit`, `upstreamTag`, `baseAvailable`, `planId`, `definitions` (each with `kind`, `name`, `deletedUpstream`, `baseTag`, `baseCommit`, `upstreamTag`, `upstreamCommit`), `files` (each with `path`, `status`, `localPath`, `upstreamPath`, `basePath`), `unsupported`, `warnings` and `nextSteps`. `--full` skips the version check and always compares. Requires `git` on `PATH`. Options: `--full`, `--home`.

## loopspec registry apply

```bash
loopspec registry apply --plan <planId> [--resolve <path>=local|upstream]... [--skip <path>]...
```

Writes the latest `registry update` plan after the human confirmed it. Every `conflict` needs exactly one `--resolve`: `local` keeps the current local file (including a merge written there after confirmation), `upstream` takes the registry version. `--skip` leaves a pending change out; its base and its definition's version stay as they were, so it appears again next time. Refused with `registry_plan_stale` when the plan is not the latest, the staged contents changed, or a local file changed after the plan. The result is built and loaded in a preview first; any Fragment or Profile that fails validation stops the command before anything is written. Then files are written atomically, deletions remove only listed files, and `registry.lock.yaml` is updated. Returns `applied`, `upstreamCommit`, `upstreamTag`, `written`, `deleted`, `skipped`, `kept` and `lock`. Applying takes effect immediately for running Plans. Options: `--plan`, `--resolve`, `--skip`, `--home`.

## Error codes

| Code | Meaning |
| --- | --- |
| `error` | Generic failure without a more specific code. |
| `config_invalid` | `config.yaml` is malformed or still has removed fields. |
| `builtin_skill_invalid` | A bundled Skill file is broken; reinstall LoopSpec. |
| `workflow_invalid` | A Fragment, Profile, request or record does not match its schema. |
| `invalid_change_name` | The Change name is not letters, digits, `_` and `-`. |
| `invalid_plan` | The Plan number is not three digits. |
| `change_not_found` | No such Change. |
| `unsupported_format` | A Change from LoopSpec 1.x or an older format; finish it with 1.x or recreate it. |
| `plan_not_found` | No such Plan, or no open Plan to show. |
| `plan_not_open` | The Plan is not the Change's open Plan. |
| `plan_not_active` | No active Plan, or the given Plan is not the active one. |
| `plan_active` | An approved Plan exists, so a new Plan cannot be created. |
| `plan_archived` | The Plan is archived. |
| `plan_changed` | The digest does not match what would take effect; show the Plan again. |
| `plan_integrity` | `plan.yaml` was edited by hand or is malformed. |
| `stale_revision` | `base_revision` does not match, or is set where no Plan is approved. |
| `node_frozen` | A revision removes, renames or rewrites a frozen node, or drops its `requires`. |
| `failure_pending` | A revision leaves an effective FAIL outside the re-run set. |
| `project_constraint` | The Plan misses required Fragments or the required assurance node. |
| `history_integrity` | A rework record or archived file does not match; a human must inspect `.attempts/`. |
| `no_failed_gate` | Nothing to roll back. |
| `retries_exhausted` | The failed Gate has no `on_fail` or no retries left. |
| `node_not_found` | The node is not a leaf of the active Plan. |
| `node_not_ready` | The node is not ready; follow `nextSteps`. |
| `reference_not_executable` | A reference node was named; execute its leaves. |
| `not_code_gate` | `gate begin` or `gate record` on a node without `evidence`. |
| `option_required` | A code Gate record without `--round` and `--report`. |
| `option_conflict` | Options that cannot be combined. |
| `round_stale` | The review round is used, missing or belongs to other input. |
| `review_input_changed` | The pinned code changed during review; begin again. |
| `invalid_verdict` | A report header is not exactly `verdict` and `summary`, or is empty. |
| `verdict_conflict` | A Gate has both a PASS and a FAIL report. |
| `unsafe_report` | The report is outside the active Plan's `artifacts/`. |
| `assurance_missing` | No assurance rules are configured for the assurance node. |
| `invalid_assurance` | The assurance node is missing, duplicated, or does not follow every branch and code review. |
| `rule_conflict` | Two assurance rules share an id with different content. |
| `on_fail_conflict` | One Gate would receive two `on_fail` policies. |
| `invalid_reset` | An `on_fail` target is not upstream of the Gates it covers. |
| `invalid_tracks` | `tracks` does not name an upstream artifact of the same instance. |
| `missing_dependency` | `requires` names a node or instance that does not exist. |
| `dependency_cycle` | The dependency graph has a cycle. |
| `fragment_cycle` | Fragments reference each other in a cycle. |
| `duplicate_instance` | Two instances share an id. |
| `output_conflict` | Two outputs overlap. |
| `unsafe_output` | An output points into a control path. |
| `unsafe_path` | A path is absolute, escapes its root, or is a link or special file. |
| `resource_limit` | A size, depth or count limit was exceeded. |
| `profile_exists` | `profile save` would overwrite an existing Profile. |
| `archive_unsafe` | The Change is not complete; finish it or use `--force` on explicit request. |
| `archive_conflict` | The archive destination already exists. |
| `baseline_required` | Code Gates or assurance need a Git repository and a fixed baseline. |
| `invalid_baseline` | The baseline is not a full commit hash. |
| `repository_changed` | The Git repository is not the one fixed for the Change. |
| `git_input_error` | Git returned output that could not be parsed safely. |
| `unsupported_input` | The diff contains an unsupported path, mode, submodule or conflict. |
| `index_worktree_mismatch` | Staged content matches neither HEAD nor the working tree (partial staging); decide which one to deliver. |
| `concurrent_input_change` | Code changed while it was being read. |
| `concurrent_source_change` | A file changed while it was being read. |
| `concurrent_path_change` | A directory was replaced during an operation. |
| `concurrent_write` | Another command holds the Change's write lock. |
| `registry_not_configured` | `config.yaml` has no `registry`. |
| `registry_unavailable` | `git` is not installed or not on `PATH`. |
| `registry_fetch_failed` | `ls-remote` or fetch failed, timed out, the tag does not exist, or the registry moved between check and fetch. |
| `registry_invalid` | The registry tree is unreadable, `path` is missing, or a size or count limit was exceeded. |
| `registry_plan_stale` | No current plan, the plan id differs, or staged or local files changed since `registry update`. |
| `registry_conflict_unresolved` | A conflict has no `--resolve`. |
