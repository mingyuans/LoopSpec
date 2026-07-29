# LoopSpec

A gated artifact workflow CLI for LLM-driven, spec-driven development. You declare a
YAML graph of artifacts (proposal, specs, design, tasks, ...) and their dependencies;
an LLM generates them one at a time; special *gate* nodes (e.g. a security review)
produce a PASS/FAIL verdict, and a FAIL rolls back to a declared upstream node so the
LLM can redo it with full knowledge of why the previous attempt failed.

Node completion, gate verdicts, and retry counts are all derived from the filesystem
on every call — there is no separate progress database to drift out of sync with
what's actually on disk. Rollbacks *move* (never delete) prior attempts into
`.attempts/round-NNN/`, so the next attempt can be shown exactly what failed and why.

## Documentation

The full manual lives in [`docs/`](docs/README.md), in **English** and **中文**:

- [English manual](docs/en/README.md)
- [中文手册](docs/zh/README.md)

It covers every command and `--json` response field, every `config.yaml` and
`schema.yaml` field, the protocol an agent follows to drive the loop, and the built-in
workflow node by node.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/mingyuans/LoopSpec/main/install.sh | sh
```

The same command installs and updates — re-run it to move to the latest release. It
downloads the wheel from the newest GitHub Release, verifies its SHA256 against the
release's `checksums.txt`, and installs it with `uv tool install` (or `pipx install`
if you don't have uv). Nothing needs `sudo`, and there is no flag to skip the
checksum check.

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

Substitute the version you want; the filenames are listed on each release page. Note
that this path skips the checksum verification the script does for you.

**Windows:** use `uv tool install` directly — `install.sh` is POSIX shell and there is
no PowerShell equivalent.

### Update and uninstall

```bash
# update: the same command as installing
curl -fsSL https://raw.githubusercontent.com/mingyuans/LoopSpec/main/install.sh | sh

# uninstall
uv tool uninstall loopspec     # or: pipx uninstall loopspec
```

If `loopspec` isn't found after installing, the tool directory (usually
`~/.local/bin`) isn't on your `PATH` yet — run `uv tool update-shell` (or
`pipx ensurepath`) and restart your shell.

## Releases

Publishing is driven by tags, not by commits. Pushing to `main` runs the checks and
builds; it never creates a release. To publish:

```bash
# 1. set the version in BOTH places, and merge that to main
#      pyproject.toml        -> project.version
#      src/loopspec/__init__.py -> __version__
# 2. tag a commit on main
git tag v0.2.0
# 3. push the tag -- this is what publishes
git push origin v0.2.0
```

The release version comes from the tag name. CI requires the tag to agree with both
version declarations and fails before building if it doesn't — the wheel's filename
comes from `pyproject.toml`, so a mismatch would otherwise produce a release whose
assets are named after a different version. It also requires the tagged commit to be
reachable from `main`, and refuses to overwrite an existing release for the same tag.

`make release-dry-run TAG=v0.2.0` runs the checks that don't need CI, so you can catch
a version mismatch before spending a tag on it.

Each release carries three assets:

- `loopspec-<version>-py3-none-any.whl`
- `loopspec-<version>.tar.gz`
- `checksums.txt` — SHA256 of the two above, which `install.sh` verifies

Two things to know before the first release:

- **Repository setting.** `Settings → Actions → General → Workflow permissions` must
  allow *Read and write*, otherwise creating the release fails with a 403.
- **Anyone who can push a `v*` tag can publish.** The workflow constrains *what* can
  be released (a commit on `main`, declaring the version the tag names, not already
  released) but not *who* may release it. If that matters for your fork, restrict tag
  pushes with a repository ruleset — that's a repository setting, not something this
  workflow enforces.

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

Every command supports `--json` for machine-readable output — that's the primary
protocol for driving `loopspec` from an LLM/agent. Omit `--json` for a plain-text
summary intended for humans.

Two nodes in the built-in schema ask the agent for something other than another
document, so a driving loop needs to expect them: `approval` is a human sign-off gate
(the agent must never approve on your behalf), and `apply` is the implementation gate,
which only counts as done once every checkbox in `tasks.md` is ticked. See
[the built-in workflow](docs/en/workflows/secure-spec-driven.md) and
[the agent protocol](docs/en/agent-protocol.md).

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

`make release-dry-run` accepts `TAG=v0.2.0` to also verify a tag name against the two
version declarations. It skips `shellcheck` when it isn't installed locally; CI treats
it as mandatory.

The built-in `secure-spec-driven` schema lives in `schemas/secure-spec-driven/` at
the repo root and is bundled into the installed package. `make docs-check` asserts the
manual has not drifted from the code, and that the two language versions still match.
