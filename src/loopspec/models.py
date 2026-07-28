"""Pydantic models for workflow schema and project config."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

KEBAB_RE = r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$"


class OnExhausted(StrEnum):
    ESCALATE = "escalate"
    STOP = "stop"


class OnFailSpec(BaseModel):
    model_config = {"extra": "forbid"}

    reset: list[str] = Field(min_length=1)
    max_retries: int = Field(default=3, ge=0)
    on_exhausted: OnExhausted = OnExhausted.ESCALATE


class GateOutputs(BaseModel):
    model_config = {"extra": "forbid", "populate_by_name": True}

    pass_: str = Field(min_length=1, alias="pass")
    fail: str = Field(min_length=1)


class GateTemplates(BaseModel):
    model_config = {"extra": "forbid", "populate_by_name": True}

    pass_: str = Field(min_length=1, alias="pass")
    fail: str = Field(min_length=1)


class GateSpec(BaseModel):
    model_config = {"extra": "forbid"}

    outputs: GateOutputs
    templates: GateTemplates
    on_fail: OnFailSpec


class InstructionRef(BaseModel):
    model_config = {"extra": "forbid"}

    file: str = Field(min_length=1)


class NodeSpec(BaseModel):
    model_config = {"extra": "forbid"}

    id: str = Field(pattern=KEBAB_RE)
    generates: str | None = None
    description: str
    template: str | None = None
    requires: list[str] = Field(default_factory=list)
    instruction: str | InstructionRef | None = None
    gate: GateSpec | None = None


class WorkflowSchema(BaseModel):
    model_config = {"extra": "forbid"}

    name: str = Field(pattern=KEBAB_RE)
    version: int = Field(gt=0)
    description: str | None = None
    nodes: list[NodeSpec] = Field(min_length=1)


class ConfigSchemaRef(BaseModel):
    model_config = {"extra": "forbid"}

    name: str = Field(pattern=KEBAB_RE)
    path: str | None = None
    description: str | None = None
    when: str | None = None


class SchemaSelectionSpec(BaseModel):
    model_config = {"extra": "forbid"}

    instruction: str = Field(min_length=1)


class WorkflowConfig(BaseModel):
    model_config = {"extra": "forbid", "populate_by_name": True}

    artifacts_dir: str = "changes"
    schema_name: str | None = Field(default=None, pattern=KEBAB_RE, alias="schema")
    schemas: list[ConfigSchemaRef] = Field(default_factory=list)
    schema_selection: SchemaSelectionSpec | None = None
    context: str | None = None
    rules: dict[str, list[str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_schema_config(self) -> WorkflowConfig:
        if self.schema_name is None and not self.schemas:
            raise ValueError("config.yaml must define schema or schemas")
        names = [item.name for item in self.schemas]
        if len(names) != len(set(names)):
            raise ValueError("schemas[*].name must be unique")
        if self.schema_name is not None and names and self.schema_name not in names:
            raise ValueError(
                "schema must be included in schemas[*].name when both are configured"
            )
        return self


class WorkflowMetadata(BaseModel):
    """Per-change `.workflow.yaml` contents."""

    model_config = {"extra": "forbid", "populate_by_name": True}

    schema_name: str = Field(alias="schema")
    created: str
