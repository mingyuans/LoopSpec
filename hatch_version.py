"""Resolve the distribution version for the build backend.

The version is not written down anywhere in this repository: the git tag is the
single source of truth, and this module resolves it for whoever is building.
``pyproject.toml`` wires it in as a ``code`` version source, so the wheel and
sdist filenames come from here.

Resolution order, first hit wins:

1. ``LOOPSPEC_BUILD_VERSION`` -- set by the release workflow from the tag it is
   publishing. Explicit, and the only path CI relies on. A malformed value is an
   error rather than a fallthrough: it means the caller believes it is releasing
   something, and guessing a different version would publish under a name nobody
   asked for.
2. ``git describe --tags --exact-match`` -- a local build of a tagged commit, so
   ``make build`` on a tag produces the same filenames CI would.
3. ``Version:`` from ``PKG-INFO`` -- present at the root of an unpacked sdist.
   Building a wheel from a released sdist has neither the environment variable
   nor a git checkout, and without this the wheel would be named after the dev
   placeholder instead of the release it was built from.
4. ``DEV_VERSION`` -- an untagged working tree. Deliberately not a guess at the
   next release number: an artifact built from here must not look releasable.

Stdlib only, and importable on its own: this runs inside the build backend,
before the project's own dependencies exist.
"""

from __future__ import annotations

import os
import re
import subprocess
from email import message_from_string
from pathlib import Path

ENV_VAR = "LOOPSPEC_BUILD_VERSION"

# What an untagged tree builds as. PEP 440 sorts it below every real release, so
# it can never shadow one in a resolver.
DEV_VERSION = "0.0.0.dev0"

# The same shape install.sh's VERSION_PATTERN and the release workflow's tag
# regex accept. A version that fails this must never reach a filename or a URL.
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+([._-]?(a|b|rc|alpha|beta|dev|post)[0-9]+)?$")

# Resolved from this file, not from the working directory: the build backend does
# not promise to run us from the project root.
ROOT = Path(__file__).resolve().parent


def _accept(value: str | None) -> str | None:
    """Return ``value`` if it is a version we are willing to name a file after."""

    if value is None:
        return None
    value = value.strip()
    return value if VERSION_RE.match(value) else None


def _from_env() -> str | None:
    raw = os.environ.get(ENV_VAR)
    if raw is None:
        return None
    version = _accept(raw)
    if version is None:
        raise ValueError(f"{ENV_VAR}={raw!r} is not a valid version")
    return version


def _from_git() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(ROOT), "describe", "--tags", "--exact-match"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None  # no git available
    if completed.returncode != 0:
        return None  # not a repository, or this commit carries no tag
    tag = completed.stdout.strip()
    return _accept(tag[1:] if tag.startswith("v") else tag)


def _from_pkg_info() -> str | None:
    try:
        text = (ROOT / "PKG-INFO").read_text(encoding="utf-8")
    except OSError:
        return None  # not an unpacked sdist
    return _accept(message_from_string(text).get("Version"))


def resolve_version() -> str:
    for source in (_from_env, _from_git, _from_pkg_info):
        version = source()
        if version is not None:
            return version
    return DEV_VERSION


if __name__ == "__main__":
    print(resolve_version())
