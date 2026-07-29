# LoopSpec

A gated artifact workflow CLI for LLM-driven, spec-driven development. You declare a YAML graph of artifacts (proposal, specs, design, tasks, ...) and their dependencies; an LLM generates them one at a time; special *gate* nodes (e.g. a security review) produce a PASS/FAIL verdict, and a FAIL rolls back to a declared upstream node so the LLM can redo it with full knowledge of why the previous attempt failed.

Node completion, gate verdicts, and retry counts are all derived from the filesystem on every call — there is no separate progress database to drift out of sync with what's actually on disk. Rollbacks *move* (never delete) prior attempts into `.attempts/round-NNN/`, so the next attempt can be shown exactly what failed and why.

## Documentation

The full manual lives in [`docs/`](docs/README.md), in **English** and **中文**:

- [English manual](docs/en/README.md)
- [中文手册](docs/zh/README.md)

It covers every command and `--json` response field, every `config.yaml` and `schema.yaml` field, the protocol an agent follows to drive the loop, and the built-in workflow node by node.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/mingyuans/LoopSpec/main/install.sh | sh
```

The same command installs and updates — re-run it to move to the latest release. It downloads the wheel from the newest GitHub Release, verifies its SHA256 against the release's `checksums.txt`, and installs it with `uv tool install` (or `pipx install` if you don't have uv). Nothing needs `sudo`, and there is no flag to skip the checksum check.

If you'd rather read the script before running it:

```bash
curl -fsSLO https://raw.githubusercontent.com/mingyuans/LoopSpec/main/install.sh
less install.sh
sh install.sh
```

Pin a specific version with `LOOPSPEC_VERSION`:

```bash
curl -fsSL https://raw.githubusercontent.com/mingyuans/LoopSpec/main/install.sh \
  | LOOPSPEC_VERSION=0.1.0 sh
```

### Without the script

The wheel is a normal `py3-none-any` wheel, so any tool that installs CLI apps works:

```bash
uv tool install https://github.com/mingyuans/LoopSpec/releases/latest/download/loopspec-0.1.0-py3-none-any.whl
# or
pipx install https://github.com/mingyuans/LoopSpec/releases/latest/download/loopspec-0.1.0-py3-none-any.whl
```

Substitute the version you want; the filenames are listed on each release page. Note that this path skips the checksum verification the script does for you.

**Windows:** use `uv tool install` directly — `install.sh` is POSIX shell and there is no PowerShell equivalent.

### Update and uninstall

```bash
# update: the same command as installing
curl -fsSL https://raw.githubusercontent.com/mingyuans/LoopSpec/main/install.sh | sh

# uninstall
uv tool uninstall loopspec     # or: pipx uninstall loopspec
```

If `loopspec` isn't found after installing, the tool directory (usually `~/.local/bin`) isn't on your `PATH` yet — run `uv tool update-shell` (or `pipx ensurepath`) and restart your shell.

## Releases

Publishing is driven by tags, not by commits. Pushing to `main` runs the checks and builds; it never creates a release. To publish:

```bash
# 1. tag a commit on main
git tag v0.2.0
# 2. push the tag -- this is what publishes
git push origin v0.2.0
```

The tag is the only place a version is declared. Nothing in the repository repeats it: `pyproject.toml` marks the version `dynamic`, and `hatch_version.py` resolves it at build time from `LOOPSPEC_BUILD_VERSION`, which the workflow sets from the tag it validated. So there is no second declaration for a tag to disagree with, and no version-bump commit to forget.

CI still requires the tagged commit to be reachable from `main`, refuses to overwrite an existing release for the same tag, and verifies after building that the assets are named after the tag.

Building outside a release resolves the same way, in this order: `LOOPSPEC_BUILD_VERSION` if set, else the tag on the current commit (`make build` on a tagged commit produces exactly what CI would), else the `Version:` in `PKG-INFO` when building from a released sdist, else `0.0.0.dev0` for an untagged tree — deliberately not a guess at the next release number, so a local build can't be mistaken for a releasable one.

`make release-dry-run TAG=v0.2.0` builds the artifacts that tag would publish and asserts their filenames, so you can check a release before spending a tag on it.

Each release carries three assets:

- `loopspec-<version>-py3-none-any.whl`
- `loopspec-<version>.tar.gz`
- `checksums.txt` — SHA256 of the two above, which `install.sh` verifies

Two things to know before the first release:

- **Repository setting.** `Settings → Actions → General → Workflow permissions` must allow *Read and write*, otherwise creating the release fails with a 403.
- **Anyone who can push a `v*` tag can publish.** The workflow constrains *what* can be released (a commit on `main`, declaring the version the tag names, not already released) but not *who* may release it. If that matters for your fork, restrict tag pushes with a repository ruleset — that's a repository setting, not something this workflow enforces.

## Quick start

```bash
# 1. Initialize a workflow home (copies the built-in `secure-spec-driven` schema).
#    Add --tools claude,codex to also scaffold agent skills and /lpsx:* commands;
#    run it in a terminal without --tools to pick from a searchable list.
loopspec init ./loopspec

# 2. Create a change
loopspec new add-payment --home ./loopspec --json

# 3. Ask what to do next
loopspec status add-payment --home ./loopspec --json
#   -> nextSteps tells you to run `loopspec instructions <node> --change ...`

# 4. Get the instructions for the next node, write the artifact it describes,
#    then go back to step 3.
loopspec instructions proposal --change add-payment --home ./loopspec --json

# If a gate fails, `status` returns a `pendingRollback` command:
loopspec rollback add-payment --home ./loopspec --json
# ...then redo the reset nodes; `instructions` will include `priorAttempts`
# with the previous failure's blocking issues so you don't repeat them.

# Once everything is done:
loopspec archive add-payment --home ./loopspec --json
```

Every command supports `--json` for machine-readable output — that's the primary protocol for driving `loopspec` from an LLM/agent. Omit `--json` for a plain-text summary intended for humans.

Two nodes in the built-in schema ask the agent for something other than another document, so a driving loop needs to expect them: `approval` is a human sign-off gate (the agent must never approve on your behalf), and `apply` is the implementation gate, which only counts as done once every checkbox in `tasks.md` is ticked. See [the built-in workflow](docs/en/workflows/secure-spec-driven.md) and [the agent protocol](docs/en/agent-protocol.md).

## Development

```bash
make install          # uv sync -- package + dev tools (pytest, ruff, mypy) into .venv
make test             # uv run pytest -v
make lint             # ruff check + mypy
make docs-check       # docs/code consistency only
make build            # uv build
make release-dry-run  # version check + install.sh checks + build
make clean            # remove build/test caches
```

`make release-dry-run` accepts `TAG=v0.2.0` to also verify a tag name against the two version declarations. It skips `shellcheck` when it isn't installed locally; CI treats it as mandatory.

The built-in `secure-spec-driven` schema lives in `schemas/secure-spec-driven/` at the repo root and is bundled into the installed package. `make docs-check` asserts the manual has not drifted from the code, and that the two language versions still match.
