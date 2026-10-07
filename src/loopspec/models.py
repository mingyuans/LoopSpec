"""Shared pydantic models: gate output pairs and the workspace config."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

KEBAB_RE = r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$"


class GateOutputs(BaseModel):
    model_config = {"extra": "forbid", "populate_by_name": True}

    pass_: str = Field(min_length=1, alias="pass")
    fail: str = Field(min_length=1)


class GateTemplates(BaseModel):
    model_config = {"extra": "forbid", "populate_by_name": True}

    pass_: str = Field(min_length=1, alias="pass")
    fail: str = Field(min_length=1)


class WorkflowConfig(BaseModel):
    """`config.yaml`: where changes live and the project's minimum workflow constraints."""

    model_config = {"extra": "forbid", "populate_by_name": True}

    artifacts_dir: str = "changes"
    workflow: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_workflow(self) -> WorkflowConfig:
        if self.workflow is not None:
            from .workflow_models import ProjectWorkflow

            self.workflow = ProjectWorkflow.model_validate(self.workflow).model_dump()
        return self
