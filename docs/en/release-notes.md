# Release notes

> Scope: what changed in LoopSpec 2.0.0 and how to upgrade from 1.x.
> Audience: users upgrading an existing installation or workspace.
> Language: **English** · [中文](../zh/release-notes.md)

## Unreleased

### `node instructions` gives the Fragment's absolute paths

- New `fragmentName`, `fragmentDir`, `instructionPath`, `templatePath` (`templatePaths` for Gates). In registry mode Fragments live only in the global snapshot; resolve `references/`, `scripts/` and other files an instruction mentions against `fragmentDir`.

### Workflow commands print text reports by default (breaking)

- Every workflow command (`change`, `plan`, `node`, `gate`, `state`, `fragment`, `profile`, `registry`, `memory`) now prints a plain-text report written for an LLM, in the style of `change status`; `--json` prints exactly the JSON it printed before.
- In text mode a failure prints an `=== ERROR ===` report; exit statuses are unchanged. `hook pre-tool-use` still prints JSON only.
- Migration: scripts that parse `loopspec` JSON output must add `--json`. The project's loopspec skills are synced by the next workflow command.

### Workflow commands keep the project's skills in sync

- Every command that accepts `--home` first brings the loopspec skill and command files of the project's configured AI tools in line with this CLI (stale ones rewritten, missing ones added) and reports on stderr; after upgrading the CLI there is no need to rerun `loopspec init` to refresh them.
- Skill and command files holding exactly this CLI's content are always left out of the delivery diff.

### Archiving takes two steps and requires the memory review

- `loopspec change archive <change>` (or `--all`) now only rechecks and returns an `archiveId` with the memory review instructions; finish with `loopspec change archive --confirm <archiveId> --memory updated|none --note <text>`. The CLI checks that memory matches the choice and records the outcome in the Change's `state.md`.
- `--dry-run` is removed (step one is the preview). Scripts using the old form must switch to the two steps; the project's archive skills are synced automatically by the next workflow command.
- Archiving also deletes `.attempts/`, `.gates/`, `.gate-rounds/` and the Gates' PASS/FAIL reports; the result fields are `dropped`/`notDropped`.

### Registry mode: definitions move to a global store

- A project that configures `registry` no longer has fragments/profiles written into it. Definitions are kept per source and commit under `$LOOPSPEC_REGISTRY_STORE` (default `~/.loopspec/registry`); the project commits only `config.yaml` and `registry.lock.yaml`.
- A fresh clone or worktree fetches and verifies the locked commit automatically the first time it reads definitions; no extra command.
- `registry.lock.yaml` is now `version: 2` (`commit`, `tag`, `files`); `registry apply` writes only the lock, `--resolve` and `--skip` are removed, and there is no local three-way merge any more.
- A project definition with a registry name fails with `registry_local_conflict`; local definitions with other names keep working, and `fragment list`/`profile list` gain a `source` field.
- In registry mode `loopspec init` copies no built-in definitions.
- Migration: delete the project definitions that share a name with the registry, run `registry update` and `registry apply`, and commit the deletions and the new lock (see [Configuration](configuration.md)).

## 2.0.0

2.0.0 is not compatible with 1.x. The Schema-based workflow is removed; every Change is now driven by Plans composed from Fragments and Profiles.

### Breaking changes

- **Schema workflow removed.** `loopspec schemas ...`, `builtin/schemas/` and the `secure-spec-driven` Schema are gone. A Change created by 1.x (its `.workflow.yaml` names a `schema`) or by a development build (format 3) reports `unsupported_format`.
- **Command tree.** Commands are `loopspec <resource> <verb>`: `change`, `plan`, `node`, `gate`, `fragment`, `profile`. Flat commands (`new`, `status`, `next`, `instructions`, `rollback`, `history`, `artifacts`, `archive`, `bulk-archive`), the plural groups (`plans`, `fragments`, `profiles`), `assurance check` and `recover` are removed. Options are explicit: `-c/--change`, `-p/--plan`, `-n/--node`, `-f/--file`, `--digest`, `--note`.
- **JSON only.** Workflow commands always print JSON and no longer take `--json`; `version` and `init` keep human output with `--json` available.
- **config.yaml.** Only `artifacts_dir` and `workflow` (`required_fragments`, `assurance_rules`, `excluded_paths`) are accepted. `workflow.generated_dirs` was removed: move its names unchanged into `excluded_paths`. Delete `schema`, `schemas`, `schema_selection`, `context`, `rules` and `workflow.default_profile`.
- **init.** No `schemas/` directory and no `--no-builtin`; missing Fragments and Profiles are copied without overwriting.
- **Archive.** `change archive` replaces `archive` and `bulk-archive` (`--all`, `--older-than`); `--force` replaces `--exhausted` and `--include-pending-failures`.

### New

- Several Plans per Change, at most one open; replanning archives the old Plan with the human's consent and starts from an empty state on the same baseline.
- One `plan.yaml` per Plan (`meta` + `spec`) with digest integrity, per-Plan artifacts, evidence and rework records.
- In-place revisions previewed with `plan validate -f` and confirmed with `plan approve -f --digest`.
- Every command takes effect in a single write: an interrupted command leaves the Change as before or as after, with no transaction file, no recovery command and no interrupted status.
- `workflow.excluded_paths` keeps any path out of the diff, by name or by full path; paths ignored by Git but not excluded only warn in the assurance report instead of stopping commands.
- Evidence digests bind only the baseline and the delivered working tree content, not the index: `git add` or `git commit` after the Gates pass no longer stales evidence, and editing after a commit made since the baseline no longer fails with `index_worktree_mismatch`; a commit in HEAD that is neither the baseline nor the working tree content fails assurance with `diverged_commits`, so commit the final content before delivery. Code Gate and assurance evidence recorded by earlier development builds becomes stale and must be rerun.
- `on_fail` is compiled into each Gate; one policy per Gate, conflicts are errors.
- `nextSteps` lists every ready leaf, and `parallel: true` marks independent steps that may run in parallel (for example one sub agent per node); `change next` adds `nodes`.

### Upgrading

1. Before upgrading, finish and archive in-flight 1.x Changes with LoopSpec 1.x. 2.0.0 does not migrate them; recreate unfinished work with `loopspec change new` and plan it again.
2. Remove the 1.x fields from `config.yaml`; `schemas/` in the workspace is no longer read and may be deleted.
3. Run `loopspec init --tools <your tools> --update-resources` to add the built-in Fragments and Profiles and refresh the Skills.
4. Adjust `evidence.paths` in the code review Fragments and `paths` in `change-assurance/rules.yaml` to your repository layout.
