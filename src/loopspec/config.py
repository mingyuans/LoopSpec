"""config.yaml and .workflow.yaml loading."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from .errors import ConfigValidationError, SchemaSelectionRequiredError
from .models import ConfigSchemaRef, WorkflowConfig, WorkflowMetadata
from .paths import is_safe_relative_path, schema_dir

CONFIG_FILENAME = "config.yaml"
METADATA_FILENAME = ".workflow.yaml"


def load_config(workflow_home: Path) -> WorkflowConfig:
    config_path = workflow_home / CONFIG_FILENAME
    if not config_path.is_file():
        raise ConfigValidationError(f"config.yaml not found in {workflow_home}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    try:
        config = WorkflowConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigValidationError(str(exc)) from exc

    if not is_safe_relative_path(config.artifacts_dir):
        raise ConfigValidationError(
            f"artifacts_dir must be a safe relative path: {config.artifacts_dir}"
        )

    for ref in config.schemas:
        if ref.path is not None and not is_safe_relative_path(ref.path):
            raise ConfigValidationError(
                f"schemas[*].path must be a safe relative path: {ref.path}"
            )
        candidate_dir = schema_dir(workflow_home, ref.name)
        if not (candidate_dir / "schema.yaml").is_file():
            raise ConfigValidationError(
                f"Candidate schema '{ref.name}' cannot be loaded: {candidate_dir} not found"
            )

    return config


def write_metadata(change_dir: Path, schema_name: str, created: str) -> Path:
    path = change_dir / METADATA_FILENAME
    metadata = WorkflowMetadata(schema=schema_name, created=created)
    path.write_text(
        yaml.safe_dump(metadata.model_dump(by_alias=True), sort_keys=False), encoding="utf-8"
    )
    return path


def read_metadata(change_dir: Path) -> WorkflowMetadata | None:
    path = change_dir / METADATA_FILENAME
    if not path.is_file():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    try:
        return WorkflowMetadata.model_validate(raw)
    except ValidationError as exc:
        raise ConfigValidationError(str(exc)) from exc


def resolve_schema_for_new_change(config: WorkflowConfig, explicit_schema: str | None) -> str:
    """Resolve which schema `loopspec new` should use, or raise SchemaSelectionRequiredError."""

    if explicit_schema is not None:
        if config.schemas and explicit_schema not in {ref.name for ref in config.schemas}:
            raise ConfigValidationError(
                f"--schema '{explicit_schema}' is not among the configured candidates"
            )
        return explicit_schema

    if len(config.schemas) > 1:
        raise SchemaSelectionRequiredError(
            "config.yaml defines multiple candidate schemas; one must be chosen "
            "before creating this change.",
            fix="Pick a schemas[*].name and re-run with --schema <name>.",
        )

    if len(config.schemas) == 1:
        return config.schemas[0].name

    if config.schema_name is not None:
        return config.schema_name

    raise ConfigValidationError("config.yaml must define schema or schemas")


def resolve_schema_for_existing_change(
    config: WorkflowConfig, metadata: WorkflowMetadata | None, explicit_schema: str | None
) -> str:
    """Command-line --schema > .workflow.yaml > config.yaml default > error."""

    if explicit_schema is not None:
        return explicit_schema
    if metadata is not None:
        return metadata.schema_name
    if config.schema_name is not None:
        return config.schema_name
    raise ConfigValidationError(
        "Unable to determine which schema to use: no --schema, .workflow.yaml, "
        "or config.yaml default schema found."
    )


def schema_path_for(config: WorkflowConfig, schema_name: str) -> str | None:
    for ref in config.schemas:
        if ref.name == schema_name:
            return ref.path
    return None


def rules_for(config: WorkflowConfig) -> dict[str, list[str]]:
    return config.rules


def schema_candidates(config: WorkflowConfig) -> list[ConfigSchemaRef]:
    return list(config.schemas)
