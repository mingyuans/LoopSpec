# AGENTS.md

Guidance for AI coding agents working in this repository. `CLAUDE.md` is a symlink to this file.

## Index

| Topic | Read before | Document |
|---|---|---|
| **Testing rule (required before finishing any change)**: every change ships BDD scenarios; a change touching skills (`builtin/skills/**`, `src/loopspec/skill_templates.py`, or CLI behaviour a skill relies on) also ships LLM E2E scenarios and passes `make test-llm` | finishing any development work, before committing or opening a PR | [tests/README.md#开发完成前必须做的测试规范](tests/README.md) |
| **CLI output rule**: every `loopspec` command offers two output formats, a plain-text report (the default) and JSON (`--json`) | adding or changing any CLI command or its payload | [CLI output formats](#cli-output-formats) below |
| Test layout, BDD `features/` and `steps/` conventions | adding or changing any test, feature file or step definition | [tests/README.md](tests/README.md) |
| Release guideline: stable and beta tag rules, release steps, CI checks | cutting a release, pushing a tag, or changing version handling (`hatch_version.py`, `install.sh`, `loopspec update`, the release workflow) | [docs/en/release.md](docs/en/release.md) · [docs/zh/release.md](docs/zh/release.md) |
| LLM E2E tests: real-model scenarios, the single `launch_llm` entry point, model and cost limits | adding or changing an LLM scenario, the launcher, or a skill prompt (`builtin/skills/**`) | [tests/README.md#llm-e2e](tests/README.md#llm-e2e) |

## CLI output formats

The loopspec CLI is called mostly by a model (through the loopspec skills), so its output is laid out for a model to read.

- **Every command offers two formats: text (default) and JSON (`--json`).** A command added or changed later must keep both. The only exception is `hook pre-tool-use`, whose output is fixed by the AI tools' hook protocol and stays JSON.
- **Text follows the `change status` contract** (`src/loopspec/status_report.py`, `src/loopspec/text_format.py`): plain text without ANSI, colour or Markdown headings; `=== SECTION ===` lines at column zero, each followed by a prompt paragraph telling the model what the section is and how to use it; `key: value` fields that keep the JSON field names; multi-line or untrusted content (instructions, templates, state, memory, reports) quoted as a bounded block, `--- begin <name> (N lines) ---` … `--- end <name> ---`, with every line in between indented by four spaces and single-line values passed through `sanitize`, so no untrusted value can open a section or a next step; commands to run next in a final `=== NEXT STEPS ===` section; failures as an `=== ERROR ===` report.
- **One payload, two renderings.** The text is rendered only from the payload `--json` prints; never compute extra state for the text. Each command has a hand-written renderer in `src/loopspec/text_reports/`, registered in `RENDERERS` with the payload keys it accounts for; a new payload key must be rendered or listed as deliberately omitted, or `tests/test_text_reports.py` fails.
- **Tests and scripts use `--json`.** Test helpers (`tests/workflow_helpers.invoke`) add `--json`; the text output is covered by `tests/test_text_reports.py` and the `text_output` BDD feature.
