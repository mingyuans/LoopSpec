"""`config.yaml` registry field: accepted shapes and the injection-oriented rejections (D1)."""

from __future__ import annotations

import pytest

from loopspec.errors import WorkflowError
from loopspec.models import RegistrySpec, registry_scheme
from loopspec.workflow_planning import load_config
from tests.workflow_helpers import home_fixture


@pytest.mark.parametrize(
    ("url", "scheme"),
    [
        ("https://github.com/acme/workflows.git", "https"),
        ("ssh://git@github.com/acme/workflows.git", "ssh"),
        ("ssh://github.com:22/acme/workflows.git", "ssh"),
        ("git@github.com:acme/workflows.git", "ssh"),
        ("file:///srv/registry", "file"),
    ],
)
def test_accepted_urls(url: str, scheme: str) -> None:
    spec = RegistrySpec.model_validate({"url": url})
    assert spec.version == "latest"
    assert spec.path is None
    assert registry_scheme(spec.url) == scheme


@pytest.mark.parametrize(
    "url",
    [
        "ext::sh -c touch% /tmp/pwned",
        "http://github.com/acme/workflows.git",
        "git://github.com/acme/workflows.git",
        "https://user:token@github.com/acme/workflows.git",
        "https://token@github.com/acme/workflows.git",
        "-oProxyCommand=touch /tmp/pwned",
        "git@github.com:-oProxyCommand=x",
        "https://github.com/acme/work flows.git",
        "https://github.com/acme/\nworkflows.git",
        "https://github.com/" + "a" * 2048,
        "file://relative/path",
        "fd::3",
        "/srv/registry",
        "",
    ],
)
def test_rejected_urls(url: str) -> None:
    with pytest.raises(ValueError):
        RegistrySpec.model_validate({"url": url})


@pytest.mark.parametrize("version", ["latest", "v1.3.0", "1.2", "release_2026+build"])
def test_accepted_versions(version: str) -> None:
    assert RegistrySpec.model_validate({"url": "file:///r", "version": version}).version == version


@pytest.mark.parametrize(
    "version", ["-v1", ".v1", "v1..2", "v1.lock", "v1 2", "a" * 201, "v1/x", "v1@{0}", ""]
)
def test_rejected_versions(version: str) -> None:
    with pytest.raises(ValueError):
        RegistrySpec.model_validate({"url": "file:///r", "version": version})


@pytest.mark.parametrize("path", ["../x", "/abs", "a/../b", "a/*", "a\\b", ""])
def test_rejected_paths(path: str) -> None:
    with pytest.raises(ValueError):
        RegistrySpec.model_validate({"url": "file:///r", "path": path})


def test_unknown_registry_field_rejected() -> None:
    with pytest.raises(ValueError):
        RegistrySpec.model_validate({"url": "file:///r", "token": "x"})


def test_config_with_registry_loads(tmp_path) -> None:
    home = home_fixture(
        tmp_path,
        "workflow: {}\nregistry:\n  url: git@github.com:acme/w.git\n  version: v1.0.0\n"
        "  path: workflows\n",
    )
    config = load_config(home)
    assert config.registry is not None
    assert config.registry.path == "workflows"


def test_config_without_registry_unchanged(tmp_path) -> None:
    assert load_config(home_fixture(tmp_path)).registry is None


def test_invalid_registry_never_echoes_url(tmp_path) -> None:
    secret = "https://alice:s3cr3t@github.com/acme/w.git"
    home = home_fixture(tmp_path, f"registry:\n  url: {secret}\n")
    with pytest.raises(WorkflowError) as caught:
        load_config(home)
    assert caught.value.code == "config_invalid"
    assert "s3cr3t" not in str(caught.value.to_dict())
    assert "registry" in caught.value.fix
