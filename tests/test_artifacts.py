"""Cross-schema, cross-location artifact discovery.

The fixtures build real workflow homes under `tmp_path` and write real files,
because every claim this module makes is about what is actually on disk --
probing a schema's patterns, following an archive month, resolving a symlink.
Mocking the filesystem would test the mock.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from loopspec import artifacts as artifacts_mod
from loopspec import config as config_mod
from loopspec.artifacts import (
    ACTIVE,
    ARCHIVED,
    discover_artifacts,
    discover_locations,
    resolve_requested_schemas,
)
from loopspec.errors import (
    ChangeNotFoundError,
    ConfigValidationError,
    InvalidChangeNameError,
    SchemaNotFoundError,
)

FULL_SCHEMA = """
name: {name}
version: 1
nodes:
  - id: proposal
    generates: proposal.md
    description: proposal
    template: proposal.md
    requires: []
    instruction: "write it"
  - id: specs
    generates: "specs/**/*.md"
    description: specs
    template: spec.md
    requires: [proposal]
    instruction: "write it"
  - id: review
    generates: null
    description: review gate
    template: null
    requires: [specs]
    instruction: "judge it"
    gate:
      outputs:
        pass: review/pass.md
        fail: review/fail.md
      templates:
        pass: pass.md
        fail: fail.md
      on_fail:
        reset: [specs]
        max_retries: 2
"""

NOTES_SCHEMA = """
name: {name}
version: 1
nodes:
  - id: notes
    generates: notes.md
    description: notes
    template: proposal.md
    requires: []
    instruction: "write it"
"""

TEMPLATE_NAMES = ("proposal.md", "spec.md", "pass.md", "fail.md")


def write_schema(home: Path, name: str, body: str) -> None:
    schema_dir = home / "schemas" / name
    (schema_dir / "templates").mkdir(parents=True)
    (schema_dir / "schema.yaml").write_text(body.format(name=name), encoding="utf-8")
    for template in TEMPLATE_NAMES:
        (schema_dir / "templates" / template).write_text("placeholder\n", encoding="utf-8")


def make_home(tmp_path: Path, config: str, schemas: dict[str, str] | None = None) -> Path:
    """A workflow home with the given `config.yaml` and schema directories."""

    home = tmp_path / "wf"
    (home / "changes").mkdir(parents=True)
    for name, body in (schemas or {"main": FULL_SCHEMA}).items():
        write_schema(home, name, body)
    (home / "config.yaml").write_text(config, encoding="utf-8")
    return home


def single_schema_home(tmp_path: Path) -> Path:
    return make_home(tmp_path, "artifacts_dir: changes\nschema: main\n")


def relay_home(tmp_path: Path) -> Path:
    """Two schemas whose artifacts live under different `path` subdirectories."""

    return make_home(
        tmp_path,
        """
artifacts_dir: changes
schemas:
  - name: main
    path: plan
  - name: notes
    path: notes
""",
        {"main": FULL_SCHEMA, "notes": NOTES_SCHEMA},
    )


def declare(change_dir: Path, schema: str, created: str = "2026-07-01") -> Path:
    """Write a location's `.workflow.yaml`, creating the directory if needed."""

    change_dir.mkdir(parents=True, exist_ok=True)
    config_mod.write_metadata(change_dir, schema, created)
    return change_dir


def make_change(home: Path, name: str, schema: str, *, subdir: str = "") -> Path:
    change_dir = declare(home / "changes" / name, schema)
    root = change_dir / subdir if subdir else change_dir
    root.mkdir(parents=True, exist_ok=True)
    (change_dir / "state.md").write_text("# Change State\n", encoding="utf-8")
    return root


def write(path: Path, body: str = "x\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def report_for(home: Path, change: str, requested: list[str] | None = None):
    return discover_artifacts(home, config_mod.load_config(home), change, requested)


def names_of(paths: list[Path], root: Path) -> set[str]:
    return {path.relative_to(root.resolve()).as_posix() for path in paths}


def snapshot(root: Path) -> set[str]:
    return {path.relative_to(root).as_posix() for path in root.rglob("*")}


# --------------------------------------------------------------------------- #
# --schemas parsing
# --------------------------------------------------------------------------- #


def test_omitted_schemas_option_means_every_known_schema():
    assert resolve_requested_schemas(None) is None


def test_schemas_option_splits_dedupes_and_preserves_first_order():
    assert resolve_requested_schemas("b, a ,b") == ["b", "a"]


@pytest.mark.parametrize("raw", ["", "   ", ",", " , "])
def test_schemas_option_that_strips_to_nothing_is_rejected(raw: str):
    """An empty value is not the same as omitting the option -- see design D10."""

    with pytest.raises(ConfigValidationError):
        resolve_requested_schemas(raw)


@pytest.mark.parametrize("raw", ["../../etc", "/abs/path", "a/b", "Upper", "under_score"])
def test_schemas_option_rejects_names_that_are_not_kebab_case(raw: str):
    with pytest.raises(ConfigValidationError):
        resolve_requested_schemas(raw)


# --------------------------------------------------------------------------- #
# locations
# --------------------------------------------------------------------------- #


def test_active_only_change_yields_one_active_location(tmp_path: Path):
    home = single_schema_home(tmp_path)
    make_change(home, "alpha", "main")

    found = discover_locations(home, "changes", "alpha")
    assert [(kind, month) for kind, month, _dir in found] == [(ACTIVE, None)]


def test_archived_change_is_found_after_the_directory_moved(tmp_path: Path):
    home = single_schema_home(tmp_path)
    archived = home / "archive" / "2026-07" / "alpha"
    write(archived / "proposal.md")

    found = discover_locations(home, "changes", "alpha")
    assert [(kind, month) for kind, month, _dir in found] == [(ARCHIVED, "2026-07")]


def test_active_and_archived_copies_are_both_reported(tmp_path: Path):
    home = single_schema_home(tmp_path)
    make_change(home, "alpha", "main")
    write(home / "archive" / "2026-06" / "alpha" / "proposal.md")

    found = discover_locations(home, "changes", "alpha")
    assert [(kind, month) for kind, month, _dir in found] == [(ARCHIVED, "2026-06"), (ACTIVE, None)]


def test_locations_run_oldest_first_with_active_last(tmp_path: Path):
    """The order is contract: a relay reads earlier stretches before the current one."""

    home = single_schema_home(tmp_path)
    make_change(home, "alpha", "main")
    write(home / "archive" / "2026-07" / "alpha" / "proposal.md")
    write(home / "archive" / "2026-06" / "alpha" / "proposal.md")

    found = discover_locations(home, "changes", "alpha")
    assert [(kind, month) for kind, month, _dir in found] == [
        (ARCHIVED, "2026-06"),
        (ARCHIVED, "2026-07"),
        (ACTIVE, None),
    ]


def test_change_missing_from_every_location_is_not_found(tmp_path: Path):
    home = single_schema_home(tmp_path)
    with pytest.raises(ChangeNotFoundError):
        discover_locations(home, "changes", "nope")


def test_archive_month_directory_name_is_not_required_to_be_year_month(tmp_path: Path):
    """A hand-reorganised archive must not make artifacts vanish (design D2)."""

    home = single_schema_home(tmp_path)
    write(home / "archive" / "2026-Q3" / "alpha" / "proposal.md")

    found = discover_locations(home, "changes", "alpha")
    assert [month for _kind, month, _dir in found] == ["2026-Q3"]


@pytest.mark.parametrize("name", ["../escape", "../../etc", "a/../../b"])
def test_unsafe_change_name_is_rejected_before_any_path_is_joined(tmp_path: Path, name: str):
    home = single_schema_home(tmp_path)
    with pytest.raises(InvalidChangeNameError):
        report_for(home, name)


# --------------------------------------------------------------------------- #
# probing
# --------------------------------------------------------------------------- #


def test_every_node_output_is_attributed_to_its_node(tmp_path: Path):
    home = single_schema_home(tmp_path)
    root = make_change(home, "alpha", "main")
    write(root / "proposal.md")
    write(root / "specs" / "cap" / "spec.md")
    write(root / "review" / "pass.md")

    location = report_for(home, "alpha").locations[0]
    by_node = {node.id: names_of(node.files, root) for node in location.schemas[0].nodes}
    assert by_node == {
        "proposal": {"proposal.md"},
        "specs": {"specs/cap/spec.md"},
        "review": {"review/pass.md"},
    }


def test_glob_output_expands_to_every_matching_file(tmp_path: Path):
    home = single_schema_home(tmp_path)
    root = make_change(home, "alpha", "main")
    write(root / "specs" / "one" / "spec.md")
    write(root / "specs" / "two" / "spec.md")

    location = report_for(home, "alpha").locations[0]
    specs = next(node for node in location.schemas[0].nodes if node.id == "specs")
    assert names_of(specs.files, root) == {"specs/one/spec.md", "specs/two/spec.md"}


def test_gate_reports_only_the_side_that_exists(tmp_path: Path):
    home = single_schema_home(tmp_path)
    root = make_change(home, "alpha", "main")
    write(root / "review" / "fail.md")

    location = report_for(home, "alpha").locations[0]
    review = next(node for node in location.schemas[0].nodes if node.id == "review")
    assert names_of(review.files, root) == {"review/fail.md"}
    assert review.is_gate is True


def test_declared_but_unwritten_outputs_contribute_nothing(tmp_path: Path):
    home = single_schema_home(tmp_path)
    make_change(home, "alpha", "main")

    location = report_for(home, "alpha").locations[0]
    assert location.schemas[0].nodes == []
    assert location.schemas[0].files == []


def test_relay_attributes_each_schemas_artifacts_under_its_own_root(tmp_path: Path):
    """The core case: two schemas worked this change, each under its own subdir."""

    home = relay_home(tmp_path)
    change_dir = declare(home / "changes" / "alpha", "notes")
    write(change_dir / "plan" / "proposal.md")
    write(change_dir / "notes" / "notes.md")

    location = report_for(home, "alpha").locations[0]
    by_schema = {schema.name: schema for schema in location.schemas}

    assert names_of(by_schema["main"].files, change_dir) == {"plan/proposal.md"}
    assert names_of(by_schema["notes"].files, change_dir) == {"notes/notes.md"}
    assert by_schema["main"].artifact_root != by_schema["notes"].artifact_root
    assert by_schema["main"].declared is False
    assert by_schema["notes"].declared is True


def test_relay_reads_the_previous_stretch_out_of_the_archive(tmp_path: Path):
    """Earlier schema archived, later schema active -- both must come back."""

    home = relay_home(tmp_path)
    archived = home / "archive" / "2026-06" / "alpha"
    write(archived / "plan" / "proposal.md")
    declare(archived, "main", "2026-06-01")

    change_dir = declare(home / "changes" / "alpha", "notes")
    write(change_dir / "notes" / "notes.md")

    report = report_for(home, "alpha")
    assert [location.kind for location in report.locations] == [ARCHIVED, ACTIVE]
    assert names_of(report.locations[0].files, archived) == {"plan/proposal.md"}
    assert names_of(report.locations[1].files, change_dir) == {"notes/notes.md"}


# --------------------------------------------------------------------------- #
# which schemas get probed
# --------------------------------------------------------------------------- #


def test_without_narrowing_every_configured_candidate_is_probed(tmp_path: Path):
    home = relay_home(tmp_path)
    change_dir = declare(home / "changes" / "alpha", "main")
    write(change_dir / "plan" / "proposal.md")

    report = report_for(home, "alpha")
    assert report.schemas_seen == ["main", "notes"]
    assert report.requested_schemas is None


def test_schema_a_location_declares_is_probed_even_if_config_dropped_it(tmp_path: Path):
    """Removing a candidate from config.yaml must not make old artifacts vanish."""

    home = make_home(
        tmp_path,
        "artifacts_dir: changes\nschema: main\n",
        {"main": FULL_SCHEMA, "notes": NOTES_SCHEMA},
    )
    change_dir = declare(home / "changes" / "alpha", "notes")
    write(change_dir / "notes.md")

    report = report_for(home, "alpha")
    assert report.schemas_seen == ["main", "notes"]
    notes = next(schema for schema in report.locations[0].schemas if schema.name == "notes")
    assert names_of(notes.files, change_dir) == {"notes.md"}


def test_narrowing_reports_only_the_named_schema(tmp_path: Path):
    home = relay_home(tmp_path)
    change_dir = declare(home / "changes" / "alpha", "main")
    write(change_dir / "plan" / "proposal.md")
    write(change_dir / "notes" / "notes.md")

    report = report_for(home, "alpha", ["notes"])
    assert report.schemas_seen == ["notes"]
    assert [schema.name for schema in report.locations[0].schemas] == ["notes"]


def test_naming_a_schema_that_does_not_exist_fails_hard(tmp_path: Path):
    """"No artifacts" and "you typo'd the name" must not look the same (design D5)."""

    home = single_schema_home(tmp_path)
    make_change(home, "alpha", "main")

    with pytest.raises(SchemaNotFoundError):
        report_for(home, "alpha", ["nope"])


def test_unloadable_inferred_schema_degrades_to_a_warning(tmp_path: Path):
    home = single_schema_home(tmp_path)
    change_dir = declare(home / "changes" / "alpha", "deleted-schema")
    write(change_dir / "proposal.md")

    report = report_for(home, "alpha")
    assert report.schemas_seen == ["main"]
    assert any("deleted-schema" in warning for warning in report.warnings)
    # The change is still fully usable: main's probe still finds the artifact.
    assert names_of(report.locations[0].files, change_dir) == {"proposal.md"}


# --------------------------------------------------------------------------- #
# reserved files and rollback rounds
# --------------------------------------------------------------------------- #


def test_reserved_files_are_neither_artifacts_nor_unclaimed(tmp_path: Path):
    home = single_schema_home(tmp_path)
    root = make_change(home, "alpha", "main")
    write(root / "proposal.md")

    location = report_for(home, "alpha").locations[0]
    assert names_of(location.files, root) == {"proposal.md"}
    assert location.unclassified_files == []
    assert location.state_exists is True
    assert location.state_path.name == "state.md"
    assert location.declared_schema == "main"
    assert location.created == "2026-07-01"


def test_rollback_rounds_are_reported_one_per_round(tmp_path: Path):
    home = single_schema_home(tmp_path)
    root = make_change(home, "alpha", "main")
    round_dir = root / ".attempts" / "round-001"
    write(round_dir / "proposal.md")
    write(
        round_dir / "_meta.yaml",
        yaml.safe_dump({"round": 1, "gate": "review", "verdict": "FAIL"}),
    )

    location = report_for(home, "alpha").locations[0]
    assert len(location.attempts) == 1
    attempt = location.attempts[0]
    assert (attempt.round, attempt.gate, attempt.verdict) == (1, "review", "FAIL")
    assert names_of(attempt.files, root) == {".attempts/round-001/proposal.md"}


def test_round_without_metadata_is_still_reported_so_its_files_survive(tmp_path: Path):
    """`attempts.list_rounds` skips these; dropping them here would drop files."""

    home = single_schema_home(tmp_path)
    root = make_change(home, "alpha", "main")
    write(root / ".attempts" / "round-002" / "design.md")

    location = report_for(home, "alpha").locations[0]
    assert [(item.round, item.gate) for item in location.attempts] == [(2, None)]
    assert names_of(location.attempts[0].files, root) == {".attempts/round-002/design.md"}


def test_round_metadata_is_not_reported_as_an_artifact(tmp_path: Path):
    home = single_schema_home(tmp_path)
    root = make_change(home, "alpha", "main")
    write(root / ".attempts" / "round-001" / "_meta.yaml", yaml.safe_dump({"round": 1}))
    write(root / ".attempts" / "round-001" / "tasks.md")

    location = report_for(home, "alpha").locations[0]
    assert names_of(location.attempts[0].files, root) == {".attempts/round-001/tasks.md"}


def test_stray_files_under_attempts_are_still_reported(tmp_path: Path):
    home = single_schema_home(tmp_path)
    root = make_change(home, "alpha", "main")
    write(root / ".attempts" / "leftover.md")

    location = report_for(home, "alpha").locations[0]
    assert [item.round for item in location.attempts] == [None]
    assert names_of(location.attempts[0].files, root) == {".attempts/leftover.md"}


# --------------------------------------------------------------------------- #
# unclaimed files and ambiguity
# --------------------------------------------------------------------------- #


def test_file_matching_no_pattern_is_reported_as_unclaimed(tmp_path: Path):
    home = single_schema_home(tmp_path)
    root = make_change(home, "alpha", "main")
    write(root / "proposal.md")
    write(root / "scratch.txt")

    location = report_for(home, "alpha").locations[0]
    assert names_of(location.unclassified_files, root) == {"scratch.txt"}
    assert names_of(location.files, root) == {"proposal.md", "scratch.txt"}


def test_narrowing_moves_the_excluded_schemas_artifacts_into_unclaimed(tmp_path: Path):
    """Filtering must not make files disappear from the listing."""

    home = relay_home(tmp_path)
    change_dir = declare(home / "changes" / "alpha", "main")
    write(change_dir / "plan" / "proposal.md")
    write(change_dir / "notes" / "notes.md")

    location = report_for(home, "alpha", ["notes"]).locations[0]
    assert names_of(location.unclassified_files, change_dir) == {"plan/proposal.md"}
    assert names_of(location.files, change_dir) == {"plan/proposal.md", "notes/notes.md"}


def test_hidden_files_are_not_filtered_out_of_unclaimed(tmp_path: Path):
    """Design D6: visible noise beats silently dropping files."""

    home = single_schema_home(tmp_path)
    root = make_change(home, "alpha", "main")
    write(root / ".DS_Store")

    location = report_for(home, "alpha").locations[0]
    assert names_of(location.unclassified_files, root) == {".DS_Store"}


def test_file_claimed_by_two_schemas_is_reported_twice_and_warned_about(tmp_path: Path):
    home = make_home(
        tmp_path,
        """
artifacts_dir: changes
schemas:
  - name: main
  - name: twin
""",
        {"main": FULL_SCHEMA, "twin": FULL_SCHEMA},
    )
    change_dir = home / "changes" / "alpha"
    change_dir.mkdir(parents=True)
    write(change_dir / "proposal.md")

    report = report_for(home, "alpha")
    location = report.locations[0]
    claimed = [names_of(schema.files, change_dir) for schema in location.schemas]
    assert claimed == [{"proposal.md"}, {"proposal.md"}]
    assert any("claimed by more than one schema" in warning for warning in report.warnings)
    # The summary de-duplicates: the file exists once.
    assert names_of(location.files, change_dir) == {"proposal.md"}
    assert len(location.files) == 1


# --------------------------------------------------------------------------- #
# degradation: no metadata may crash a query
# --------------------------------------------------------------------------- #


def test_location_without_metadata_still_reports_its_artifacts(tmp_path: Path):
    home = single_schema_home(tmp_path)
    archived = home / "archive" / "2026-07" / "alpha"
    write(archived / "proposal.md")

    location = report_for(home, "alpha").locations[0]
    assert location.declared_schema is None
    assert names_of(location.files, archived) == {"proposal.md"}


def test_invalid_change_metadata_degrades_to_a_warning(tmp_path: Path):
    home = single_schema_home(tmp_path)
    change_dir = home / "changes" / "alpha"
    change_dir.mkdir(parents=True)
    write(change_dir / ".workflow.yaml", "schema: main\nunexpected: field\n")
    write(change_dir / "proposal.md")

    report = report_for(home, "alpha")
    assert report.locations[0].declared_schema is None
    assert any(".workflow.yaml" in warning for warning in report.warnings)
    assert names_of(report.locations[0].files, change_dir) == {"proposal.md"}


@pytest.mark.parametrize(
    "body",
    [
        "- a\n- b\n",  # valid YAML, top level is a list -- the AttributeError case
        "just a string\n",
        "{unclosed\n",  # not valid YAML at all
    ],
)
def test_broken_round_metadata_degrades_instead_of_crashing(tmp_path: Path, body: str):
    """The gate caught this: `list_rounds` would raise past the error contract."""

    home = single_schema_home(tmp_path)
    root = make_change(home, "alpha", "main")
    write(root / ".attempts" / "round-001" / "_meta.yaml", body)
    write(root / ".attempts" / "round-001" / "design.md")

    report = report_for(home, "alpha")
    attempt = report.locations[0].attempts[0]
    assert (attempt.round, attempt.gate, attempt.verdict) == (1, None, None)
    assert names_of(attempt.files, root) == {".attempts/round-001/design.md"}
    assert any("_meta.yaml" in warning for warning in report.warnings)


# --------------------------------------------------------------------------- #
# every reported path stays inside the workflow home (design D11)
# --------------------------------------------------------------------------- #


def outside_file(tmp_path: Path) -> Path:
    return write(tmp_path / "outside" / "secret.md")


def test_declared_output_that_is_a_link_out_of_the_home_is_skipped(tmp_path: Path):
    home = single_schema_home(tmp_path)
    root = make_change(home, "alpha", "main")
    (root / "proposal.md").symlink_to(outside_file(tmp_path))

    report = report_for(home, "alpha")
    assert report.files == []
    assert any("outside the workflow home" in warning for warning in report.warnings)


def test_unclaimed_link_out_of_the_home_is_skipped(tmp_path: Path):
    home = single_schema_home(tmp_path)
    root = make_change(home, "alpha", "main")
    (root / "scratch.md").symlink_to(outside_file(tmp_path))

    report = report_for(home, "alpha")
    assert report.locations[0].unclassified_files == []
    assert any("outside the workflow home" in warning for warning in report.warnings)


def test_a_link_out_of_the_home_does_not_hide_its_neighbours(tmp_path: Path):
    home = single_schema_home(tmp_path)
    root = make_change(home, "alpha", "main")
    write(root / "specs" / "cap" / "spec.md")
    (root / "scratch.md").symlink_to(outside_file(tmp_path))

    report = report_for(home, "alpha")
    assert names_of(report.files, root) == {"specs/cap/spec.md"}


def test_warnings_never_disclose_a_path_outside_the_home(tmp_path: Path):
    """Naming the resolved target would leak the path the check exists to block."""

    home = single_schema_home(tmp_path)
    root = make_change(home, "alpha", "main")
    secret = outside_file(tmp_path)
    (root / "proposal.md").symlink_to(secret)
    (root / "scratch.md").symlink_to(secret)

    report = report_for(home, "alpha")
    assert report.warnings
    for warning in report.warnings:
        assert "secret.md" not in warning
        assert str(secret.parent) not in warning


def test_archive_month_linked_out_of_the_home_is_not_reported(tmp_path: Path):
    home = single_schema_home(tmp_path)
    make_change(home, "alpha", "main")
    write(root_of := tmp_path / "elsewhere" / "alpha" / "proposal.md")
    (home / "archive").mkdir()
    (home / "archive" / "2026-07").symlink_to(root_of.parent.parent, target_is_directory=True)

    report = report_for(home, "alpha")
    assert [location.kind for location in report.locations] == [ACTIVE]


def test_symlinked_directory_cycle_terminates(tmp_path: Path):
    """Pins the stdlib guarantee that `rglob` does not descend into linked dirs."""

    home = single_schema_home(tmp_path)
    root = make_change(home, "alpha", "main")
    write(root / "proposal.md")
    (root / "loop").symlink_to(root, target_is_directory=True)

    report = report_for(home, "alpha")
    assert names_of(report.files, root) == {"proposal.md"}


# --------------------------------------------------------------------------- #
# read-only
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("archived", [False, True])
def test_discovery_never_touches_the_disk(tmp_path: Path, archived: bool):
    """Design D3: reusing `_load_change_context` would mkdir inside the archive."""

    home = make_home(
        tmp_path,
        "artifacts_dir: changes\nschema: main\nschemas:\n  - name: main\n    path: plan\n",
    )
    if archived:
        target = home / "archive" / "2026-07" / "alpha"
        write(target / "plan" / "proposal.md")
    else:
        make_change(home, "alpha", "main", subdir="plan")
        write(home / "changes" / "alpha" / "plan" / "proposal.md")

    before = snapshot(home)
    report_for(home, "alpha")
    assert snapshot(home) == before


def test_probing_a_schema_whose_subdir_is_absent_creates_nothing(tmp_path: Path):
    home = relay_home(tmp_path)
    change_dir = home / "changes" / "alpha"
    write(change_dir / "plan" / "proposal.md")

    before = snapshot(home)
    report = report_for(home, "alpha")
    assert snapshot(home) == before
    notes = next(schema for schema in report.locations[0].schemas if schema.name == "notes")
    assert notes.files == []


# --------------------------------------------------------------------------- #
# module constants
# --------------------------------------------------------------------------- #


def test_round_metadata_filename_matches_what_rollback_writes():
    """Both sides name the same file; a rename here must not go unnoticed."""

    from loopspec import rollback as rollback_mod

    source = Path(rollback_mod.__file__).read_text(encoding="utf-8")
    assert f'"{artifacts_mod.ROUND_META_FILENAME}"' in source
