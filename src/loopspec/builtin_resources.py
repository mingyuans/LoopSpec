"""Where the resources that ship with loopspec live on disk.

`builtin/` at the repo root holds both bundled resource trees -- the built-in
schemas and the built-in skill bodies -- and is force-included into the wheel
as `loopspec/builtin` (see `[tool.hatch.build.targets.wheel.force-include]`).
So an installed package resolves inside itself, while an editable/source
checkout -- where `src/loopspec` has no such copy -- falls back to the
repo-root tree, and editing a resource there takes effect without reinstalling.

Both trees resolve through the one `builtin_root()`, so a future move cannot
leave schemas and skills looking for different roots.
"""

from __future__ import annotations

import importlib.resources
from pathlib import Path

#: `src/loopspec/builtin_resources.py` -> repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _packaged_root() -> Path:
    return Path(str(importlib.resources.files("loopspec") / "builtin"))


def builtin_root() -> Path:
    """The bundled resource root: inside the package if present, else repo-root."""

    packaged = _packaged_root()
    if packaged.is_dir() and any(packaged.iterdir()):
        return packaged
    return _REPO_ROOT / "builtin"


def builtin_schemas_dir() -> Path:
    return builtin_root() / "schemas"


def builtin_skills_dir() -> Path:
    return builtin_root() / "skills"
