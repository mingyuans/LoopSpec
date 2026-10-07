"""Shared fixtures for the `loopspec <resource> <verb>` workflow tests."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml
from typer.testing import CliRunner

from loopspec.builtin_resources import builtin_root
from loopspec.cli import app
from loopspec.workflow_git import git
from loopspec.workflow_io import atomic_write
from loopspec.workflow_state import LoadedPlan, active_plan, open_change

runner = CliRunner()
CHANGE = "AFD1111"

BUGFIX_FLOW = [
    {"id": "requirements", "use": "requirements"},
    {"id": "be", "use": "backend-implementation", "requires": ["requirements"]},
    {"id": "qa", "use": "qa-testing", "requires": ["be"], "on_fail": {"reset": ["be"]}},
    {"id": "assurance", "use": "change-assurance", "requires": ["qa"]},
]

DOCS_FLOW = [
    {"id": "requirements", "use": "requirements"},
    {"id": "design", "use": "design", "requires": ["requirements"]},
]


def invoke(home: Path, *args: str) -> tuple[int, dict]:
    result = runner.invoke(app, [*args, "--home", str(home)])
    return result.exit_code, json.loads(result.stdout) if result.stdout.strip() else {}


def init_repository(root: Path) -> None:
    git(root, ["init", "-q"])
    git(root, ["config", "user.name", "LoopSpec Test"])
    git(root, ["config", "user.email", "test@example.invalid"])
    (root / "initial.md").write_text("initial")
    git(root, ["add", "--", "initial.md"])
    git(root, ["commit", "-q", "-m", "initial"])


def home_fixture(tmp_path: Path, config: str = "workflow: {}\n") -> Path:
    home = tmp_path / "loopspec"
    home.mkdir()
    for kind in ("fragments", "profiles"):
        shutil.copytree(builtin_root() / kind, home / kind)
    (home / "config.yaml").write_text(config)
    return home


def project(tmp_path: Path, *, code: bool = True) -> Path:
    """A Git repository with a workflow home and committed frontend/backend code."""
    init_repository(tmp_path)
    home = home_fixture(tmp_path)
    if code:
        for name in ("frontend", "backend"):
            (tmp_path / name).mkdir()
            (tmp_path / name / "code.py").write_text("original\n")
    git(tmp_path, ["add", "."])
    git(tmp_path, ["commit", "-q", "-m", "workflow resources"])
    return home


def write_request(
    home: Path,
    flow: list[dict],
    *,
    name: str = "request.yaml",
    based_on: str | None = None,
    base_revision: int | None = None,
    change: str = CHANGE,
) -> str:
    """Requests live under the Change's plans/ directory, which the Git diff excludes."""
    data: dict = {"flow": flow}
    if based_on:
        data["based_on"] = based_on
    if base_revision is not None:
        data["base_revision"] = base_revision
    relative = f"changes/{change}/plans/{name}"
    path = home / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
    return relative


def new_change(home: Path, name: str = CHANGE) -> None:
    code, result = invoke(home, "change", "new", name)
    assert code == 0, result


def create_draft(home: Path, flow: list[dict], name: str = CHANGE, **kwargs) -> dict:
    request = write_request(home, flow)
    code, result = invoke(
        home, "plan", "create", "-c", name, "-f", request, *kwargs.get("args", [])
    )
    assert code == 0, result
    return result


def approve(home: Path, plan: str, name: str = CHANGE) -> dict:
    """Stands in for a human who saw `plan show` and explicitly confirmed it."""
    shown = invoke(home, "plan", "show", "-c", name, "-p", plan)[1]
    code, result = invoke(
        home, "plan", "approve", "-c", name, "-p", plan, "--digest", shown["meta"]["digest"]
    )
    assert code == 0, result
    return result


def create_approved(home: Path, flow: list[dict], name: str = CHANGE) -> LoadedPlan:
    new_change(home, name)
    draft = create_draft(home, flow, name)
    approve(home, draft["plan"], name)
    return loaded(home, name)


def loaded(home: Path, name: str = CHANGE) -> LoadedPlan:
    return active_plan(open_change(home, name))


def status(home: Path, name: str = CHANGE) -> dict:
    code, result = invoke(home, "change", "status", name)
    assert code == 0, result
    return result


def node_status(home: Path, identity: str, name: str = CHANGE) -> str:
    return next(node["status"] for node in status(home, name)["nodes"] if node["id"] == identity)


def pass_node(home: Path, identity: str, name: str = CHANGE) -> None:
    plan = loaded(home, name)
    node = next(node for node in plan.spec.nodes if node.id == identity)
    if node.generates:
        atomic_write(plan.root, node.generates, "模拟实施产物\n".encode())
    elif node.gate and node.gate.evidence:
        code, context = invoke(home, "gate", "begin", "-c", name, "-n", identity)
        assert code == 0, context
        path = f"artifacts/reports/{identity}.yaml"
        atomic_write(plan.root, path, "verdict: PASS\nsummary: 模拟验证通过\n".encode())
        code, result = invoke(
            home,
            "gate",
            "record",
            "-c",
            name,
            "-n",
            identity,
            "--round",
            context["roundId"],
            "--report",
            path,
        )
        assert code == 0, result
    elif node.gate and node.gate.assurance:
        code, result = invoke(home, "gate", "record", "-c", name, "-n", identity)
        assert code == 0, result
        assert result["verdict"] == "PASS", result
    else:
        assert node.gate
        atomic_write(plan.root, node.gate.outputs.pass_, "模拟验收通过\n".encode())


def fail_gate(home: Path, identity: str, name: str = CHANGE) -> None:
    plan = loaded(home, name)
    node = next(node for node in plan.spec.nodes if node.id == identity)
    assert node.gate and not node.gate.evidence and not node.gate.assurance
    atomic_write(
        plan.root, node.gate.outputs.fail, "verdict: FAIL\nsummary: 模拟发现缺陷\n".encode()
    )


def run_until(home: Path, stop: str, name: str = CHANGE) -> None:
    """Pass every ready node in order until `stop` becomes the next ready node."""
    for _ in range(64):
        report = status(home, name)
        ready = next(node["id"] for node in report["nodes"] if node["status"] == "ready")
        if ready == stop:
            return
        pass_node(home, ready, name)
    raise AssertionError("未到达目标节点")


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and ".write.lock" not in path.name
    }
