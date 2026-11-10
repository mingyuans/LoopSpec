# LoopSpec

A plan-driven, gated delivery CLI for LLM agents. For each Change, an agent drafts one Plan for the whole task from reusable Fragments and Profiles; a human confirms it by digest; the agent then executes the confirmed graph node by node. Code Gates count only with review evidence bound to the exact code reviewed, and a final assurance node checks the full Git diff since the Change's fixed baseline. A failed Gate sends work back by its own `on_fail`, archiving the failed attempt so the redo can see why.

Node status is derived from the filesystem on every call; there is no progress database to drift. Every Plan, revision and replan becomes effective only with the digest a human was shown.

## Documentation

The full manual lives in [`docs/`](docs/README.md), in **English** and **中文**:

- [English manual](docs/en/README.md)
- [中文手册](docs/zh/README.md)

It covers every command and its JSON output, writing Fragments, Profiles and Plan requests, every `plan.yaml` and `config.yaml` field, and the protocol an agent follows. Upgrading from 1.x? Read the [release notes](docs/en/release-notes.md): 2.0.0 removes the Schema workflow.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/mingyuans/LoopSpec/main/install.sh | sh
```

The same command installs and updates — re-run it to move to the latest release. It installs stable releases only: it downloads the wheel from the latest stable GitHub Release (betas are never marked Latest), verifies its SHA256 against the release's `checksums.txt`, and installs it with `uv tool install` (or `pipx install` if you don't have uv). Nothing needs `sudo`, and there is no flag to skip the checksum check.

If you'd rather read the script before running it:

```bash
curl -fsSLO https://raw.githubusercontent.com/mingyuans/LoopSpec/main/install.sh
less install.sh
sh install.sh
```

Pin a specific stable version with `LOOPSPEC_VERSION` (only `X.Y.Z`; a beta such as `1.1.4-beta` is rejected, use `loopspec update --beta` or `--version` instead):

```bash
curl -fsSL https://raw.githubusercontent.com/mingyuans/LoopSpec/main/install.sh \
  | LOOPSPEC_VERSION=1.0.3 sh
```

### Without the script

The wheel is a normal `py3-none-any` wheel, so any tool that installs CLI apps works:

```bash
uv tool install https://github.com/mingyuans/LoopSpec/releases/latest/download/loopspec-1.0.3-py3-none-any.whl
# or
pipx install https://github.com/mingyuans/LoopSpec/releases/latest/download/loopspec-1.0.3-py3-none-any.whl
```

Substitute the version you want; the filenames are listed on each release page. Note that this path skips the checksum verification the script does for you.

**Windows:** use `uv tool install` directly — `install.sh` is POSIX shell and there is no PowerShell equivalent.

### Update and uninstall

```bash
# update: verifies the release's SHA256 and reinstalls with uv (or pipx), like install.sh
loopspec update                    # latest stable; never downgrades an installed beta
loopspec update --check            # only report whether a newer release exists
loopspec update --beta             # newest release, betas included (works with --check)
loopspec update --version 2.0.0    # install an exact release
loopspec update --version 1.1.4-beta   # an exact beta; installs package version 1.1.4b0

# or, e.g. when the installed CLI is too old to have `update`: the install command
curl -fsSL https://raw.githubusercontent.com/mingyuans/LoopSpec/main/install.sh | sh

# uninstall
uv tool uninstall loopspec     # or: pipx uninstall loopspec
```

If `loopspec` isn't found after installing, the tool directory (usually `~/.local/bin`) isn't on your `PATH` yet — run `uv tool update-shell` (or `pipx ensurepath`) and restart your shell.

## Releases

Publishing is driven by tags, not by commits: pushing a `vX.Y.0` tag on `main` publishes a stable release, pushing a `vX.Y.Z-beta` tag publishes a beta as a pre-release (package version `X.Y.Zb0`, never marked Latest). Run `make release-dry-run TAG=<tag>` before spending a tag. The tag is the only place a version is declared.

Version rules, release steps, what CI checks and how to recover from a bad release are in the [release guideline](docs/en/release.md) ([中文](docs/zh/release.md)).

## Quick start

```bash
# 1. Initialize a workflow home with the built-in Fragments and Profiles.
#    Add --tools claude,codex to also scaffold agent skills and /lpsx:* commands.
loopspec init ./loopspec

# 2. Create a Change and draft one Plan for the whole task.
loopspec change new AFD1111
loopspec profile show bugfix
#    write loopspec/changes/AFD1111/plans/request.yaml, then:
loopspec plan validate -c AFD1111 -f changes/AFD1111/plans/request.yaml
loopspec plan create -c AFD1111 -f changes/AFD1111/plans/request.yaml
loopspec plan show -c AFD1111 -p 001

# 3. Show the draft to a human; only after explicit confirmation:
loopspec plan approve -c AFD1111 -p 001 --digest "<shown digest>"

# 4. Loop: ask what to do next, do it, repeat.
loopspec change status AFD1111
loopspec node instructions -c AFD1111 -n requirements/proposal

# A failed Gate: nextSteps names the rollback.
loopspec plan rollback -c AFD1111 -p 001

# Once complete:
loopspec change archive AFD1111
```

Workflow commands always print JSON for the agent driving the loop; `version` and `init` print human-readable output. See the [agent protocol](docs/en/agent-protocol.md) for revisions, replanning and what happens when a command is interrupted.

## Development

```bash
make install          # uv sync -- package + dev tools (pytest, ruff, mypy) into .venv
make test             # uv run pytest -v
make lint             # ruff check + mypy
make docs-check       # docs/code consistency only
make build            # uv build
make install-local    # build, then uv tool install the wheel as the global `loopspec`
make release-dry-run  # install.sh checks + build (add TAG= to check artifact names)
make clean            # remove build/test caches
```

`make release-dry-run` accepts `TAG=v0.2.0` to also build the artifacts that tag would publish and assert their filenames -- there is no declared version for it to check them against, only the tag. It skips `shellcheck` when it isn't installed locally; CI treats it as mandatory.

Everything that ships as data lives under `builtin/` at the repo root and is bundled into the installed package: the built-in Fragments and Profiles in `builtin/fragments/` and `builtin/profiles/`, and the Agent Skill bodies `loopspec init` writes in `builtin/skills/` (one Markdown file per `/lpsx:*` command, edit it and the next `init` writes the new text). `make docs-check` asserts the manual has not drifted from the code, and that the two language versions still match.
