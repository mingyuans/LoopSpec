from pathlib import Path

import pytest
import yaml

from loopspec.errors import WorkflowError
from loopspec.workflow_catalog import WorkflowCatalog
from loopspec.workflow_compiler import FragmentExpander, build_order


def put_fragment(home: Path, name: str, nodes: list[dict]):
    (home / "fragments" / name).mkdir(parents=True, exist_ok=True)
    (home / f"fragments/{name}/fragment.yaml").write_text(
        yaml.safe_dump({"name": name, "nodes": nodes}), encoding="utf-8"
    )


def test_recursive_instances_are_independent(tmp_path: Path):
    put_fragment(tmp_path, "review", [{"id": "check", "generates": "review.md"}])
    put_fragment(
        tmp_path,
        "work",
        [
            {"id": "code", "generates": "code.md"},
            {"id": "review", "use": "review", "requires": ["code"]},
        ],
    )
    expander = FragmentExpander(WorkflowCatalog(tmp_path))
    expander.expand("work", "fe")
    expander.expand("work", "be")
    assert set(expander.leaves) == {"fe/code", "fe/review/check", "be/code", "be/review/check"}
    assert expander.instances["be/review"].parent == "be"


def test_recursive_definition_cycle(tmp_path: Path):
    put_fragment(tmp_path, "a", [{"id": "b", "use": "b"}])
    put_fragment(tmp_path, "b", [{"id": "a", "use": "a"}])
    with pytest.raises(WorkflowError, match="环"):
        FragmentExpander(WorkflowCatalog(tmp_path)).expand("a", "first")


def test_expansion_limit(tmp_path: Path):
    for index in range(17):
        nodes = (
            [{"id": "nested", "use": f"item-{index + 1}"}]
            if index < 16
            else [{"id": "write", "generates": "a.md"}]
        )
        put_fragment(tmp_path, f"item-{index}", nodes)
    with pytest.raises(WorkflowError, match="限制"):
        FragmentExpander(WorkflowCatalog(tmp_path)).expand("item-0", "root")


def test_mixed_dependencies_and_parallel_roots(tmp_path: Path):
    put_fragment(
        tmp_path, "review", [{"id": "a", "generates": "a.md"}, {"id": "b", "generates": "b.md"}]
    )
    put_fragment(
        tmp_path,
        "work",
        [
            {"id": "review", "use": "review", "requires": ["code"]},
            {"id": "finish", "requires": ["review"], "generates": "finish.md"},
            {"id": "code", "generates": "code.md"},
        ],
    )
    expander = FragmentExpander(WorkflowCatalog(tmp_path))
    expander.expand("work", "be")
    graph = expander.connect()
    assert graph["be/review/a"] == graph["be/review/b"] == {"be/code"}
    assert graph["be/finish"] == {"be/review/a", "be/review/b"}
    assert expander.instances["be"].roots == ["be/code"]
    assert expander.instances["be"].terminals == ["be/finish"]
    assert build_order(graph)[0] == "be/code"


def test_reference_reset_to_inline_node(tmp_path: Path):
    put_fragment(
        tmp_path,
        "review",
        [{"id": "check", "gate": {"outputs": {"pass": "pass.md", "fail": "fail.md"}}}],
    )
    put_fragment(
        tmp_path,
        "work",
        [
            {"id": "code", "generates": "code.md"},
            {
                "id": "review",
                "use": "review",
                "requires": ["code"],
                "on_fail": {"reset": ["code"], "max_retries": 3},
            },
        ],
    )
    expander = FragmentExpander(WorkflowCatalog(tmp_path))
    expander.expand("work", "be")
    expander.connect()
    expander.validate()
    nodes = {node.id: node for node in expander.resolve_nodes()}
    gate = nodes["be/review/check"].gate
    assert gate and gate.on_fail
    assert gate.on_fail.reset == ["be/code"]
    assert gate.on_fail.max_retries == 3


def test_reference_on_fail_pushes_down_to_every_gate(tmp_path: Path):
    put_fragment(
        tmp_path,
        "review",
        [
            {"id": "a", "gate": {"outputs": {"pass": "a/pass.md", "fail": "a/fail.md"}}},
            {
                "id": "b",
                "requires": ["a"],
                "gate": {"outputs": {"pass": "b/pass.md", "fail": "b/fail.md"}},
            },
        ],
    )
    put_fragment(
        tmp_path,
        "work",
        [
            {"id": "code", "generates": "code.md"},
            {"id": "review", "use": "review", "requires": ["code"], "on_fail": {"reset": ["code"]}},
        ],
    )
    expander = FragmentExpander(WorkflowCatalog(tmp_path))
    expander.expand("work", "be")
    expander.connect()
    expander.validate()
    gates = [node.gate for node in expander.resolve_nodes() if node.gate]
    assert [gate.on_fail.reset for gate in gates if gate.on_fail] == [["be/code"], ["be/code"]]


def test_one_gate_with_two_on_fail_is_a_conflict(tmp_path: Path):
    put_fragment(
        tmp_path,
        "review",
        [
            {
                "id": "check",
                "gate": {"outputs": {"pass": "pass.md", "fail": "fail.md"}},
                "on_fail": {"reset": ["prep"]},
                "requires": ["prep"],
            },
            {"id": "prep", "generates": "prep.md"},
        ],
    )
    put_fragment(
        tmp_path,
        "work",
        [
            {"id": "code", "generates": "code.md"},
            {"id": "review", "use": "review", "requires": ["code"], "on_fail": {"reset": ["code"]}},
        ],
    )
    expander = FragmentExpander(WorkflowCatalog(tmp_path))
    expander.expand("work", "be")
    expander.connect()
    with pytest.raises(WorkflowError) as error:
        expander.validate()
    assert error.value.code == "on_fail_conflict"


@pytest.mark.parametrize(
    "nodes",
    [
        [
            {"id": "a", "generates": "a.md", "requires": ["b"]},
            {"id": "b", "generates": "b.md", "requires": ["a"]},
        ],
        [
            {"id": "a", "generates": "a.md"},
            {
                "id": "b",
                "gate": {"outputs": {"pass": "p.md", "fail": "f.md"}},
                "on_fail": {"reset": ["a"]},
            },
        ],
        [{"id": "a", "generates": "a.md", "requires": ["missing"]}],
        [{"id": "a", "generates": "a.md", "tracks": "missing.md"}],
    ],
)
def test_invalid_graph_or_policy(tmp_path: Path, nodes):
    put_fragment(tmp_path, "work", nodes)
    expander = FragmentExpander(WorkflowCatalog(tmp_path))
    expander.expand("work", "be")
    with pytest.raises(WorkflowError):
        expander.connect()
        expander.validate()


def test_output_namespace_and_cached_resources(tmp_path: Path):
    put_fragment(
        tmp_path,
        "review",
        [
            {
                "id": "check",
                "instruction": "check.instruction.md",
                "gate": {
                    "outputs": {"pass": "review/pass.md", "fail": "review/fail.md"},
                    "templates": {"pass": "check.pass.md", "fail": "check.fail.md"},
                },
            }
        ],
    )
    for name, text in (
        ("check.instruction.md", "审查当前内容"),
        ("check.pass.md", "---\nverdict: PASS\nsummary: 通过\n---\n"),
        ("check.fail.md", "---\nverdict: FAIL\nsummary: 失败\n---\n"),
    ):
        (tmp_path / "fragments/review" / name).write_text(text)
    expander = FragmentExpander(WorkflowCatalog(tmp_path))
    expander.expand("review", "fe/review")
    expander.expand("review", "be/review")
    expander.connect()
    expander.validate()
    nodes = expander.resolve_nodes()
    assert nodes[0].gate.outputs.pass_ == "artifacts/be/review/review/pass.md"
    assert nodes[1].gate.outputs.pass_ == "artifacts/fe/review/review/pass.md"
    assert nodes[0].instruction == "fragments/review/check.instruction.md"
    assert nodes[0].gate.templates.pass_ == "fragments/review/check.pass.md"
    assert nodes[0].gate.templates.fail == "fragments/review/check.fail.md"
    assert expander.catalog.bundle.total > 0


def test_reference_resolves_resources_in_source_fragment_directory(tmp_path: Path):
    put_fragment(
        tmp_path,
        "write",
        [{"id": "doc", "generates": "doc.md", "template": "doc.template.md"}],
    )
    (tmp_path / "fragments/write/doc.template.md").write_text("## 标题")
    put_fragment(tmp_path, "work", [{"id": "spec", "use": "write"}])
    expander = FragmentExpander(WorkflowCatalog(tmp_path))
    expander.expand("work", "be")
    expander.connect()
    assert expander.resolve_nodes()[0].template == "fragments/write/doc.template.md"


@pytest.mark.parametrize(
    "node",
    [
        {"id": "doc", "generates": "doc.md", "template": "missing.template.md"},
        {"id": "doc", "generates": "doc.md", "instruction": "missing.instruction.md"},
        {
            "id": "doc",
            "gate": {
                "outputs": {"pass": "pass.md", "fail": "fail.md"},
                "templates": {"pass": "doc.pass.md", "fail": "missing.fail.md"},
            },
        },
    ],
)
def test_missing_resource_fails_compilation(tmp_path: Path, node):
    put_fragment(tmp_path, "work", [node])
    (tmp_path / "fragments/work/doc.pass.md").write_text("---\nverdict: PASS\n---\n")
    expander = FragmentExpander(WorkflowCatalog(tmp_path))
    expander.expand("work", "be")
    expander.connect()
    with pytest.raises(WorkflowError):
        expander.resolve_nodes()


@pytest.mark.parametrize(
    "outputs", [["same.md", "same.md"], ["**/*.md", "specific.md"], ["a/**/x.md", "a/b/*.md"]]
)
def test_output_collision(tmp_path: Path, outputs):
    put_fragment(
        tmp_path,
        "work",
        [{"id": "a", "generates": outputs[0]}, {"id": "b", "generates": outputs[1]}],
    )
    expander = FragmentExpander(WorkflowCatalog(tmp_path))
    expander.expand("work", "be")
    expander.connect()
    with pytest.raises(WorkflowError, match="重叠"):
        expander.resolve_nodes()


@pytest.mark.parametrize(
    "path", ["../outside.md", "/outside.md", ".gates/x.yaml", ".attempts/old.md", "a\\b.md"]
)
def test_rejects_output_escape(tmp_path: Path, path):
    put_fragment(tmp_path, "work", [{"id": "write", "generates": path}])
    expander = FragmentExpander(WorkflowCatalog(tmp_path))
    expander.expand("work", "be")
    expander.connect()
    with pytest.raises(WorkflowError):
        expander.resolve_nodes()


def test_duplicate_instance_and_symlink_resource(tmp_path: Path):
    (tmp_path / "outside").write_text("untrusted")
    put_fragment(
        tmp_path,
        "work",
        [{"id": "write", "generates": "a.md", "instruction": "write.instruction.md"}],
    )
    (tmp_path / "fragments/work/write.instruction.md").symlink_to(tmp_path / "outside")
    expander = FragmentExpander(WorkflowCatalog(tmp_path))
    expander.expand("work", "be")
    with pytest.raises(WorkflowError, match="重复"):
        expander.expand("work", "be")
    expander.connect()
    with pytest.raises(WorkflowError):
        expander.resolve_nodes()
