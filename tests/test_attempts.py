from pathlib import Path

import yaml

from loopspec.attempts import prior_attempts_for_node
from loopspec.models import NodeSpec


def make_plain_node(node_id: str) -> NodeSpec:
    return NodeSpec(
        id=node_id, description=node_id, generates=f"{node_id}.md", template=f"{node_id}.md"
    )


def write_round(change_dir: Path, round_no: int, gate: str, archived_files: list[str]) -> None:
    round_dir = change_dir / ".attempts" / f"round-{round_no:03d}"
    round_dir.mkdir(parents=True)
    for rel in archived_files:
        path = round_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("archived")
    meta = {
        "round": round_no,
        "gate": gate,
        "verdict": "FAIL",
        "summary": f"round {round_no} failed",
        "blocking_issues": [f"issue {round_no}"],
        "archived_files": archived_files,
    }
    (round_dir / "_meta.yaml").write_text(yaml.safe_dump(meta))


def test_no_history_returns_empty(tmp_path: Path):
    node = make_plain_node("design")
    assert prior_attempts_for_node(tmp_path, node) == []


def test_single_round_history(tmp_path: Path):
    write_round(tmp_path, 1, "security", ["design.md", "tasks.md", "security/fail.md"])
    node = make_plain_node("design")

    attempts = prior_attempts_for_node(tmp_path, node)
    assert len(attempts) == 1
    assert attempts[0]["round"] == 1
    assert attempts[0]["verdict"] == "FAIL"
    assert attempts[0]["blockingIssues"] == ["issue 1"]
    assert Path(attempts[0]["archivedPath"]).name == "design.md"


def test_two_rounds_sorted_ascending(tmp_path: Path):
    write_round(tmp_path, 1, "security", ["design.md"])
    write_round(tmp_path, 2, "security", ["design.md"])
    node = make_plain_node("design")

    attempts = prior_attempts_for_node(tmp_path, node)
    assert [a["round"] for a in attempts] == [1, 2]


def test_unrelated_node_not_included(tmp_path: Path):
    write_round(tmp_path, 1, "security", ["design.md", "tasks.md"])
    node = make_plain_node("proposal")

    assert prior_attempts_for_node(tmp_path, node) == []
