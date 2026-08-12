"""Cross-schema, cross-location artifact discovery for one change.

`status` and `instructions` both answer "where are this change's artifacts?" for
exactly one schema in exactly one directory -- the schema recorded in
`.workflow.yaml`, under the change directory that still exists. That is the wrong
shape for two real situations:

* **Schema relay.** Several schemas work a change in turn. `.workflow.yaml` holds
  one `schema` field, so migrating overwrites the previous schema's name, and
  each schema's artifacts may sit under a different `schemas[*].path` root that
  the current schema's patterns cannot match.
* **Archiving.** `loopspec archive` *moves* the whole directory to
  `<home>/archive/<YYYY-MM>/<change>/`. Once a stretch of work is archived, the
  next stretch cannot see it at all -- and "finish, archive, carry on" is the
  most common form the relay takes.

So discovery here spans three axes: location (active plus every archive month),
schema (probed, never assumed -- design D1), and rollback round.

Two invariants this module owes its callers, both learned from the security gate:

1. **Every reported path is inside the workflow home.** Resolution follows
   symlinks, so a link inside a change directory resolves outside the home. All
   paths funnel through `paths.contained_in` before they can reach a result
   (design D11); a path that escapes is dropped and named in a warning by its
   *relative* name, never by where it pointed.
2. **No metadata can crash a query.** This module exists to read old, possibly
   archived data. Every metadata read degrades to a warning -- missing, invalid
   YAML, or a top level that is not a mapping (design D9).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import config as config_mod
from . import paths as paths_mod
from .errors import ChangeNotFoundError, ConfigValidationError, LoopspecError
from .models import KEBAB_RE, WorkflowConfig
from .outputs import iter_artifact_candidates, node_output_patterns, resolve_output_entries
from .schema_loader import LoadedSchema, load_schema

ACTIVE = "active"
ARCHIVED = "archived"

#: Per-round metadata, the `.attempts` counterpart of `.workflow.yaml`. Not an
#: artifact, so it is excluded from the files a round reports.
ROUND_META_FILENAME = "_meta.yaml"

_ROUND_DIR_RE = re.compile(r"^round-(\d+)$")
_KEBAB = re.compile(KEBAB_RE)


@dataclass
class NodeArtifacts:
    id: str
    is_gate: bool
    output_patterns: list[str]
    files: list[Path]


@dataclass
class SchemaArtifacts:
    name: str
    #: Whether this location's `.workflow.yaml` names this schema. A schema can
    #: hold artifacts in a location that never declared it -- that is the relay.
    declared: bool
    schema_path: str | None
    artifact_root: Path
    nodes: list[NodeArtifacts]
    files: list[Path]


@dataclass
class AttemptRound:
    #: `None` when the directory name is not `round-<digits>`, which still gets
    #: reported: dropping it would drop the files inside it.
    round: int | None
    gate: str | None
    verdict: str | None
    archive_dir: Path
    files: list[Path]


@dataclass
class ChangeLocation:
    kind: str
    archive_month: str | None
    change_root: Path
    declared_schema: str | None
    created: str | None
    state_path: Path
    state_exists: bool
    schemas: list[SchemaArtifacts] = field(default_factory=list)
    attempts: list[AttemptRound] = field(default_factory=list)
    unclassified_files: list[Path] = field(default_factory=list)
    files: list[Path] = field(default_factory=list)


@dataclass
class ArtifactReport:
    change_name: str
    artifacts_dir: str
    #: `None` means "not narrowed", which is not the same as an empty list.
    requested_schemas: list[str] | None
    schemas_seen: list[str]
    locations: list[ChangeLocation]
    files: list[Path]
    warnings: list[str]


# --------------------------------------------------------------------------- #
# --schemas parsing
# --------------------------------------------------------------------------- #


def resolve_requested_schemas(raw: str | None) -> list[str] | None:
    """Parse `--schemas` into a de-duplicated, order-preserving list, or `None`.

    `None` (the option was omitted) means "every known schema". A value that
    strips down to nothing is an error rather than the same thing: passing the
    option says the caller had an intent, and silently widening to "everything"
    would hide a broken variable upstream.

    Each name is checked against `KEBAB_RE` -- the same rule `config.yaml` puts
    on `schemas[*].name`. It doubles as path-component validation, since the name
    is joined onto `<home>/schemas/`: it rejects `../../etc` and absolute paths,
    and also `a/b`, which would stay inside the home but sidestep the naming
    convention the candidates answer to (design D8).
    """

    if raw is None:
        return None

    requested = [part.strip() for part in raw.split(",")]
    requested = [part for part in requested if part]
    if not requested:
        raise ConfigValidationError(
            "--schemas was given no schema names.",
            fix="Pass a comma-separated list of schema names, or omit --schemas "
            "to report every known schema.",
        )

    invalid = [name for name in requested if not _KEBAB.match(name)]
    if invalid:
        raise ConfigValidationError(
            f"--schemas contains invalid schema name(s): {', '.join(invalid)}",
            fix="Schema names must be kebab-case, matching the schemas[*].name rule.",
        )

    unique: list[str] = []
    for name in requested:
        if name not in unique:
            unique.append(name)
    return unique


# --------------------------------------------------------------------------- #
# locations
# --------------------------------------------------------------------------- #


def discover_locations(
    workflow_home: Path, artifacts_dir: str, change_name: str
) -> list[tuple[str, str | None, Path]]:
    """`(kind, month, directory)` for every place this change's artifacts live.

    Ordered oldest-first -- archive months ascending, then the active directory.
    The order is part of the contract: a relay reads the earlier stretches before
    the current one, so consumers can walk the list as-is (design D2).
    """

    found: list[tuple[str, str | None, Path]] = [
        (ARCHIVED, month, directory)
        for month, directory in paths_mod.archive_locations(workflow_home, change_name)
    ]

    active = paths_mod.artifacts_root(workflow_home, artifacts_dir) / change_name
    if active.is_dir() and paths_mod.contained_in(workflow_home, active):
        found.append((ACTIVE, None, active))

    if not found:
        raise ChangeNotFoundError(
            f"Change not found in any location: {change_name}",
            fix="Check the name, or check --home. Both the active directory and "
            "every archive month were searched.",
        )
    return found


# --------------------------------------------------------------------------- #
# metadata, degraded safely
# --------------------------------------------------------------------------- #


def _read_metadata(
    change_dir: Path, label: str, warnings: list[str]
) -> tuple[str | None, str | None]:
    """`(schema, created)` from `.workflow.yaml`, or `(None, None)` with a warning."""

    try:
        metadata = config_mod.read_metadata(change_dir)
    except LoopspecError as exc:
        warnings.append(f"{label}: .workflow.yaml is unreadable and was ignored ({exc.message})")
        return None, None
    except yaml.YAMLError:
        warnings.append(f"{label}: .workflow.yaml is not valid YAML and was ignored")
        return None, None
    if metadata is None:
        return None, None
    return metadata.schema_name, metadata.created


def _read_round_meta(round_dir: Path, label: str, warnings: list[str]) -> dict[str, object]:
    """A round's `_meta.yaml` as a mapping, or `{}` with a warning.

    `attempts.list_rounds` is deliberately not reused here (design D12): it skips
    rounds that have no `_meta.yaml` -- which for this command means dropping the
    files inside them -- and it calls `.get()` straight on whatever YAML returns,
    so a top level that is not a mapping raises `AttributeError` rather than the
    CLI's error contract.
    """

    meta_path = round_dir / ROUND_META_FILENAME
    if not meta_path.is_file():
        return {}
    try:
        raw = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError):
        warnings.append(f"{label}: {ROUND_META_FILENAME} is not valid YAML and was ignored")
        return {}
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        warnings.append(
            f"{label}: {ROUND_META_FILENAME} does not contain a mapping and was ignored"
        )
        return {}
    return raw


# --------------------------------------------------------------------------- #
# schema selection
# --------------------------------------------------------------------------- #


def _candidate_names(config: WorkflowConfig) -> list[str]:
    names = [ref.name for ref in config.schemas]
    if config.schema_name is not None and config.schema_name not in names:
        names.append(config.schema_name)
    return names


def _load_schemas(
    workflow_home: Path,
    names: list[str],
    *,
    explicit: bool,
    warnings: list[str],
) -> dict[str, LoadedSchema]:
    """Load each named schema.

    Explicitly requested names fail hard: naming something that does not exist is
    the caller's mistake, and an empty result would make "this schema produced
    nothing" indistinguishable from "you typo'd the name". Names that were merely
    inferred degrade to a warning -- dropping a candidate from `config.yaml` is
    ordinary maintenance and must not make old artifacts vanish (design D5).
    """

    loaded: dict[str, LoadedSchema] = {}
    for name in names:
        try:
            loaded[name] = load_schema(paths_mod.schema_dir(workflow_home, name))
        except LoopspecError as exc:
            if explicit:
                raise
            warnings.append(f"schema '{name}' could not be loaded and was skipped ({exc.message})")
    return loaded


# --------------------------------------------------------------------------- #
# per-location artifact collection
# --------------------------------------------------------------------------- #


def _keep_contained(
    workflow_home: Path,
    entries: list[tuple[str, Path]],
    label: str,
    warnings: list[str],
) -> list[Path]:
    """Drop paths that resolve outside the workflow home, naming what was dropped.

    The single choke point every reported path passes through (design D11). The
    warning names the file by its relative name only: printing the resolved
    target would leak the very path the check exists to keep out.
    """

    kept: list[Path] = []
    escaped: list[str] = []
    for relative, resolved in entries:
        if paths_mod.contained_in(workflow_home, resolved):
            kept.append(resolved)
        else:
            escaped.append(relative)
    if escaped:
        warnings.append(
            f"{label}: {len(escaped)} path(s) resolve outside the workflow home and were "
            f"skipped ({', '.join(sorted(escaped))})"
        )
    return kept


def _collect_schema(
    workflow_home: Path,
    config: WorkflowConfig,
    change_dir: Path,
    name: str,
    loaded: LoadedSchema,
    *,
    declared: bool,
    label: str,
    warnings: list[str],
) -> SchemaArtifacts:
    schema_path = config_mod.schema_workspace_path_for(config, name)
    artifact_root = paths_mod.artifact_root(change_dir, schema_path)

    # Before schema workspaces were introduced, a multi-schema change could
    # have its declared schema's outputs directly at the change root.  Probe
    # that old location only for the declared schema, avoiding false claims by
    # every candidate whose node patterns happen to overlap.
    if schema_path is not None and config_mod.schema_path_for(config, name) is None:
        automatic_roots_exist = any(
            (
                change_dir
                / (config_mod.schema_workspace_path_for(config, candidate) or "")
            ).is_dir()
            for candidate in _candidate_names(config)
        )
        if not automatic_roots_exist or (not artifact_root.is_dir() and declared):
            artifact_root = change_dir

    nodes: list[NodeArtifacts] = []
    files: list[Path] = []
    if artifact_root.is_dir():
        for node_id in loaded.graph.build_order():
            node = loaded.node(node_id)
            patterns = node_output_patterns(node)
            entries: list[tuple[str, Path]] = []
            for pattern in patterns:
                entries.extend(resolve_output_entries(artifact_root, pattern))
            node_files = _keep_contained(
                workflow_home, entries, f"{label} schema '{name}' node '{node_id}'", warnings
            )
            if node_files:
                nodes.append(
                    NodeArtifacts(
                        id=node_id,
                        is_gate=node.gate is not None,
                        output_patterns=patterns,
                        files=_unique(node_files),
                    )
                )
                files.extend(node_files)

    return SchemaArtifacts(
        name=name,
        declared=declared,
        schema_path=schema_path,
        artifact_root=artifact_root,
        nodes=nodes,
        files=_unique(files),
    )


def _collect_attempts(
    workflow_home: Path, change_dir: Path, label: str, warnings: list[str]
) -> list[AttemptRound]:
    """Every rollback round in this location, plus anything else under `.attempts`.

    Grouped by first path component so nothing under `.attempts` can go
    unreported: files sitting directly in it, or in a directory that is not named
    `round-<digits>`, still come back (with `round` left unset) rather than
    silently dropping out of the listing.
    """

    attempts_dir = change_dir / ".attempts"
    if not attempts_dir.is_dir():
        return []

    grouped: dict[str, list[tuple[str, Path]]] = {}
    for relative, resolved in iter_artifact_candidates(attempts_dir):
        parts = Path(relative).parts
        group = parts[0] if len(parts) > 1 else ""
        if len(parts) > 1 and parts[-1] == ROUND_META_FILENAME:
            continue
        grouped.setdefault(group, []).append((relative, resolved))

    rounds: list[AttemptRound] = []
    for group in sorted(grouped):
        round_dir = attempts_dir / group if group else attempts_dir
        match = _ROUND_DIR_RE.match(group)
        number = int(match.group(1)) if match else None
        meta = _read_round_meta(round_dir, f"{label} {group or '.attempts'}", warnings)
        gate = meta.get("gate")
        verdict = meta.get("verdict")
        rounds.append(
            AttemptRound(
                round=number,
                gate=gate if isinstance(gate, str) else None,
                verdict=verdict if isinstance(verdict, str) else None,
                archive_dir=round_dir,
                files=_keep_contained(
                    workflow_home,
                    grouped[group],
                    f"{label} {group or '.attempts'}",
                    warnings,
                ),
            )
        )

    rounds.sort(key=lambda item: (item.round is None, item.round or 0, str(item.archive_dir)))
    return rounds


def _unique(paths: list[Path]) -> list[Path]:
    """De-duplicate while sorting, so repeat calls on the same disk state match."""

    return sorted(set(paths), key=str)


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #


def discover_artifacts(
    workflow_home: Path,
    config: WorkflowConfig,
    change_name: str,
    requested_schemas: list[str] | None,
) -> ArtifactReport:
    """Every artifact path this change name owns, across locations and schemas."""

    paths_mod.safe_change_name(change_name)
    schema_hints: list[str | None] = list(
        requested_schemas or _candidate_names(config)
    ) or [None]
    resolved_names = {
        paths_mod.reusable_change_name(
            workflow_home, config.artifacts_dir, change_name, schema_hint
        )
        for schema_hint in schema_hints
    }
    reused_names = resolved_names - {change_name}
    if len(reused_names) == 1:
        change_name = reused_names.pop()
    warnings: list[str] = []

    raw_locations = discover_locations(workflow_home, config.artifacts_dir, change_name)

    # Metadata first, for the whole set: an inferred schema set has to include
    # what *any* location declares before probing starts, since a relay's earlier
    # schema may hold artifacts in the later location too (design D5).
    declared: dict[Path, tuple[str | None, str | None]] = {}
    for kind, month, directory in raw_locations:
        label = _label(kind, month)
        declared[directory] = _read_metadata(directory, label, warnings)

    if requested_schemas is not None:
        names = list(requested_schemas)
    else:
        names = _candidate_names(config)
        for schema_name, _created in declared.values():
            if schema_name is not None and schema_name not in names:
                names.append(schema_name)

    loaded = _load_schemas(
        workflow_home, names, explicit=requested_schemas is not None, warnings=warnings
    )

    locations: list[ChangeLocation] = []
    all_files: list[Path] = []
    for kind, month, directory in raw_locations:
        label = _label(kind, month)
        declared_schema, created = declared[directory]
        state_root = directory
        if declared_schema is not None:
            declared_path = config_mod.schema_workspace_path_for(config, declared_schema)
            candidate_state_root = paths_mod.artifact_root(directory, declared_path)
            if (candidate_state_root / config_mod.METADATA_FILENAME).is_file():
                state_root = candidate_state_root
        state_path = state_root / "state.md"

        location = ChangeLocation(
            kind=kind,
            archive_month=month,
            change_root=directory.resolve(),
            declared_schema=declared_schema,
            created=created,
            state_path=state_path.resolve(),
            state_exists=state_path.is_file(),
        )

        claimed_by: dict[Path, list[str]] = {}
        for name in sorted(loaded):
            schema_artifacts = _collect_schema(
                workflow_home,
                config,
                directory,
                name,
                loaded[name],
                declared=name == declared_schema,
                label=label,
                warnings=warnings,
            )
            location.schemas.append(schema_artifacts)
            for path in schema_artifacts.files:
                claimed_by.setdefault(path, []).append(name)

        for path, owners in sorted(claimed_by.items(), key=lambda item: str(item[0])):
            if len(owners) > 1:
                warnings.append(
                    f"{label}: '{_relative_to(directory, path)}' is claimed by more than one "
                    f"schema ({', '.join(owners)})"
                )

        attempt_roots = [directory]
        for schema_artifacts in location.schemas:
            root = schema_artifacts.artifact_root
            if root != directory and root.is_dir() and root not in attempt_roots:
                attempt_roots.append(root)
        location.attempts = [
            round_
            for attempt_root in attempt_roots
            for round_ in _collect_attempts(workflow_home, attempt_root, label, warnings)
        ]

        candidates = _keep_contained(
            workflow_home, iter_artifact_candidates(directory), label, warnings
        )
        location.unclassified_files = _unique(
            [path for path in candidates if path not in claimed_by]
        )

        location.files = _unique(
            list(claimed_by)
            + location.unclassified_files
            + [path for round_ in location.attempts for path in round_.files]
        )
        all_files.extend(location.files)
        locations.append(location)

    return ArtifactReport(
        change_name=change_name,
        artifacts_dir=config.artifacts_dir,
        requested_schemas=list(requested_schemas) if requested_schemas is not None else None,
        schemas_seen=sorted(loaded),
        locations=locations,
        files=_unique(all_files),
        warnings=warnings,
    )


def _label(kind: str, month: str | None) -> str:
    return f"{kind} {month}" if month else kind


def _relative_to(change_dir: Path, path: Path) -> str:
    """A path's name relative to its change directory, for warning text."""

    try:
        return path.relative_to(change_dir.resolve()).as_posix()
    except ValueError:
        return path.name
