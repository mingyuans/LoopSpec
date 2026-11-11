# AGENTS.md

Guidance for AI coding agents working in this repository. `CLAUDE.md` is a symlink to this file.

## Index

| Topic | Read before | Document |
|---|---|---|
| **Testing rule (required before finishing any change)**: every change ships BDD scenarios; a change touching skills (`builtin/skills/**`, `src/loopspec/skill_templates.py`, or CLI behaviour a skill relies on) also ships LLM E2E scenarios and passes `make test-llm` | finishing any development work, before committing or opening a PR | [tests/README.md#开发完成前必须做的测试规范](tests/README.md) |
| Test layout, BDD `features/` and `steps/` conventions | adding or changing any test, feature file or step definition | [tests/README.md](tests/README.md) |
| Release guideline: stable and beta tag rules, release steps, CI checks | cutting a release, pushing a tag, or changing version handling (`hatch_version.py`, `install.sh`, `loopspec update`, the release workflow) | [docs/en/release.md](docs/en/release.md) · [docs/zh/release.md](docs/zh/release.md) |
| LLM E2E tests: real-model scenarios, the single `launch_llm` entry point, model and cost limits | adding or changing an LLM scenario, the launcher, or a skill prompt (`builtin/skills/**`) | [tests/README.md#llm-e2e](tests/README.md#llm-e2e) |
