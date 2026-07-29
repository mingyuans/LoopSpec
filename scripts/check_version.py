#!/usr/bin/env python3
"""Assert the project's version numbers agree, and print the agreed value.

The version lives in two files that are kept in sync by hand:

* ``pyproject.toml`` (``project.version``) -- decides the wheel/sdist filenames
* ``src/loopspec/__init__.py`` (``__version__``) -- the fallback ``loopspec
  version`` uses in a source checkout

The release workflow adds a third source, the git tag, and passes it via
``--expect``. The tag is authoritative for *what gets released*, but the build
artifacts are named from ``pyproject.toml``, so a mismatch has to be caught
before the build rather than showing up as a missing asset afterwards.

Stdlib only, and deliberately no ``import loopspec``: this runs in CI before
dependencies are installed.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
import tomllib
from pathlib import Path

DEFAULT_REPO_ROOT = Path(__file__).resolve().parent.parent

# Same gate the install script applies to LOOPSPEC_VERSION and to the tag_name it
# reads back from the releases API. Anything outside this shape must never reach
# a tag, a URL or a filename.
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+([._-]?(a|b|rc|alpha|beta|dev|post)[0-9]+)?$")


def read_pyproject_version(path: Path) -> str:
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    try:
        version = data["project"]["version"]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"{path}: no project.version") from exc
    if not isinstance(version, str):
        raise ValueError(f"{path}: project.version is not a string")
    return version


def read_dunder_version(path: Path) -> str:
    """Parse ``__version__`` out of the source without importing the package."""
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "__version__":
                value = node.value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    return value.value
                raise ValueError(f"{path}: __version__ is not a string literal")
    raise ValueError(f"{path}: no __version__ assignment")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expect",
        metavar="VERSION",
        help="also require both files to equal this value (the release tag, without 'v')",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=DEFAULT_REPO_ROOT,
        help="repository root to read from (defaults to this script's parent repo)",
    )
    args = parser.parse_args(argv)

    try:
        pyproject_version = read_pyproject_version(args.repo_root / "pyproject.toml")
        init_version = read_dunder_version(args.repo_root / "src" / "loopspec" / "__init__.py")
    except (OSError, ValueError, SyntaxError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    problems: list[str] = []

    if pyproject_version != init_version:
        problems.append(
            f"version drift: pyproject.toml has {pyproject_version!r}, "
            f"src/loopspec/__init__.py has {init_version!r}"
        )

    for label, value in (("pyproject.toml", pyproject_version), ("__init__.py", init_version)):
        if not VERSION_RE.match(value):
            problems.append(f"malformed version in {label}: {value!r}")

    if args.expect is not None:
        if not VERSION_RE.match(args.expect):
            problems.append(f"malformed expected version: {args.expect!r}")
        mismatched = [
            f"{label} has {value!r}"
            for label, value in (
                ("pyproject.toml", pyproject_version),
                ("src/loopspec/__init__.py", init_version),
            )
            if value != args.expect
        ]
        if mismatched:
            problems.append(
                f"expected {args.expect!r} (from the release tag) but " + ", ".join(mismatched)
            )

    if problems:
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        return 1

    print(pyproject_version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
