"""Shared pydantic models: gate output pairs and the workspace config."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

KEBAB_RE = r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$"
TAG_RE = r"^[A-Za-z0-9._+-]{1,200}$"

# Registry URLs end up as git arguments, so only four shapes with a conservative
# character set are accepted; transports such as `ext::`/`fd::`, plaintext
# `http://`/`git://` and credentials embedded in the URL never get that far.
_HOST = r"[A-Za-z0-9][A-Za-z0-9.-]*"
_USER = r"[A-Za-z0-9._][A-Za-z0-9._-]*"
_PATH = r"[A-Za-z0-9._~%/+-]*"
_REGISTRY_URLS = {
    "https": re.compile(rf"^https://{_HOST}(:[0-9]{{1,5}})?(/{_PATH})?$"),
    "ssh": re.compile(rf"^ssh://({_USER}@)?{_HOST}(:[0-9]{{1,5}})?/{_PATH}$"),
    "scp": re.compile(rf"^{_USER}@{_HOST}:(?![-/]){_PATH}$"),
    "file": re.compile(rf"^file:///{_PATH}$"),
}


def registry_scheme(url: str) -> str:
    """The git protocol a valid registry URL uses: `https`, `ssh` or `file`."""
    if len(url) > 2048 or url.startswith("-") or "::" in url:
        raise ValueError("registry.url 不合法")
    for shape, pattern in _REGISTRY_URLS.items():
        if pattern.fullmatch(url):
            return "ssh" if shape == "scp" else shape
    raise ValueError("registry.url 不合法")


def check_tag(value: str) -> str:
    if (
        not re.fullmatch(TAG_RE, value)
        or value[0] in "-."
        or value.endswith(".lock")
        or ".." in value
    ):
        raise ValueError("tag 名不合法")
    return value


class GateOutputs(BaseModel):
    model_config = {"extra": "forbid", "populate_by_name": True}

    pass_: str = Field(min_length=1, alias="pass")
    fail: str = Field(min_length=1)


class GateTemplates(BaseModel):
    model_config = {"extra": "forbid", "populate_by_name": True}

    pass_: str = Field(min_length=1, alias="pass")
    fail: str = Field(min_length=1)


class RegistrySpec(BaseModel):
    """`config.yaml` `registry`: the one git repository fragments/profiles sync from."""

    model_config = {"extra": "forbid", "strict": True}

    url: str
    version: str = "latest"
    path: str | None = None

    @field_validator("url")
    @classmethod
    def valid_url(cls, value: str) -> str:
        registry_scheme(value)
        return value

    @field_validator("version")
    @classmethod
    def valid_version(cls, value: str) -> str:
        return value if value == "latest" else check_tag(value)

    @field_validator("path")
    @classmethod
    def valid_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        from .errors import WorkflowError
        from .workflow_io import relative_path

        try:
            return relative_path(value)
        except WorkflowError as exc:
            raise ValueError("registry.path 必须是安全相对路径") from exc


class WorkflowConfig(BaseModel):
    """`config.yaml`: where changes live and the project's minimum workflow constraints."""

    model_config = {"extra": "forbid", "populate_by_name": True}

    artifacts_dir: str = "changes"
    workflow: dict[str, Any] | None = None
    registry: RegistrySpec | None = None

    @model_validator(mode="after")
    def validate_workflow(self) -> WorkflowConfig:
        if self.workflow is not None:
            from .workflow_models import ProjectWorkflow

            self.workflow = ProjectWorkflow.model_validate(self.workflow).model_dump()
        return self
