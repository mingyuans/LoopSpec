"""Resolution of the bundled `builtin/` resource root, and its packaging."""

import tomllib
from pathlib import Path

from loopspec import builtin_resources
from loopspec.builtin_resources import builtin_root, builtin_schemas_dir, builtin_skills_dir

REPO_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# root resolution
# --------------------------------------------------------------------------- #


def test_source_checkout_falls_back_to_the_repo_root_tree(monkeypatch, tmp_path: Path):
    """An editable install has no `loopspec/builtin` inside the package, so an
    absent -- or present-but-empty -- packaged dir must fall back."""

    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setattr(builtin_resources, "_packaged_root", lambda: empty)
    assert builtin_root() == REPO_ROOT / "builtin"

    monkeypatch.setattr(builtin_resources, "_packaged_root", lambda: tmp_path / "missing")
    assert builtin_root() == REPO_ROOT / "builtin"


def test_packaged_tree_wins_when_it_has_content(monkeypatch, tmp_path: Path):
    packaged = tmp_path / "packaged"
    (packaged / "schemas").mkdir(parents=True)
    monkeypatch.setattr(builtin_resources, "_packaged_root", lambda: packaged)

    assert builtin_root() == packaged
    assert builtin_schemas_dir() == packaged / "schemas"
    assert builtin_skills_dir() == packaged / "skills"


def test_both_resource_trees_resolve_under_the_same_root():
    assert builtin_schemas_dir().parent == builtin_root()
    assert builtin_skills_dir().parent == builtin_root()


def test_the_repo_ships_both_resource_trees():
    assert (REPO_ROOT / "builtin" / "schemas" / "secure-spec-driven" / "schema.yaml").is_file()
    assert sorted(p.name for p in (REPO_ROOT / "builtin" / "skills").glob("*.md")) == [
        "archive.md",
        "bulk-archive.md",
        "continue.md",
        "new.md",
    ]


# --------------------------------------------------------------------------- #
# packaging
# --------------------------------------------------------------------------- #


def test_wheel_force_includes_the_whole_builtin_tree():
    """Moving a resource without updating packaging ships a wheel whose
    `builtin_root()` resolves to nothing -- this is the guard against that."""

    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    force_include = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
    assert force_include == {"builtin": "loopspec/builtin"}
