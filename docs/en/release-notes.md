# Release notes

> Scope: what changed in LoopSpec 2.0.0 and how to upgrade from 1.x.
> Audience: users upgrading an existing installation or workspace.
> Language: **English** · [中文](../zh/release-notes.md)

## 2.0.0

2.0.0 is not compatible with 1.x. The Schema-based workflow is removed; every Change is now driven by Plans composed from Fragments and Profiles.

### Breaking changes

- **Schema workflow removed.** `loopspec schemas ...`, `builtin/schemas/` and the `secure-spec-driven` Schema are gone. A Change created by 1.x (its `.workflow.yaml` names a `schema`) or by a development build (format 3) reports `unsupported_format`.
- **Command tree.** Commands are `loopspec <resource> <verb>`: `change`, `plan`, `node`, `gate`, `fragment`, `profile`. Flat commands (`new`, `status`, `next`, `instructions`, `rollback`, `history`, `artifacts`, `archive`, `bulk-archive`), the plural groups (`plans`, `fragments`, `profiles`), `assurance check` and `recover` are removed. Options are explicit: `-c/--change`, `-p/--plan`, `-n/--node`, `-f/--file`, `--digest`, `--note`.
- **JSON only.** Workflow commands always print JSON and no longer take `--json`; `version` and `init` keep human output with `--json` available.
- **config.yaml.** Only `artifacts_dir` and `workflow` (`required_fragments`, `assurance_rules`, `generated_dirs`) are accepted. Delete `schema`, `schemas`, `schema_selection`, `context`, `rules` and `workflow.default_profile`.
- **init.** No `schemas/` directory and no `--no-builtin`; missing Fragments and Profiles are copied without overwriting.
- **Archive.** `change archive` replaces `archive` and `bulk-archive` (`--all`, `--older-than`); `--force` replaces `--exhausted` and `--include-pending-failures`.

### New

- Several Plans per Change, at most one open; replanning archives the old Plan with the human's consent and starts from an empty state on the same baseline.
- One `plan.yaml` per Plan (`meta` + `spec`) with digest integrity, per-Plan artifacts, evidence and rework records.
- In-place revisions previewed with `plan validate -f` and confirmed with `plan approve -f --digest`.
- Every command takes effect in a single write: an interrupted command leaves the Change as before or as after, with no transaction file, no recovery command and no interrupted status.
- `on_fail` is compiled into each Gate; one policy per Gate, conflicts are errors.

### Upgrading

1. Before upgrading, finish and archive in-flight 1.x Changes with LoopSpec 1.x. 2.0.0 does not migrate them; recreate unfinished work with `loopspec change new` and plan it again.
2. Remove the 1.x fields from `config.yaml`; `schemas/` in the workspace is no longer read and may be deleted.
3. Run `loopspec init --tools <your tools>` to add the built-in Fragments and Profiles and refresh the Skills.
4. Adjust `evidence.paths` in the code review Fragments and `paths` in `change-assurance/rules.yaml` to your repository layout.
