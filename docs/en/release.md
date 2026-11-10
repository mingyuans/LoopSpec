# Release guideline

> Scope: how LoopSpec versions are numbered, how to cut a stable or beta release, what CI checks, and what users get from each.
> Audience: maintainers and AI agents about to tag a release or change version handling.
> Language: **English** · [中文](../zh/release.md)

A release is published by pushing a tag. Nothing else creates one: pushing to `main` runs the checks and builds, but never publishes.

## Version rules

There are exactly two tag shapes. CI rejects any other tag, including `v1.1.4-beta1`, `v1.1.4b0`, `v1.1.4-rc` and `v1.1.4-my-branch`.

| Kind | Tag | Package version | Next one |
| --- | --- | --- | --- |
| Stable | `vX.Y.0` | `X.Y.0` | Bump Y, reset Z: after `v1.2.0` comes `v1.3.0`. |
| Beta | `vX.Y.Z-beta` | `X.Y.Zb0` | Bump Z: after `v1.1.4-beta` comes `v1.1.5-beta`. |

- The package version of a beta is its PEP 440 form. For tag `v1.1.4-beta`, `loopspec version` prints `1.1.4b0` and the assets are `loopspec-1.1.4b0-py3-none-any.whl` and `loopspec-1.1.4b0.tar.gz`. The tag on GitHub keeps the `-beta` spelling.
- A stable release keeps the patch at `0`. CI accepts any `vX.Y.Z`, so this rule is enforced here, not by the workflow; a non-zero patch is reserved for an urgent fix that cannot wait for the next minor.
- `v1.1.1` to `v1.1.3` predate these rules and stay as they are.
- A beta must sort above the latest stable to be offered by `loopspec update --beta`: pick Z greater than the latest stable's patch (or a higher Y).

Example sequence:

```text
v1.1.3         stable (predates the rules)
v1.1.4-beta    beta, package 1.1.4b0
v1.1.5-beta    beta, package 1.1.5b0
v1.2.0         next stable
```

The tag is the only place a version is declared. `pyproject.toml` marks the version `dynamic`, and `hatch_version.py` resolves it at build time, in this order: `LOOPSPEC_BUILD_VERSION` if set (CI sets it from the tag it validated), else the tag on the current commit (a `-beta` tag maps to `b0`), else the `Version:` in `PKG-INFO` when building from a released sdist, else `0.0.0.dev0`. There is no version-bump commit to make.

## Cutting a release

1. Merge the work to `main` and make sure the `main` checks are green.
2. Pick the tag from the rules above. Check the existing tags with `git tag --list 'v*'` and the Releases page.
3. Dry-run the build for that tag. It builds what the tag would publish and asserts the asset names:

   ```bash
   make release-dry-run TAG=v1.2.0
   make release-dry-run TAG=v1.1.4-beta   # expects loopspec-1.1.4b0-*
   ```

4. Tag a commit on `main` and push the tag. Pushing the tag is what publishes:

   ```bash
   git checkout main && git pull
   git tag v1.2.0
   git push origin v1.2.0
   ```

5. Follow the release workflow run in GitHub Actions until it finishes.
6. Verify the Release page: three assets are attached; a stable release is marked **Latest**; a beta is marked **Pre-release** and the Latest badge stays on the previous stable.

## What CI does

The release workflow runs on a pushed `v*` tag and:

- validates the tag shape and derives the package version (`X.Y.Z`, or `X.Y.Zb0` for a beta) and whether it is a pre-release;
- runs lint and the tests;
- requires the tagged commit to be reachable from `main`;
- refuses to run when a release for the tag already exists;
- builds the wheel and sdist, asserts they are named after the package version, and writes `checksums.txt`;
- creates the GitHub Release: a stable one with `--latest`, a beta with `--prerelease --latest=false`, so a beta is never marked Latest.

Stable and beta go through the same build and publish the same three assets:

- `loopspec-<version>-py3-none-any.whl`
- `loopspec-<version>.tar.gz`
- `checksums.txt`: SHA256 of the two above, which `install.sh` and `loopspec update` verify

Repository prerequisites:

- `Settings -> Actions -> General -> Workflow permissions` must allow *Read and write*, otherwise creating the release fails with a 403.
- Anyone who can push a `v*` tag can publish. The workflow constrains *what* can be released, not *who*; restrict tag pushes with a repository ruleset if that matters.

## What users get

| Path | Installs |
| --- | --- |
| `install.sh` | The latest stable release only. `LOOPSPEC_VERSION` accepts only `X.Y.Z`; a beta value is rejected with a hint to run `loopspec update --beta`. |
| `loopspec update` | The latest stable release (from `releases/latest`). It never downgrades: an installed beta newer than the latest stable stays until a newer stable is out. |
| `loopspec update --beta` | The newest release, beta included, read from the repository's `releases.atom` feed. The feed lists recent releases only; `api.github.com` is not used. If the newest tag's release answers HTTP 404 (CI still running or failed), up to 3 tags are tried, newest first; any other failure stops the update. |
| `loopspec update --version <v>` | Exactly that release, even an older one or the installed one. Accepts `X.Y.Z`, `X.Y.Z-beta` or `X.Y.Zb0`. |

`--check` reports without installing and also works with `--beta`. `--beta` and `--version` cannot be combined (`update_invalid_version`). See the [CLI reference](cli-reference.md#loopspec-update).

## When something goes wrong

- **CI failed before publishing** (lint, tests, reachability, build): fix it on `main`, then move the tag. Delete the remote and local tag, re-tag the fixed commit and push again:

  ```bash
  git push origin :refs/tags/v1.2.0
  git tag -d v1.2.0
  git tag v1.2.0
  git push origin v1.2.0
  ```

- **A bad release was published**: delete the release together with its tag, then re-push the tag on the fixed commit:

  ```bash
  gh release delete v1.2.0 --cleanup-tag --yes
  git tag -d v1.2.0
  git tag v1.2.0
  git push origin v1.2.0
  ```

  If users may already have installed it, prefer bumping to the next version instead of reusing the tag.
- **The tag was rejected**: the tag is neither `vX.Y.Z` nor `vX.Y.Z-beta`. Delete it and push a correctly shaped one.
- **A beta became Latest** (for example, published or edited by hand): mark the latest stable as Latest on the Releases page. `install.sh` and `loopspec update` read `releases/latest`; `install.sh` and the default `loopspec update` both refuse a non-stable version there, so both fail instead of installing the beta until it is fixed.
