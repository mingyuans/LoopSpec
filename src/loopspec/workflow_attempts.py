"""Rework records under `.attempts/`.

A record takes effect at a single write (a rollback record when written, a revision
record once `plan.yaml` reaches its revision). Files it lists that are not archived yet
count as absent and are moved by the next writing command; business code is never moved.
"""

from __future__ import annotations

import fnmatch
import os
import re
from typing import Literal

from pydantic import Field, model_validator

from .errors import WorkflowError
from .workflow_compiler import build_order
from .workflow_io import (
    ResourceBundle,
    archive_file,
    byte_hash,
    directory,
    exists,
    read_bytes,
    relative_path,
    write_yaml,
)
from .workflow_models import DIGEST_RE, ResolvedNode, StrictModel
from .workflow_state import ChangeContext, LoadedPlan, active_plan, now

GATE_CONTROL_FILES = ("begin", "evidence", "assurance")


class Move(StrictModel):
    source: str
    destination: str
    sha256: str = Field(pattern=DIGEST_RE)


class AttemptRecord(StrictModel):
    seq: int = Field(ge=1, le=1024)
    kind: Literal["rollback", "revision"]
    created: str
    plan_digest: str = Field(pattern=DIGEST_RE)
    reset: list[str] = Field(min_length=1, max_length=1024)
    files: list[Move] = Field(max_length=4096)
    # rollback only: the failed Gate and its failure report digest.
    gate: str | None = None
    failure_digest: str | None = Field(default=None, pattern=DIGEST_RE)
    # revision only: the spec digest and revision number this record leads to.
    target_digest: str | None = Field(default=None, pattern=DIGEST_RE)
    revision: int | None = Field(default=None, ge=2)

    @model_validator(mode="after")
    def kind_fields(self) -> AttemptRecord:
        rollback = (self.gate, self.failure_digest)
        revision = (self.target_digest, self.revision)
        if self.kind == "rollback":
            if None in rollback or any(item is not None for item in revision):
                raise ValueError("rollback 记录必须且只能带来源 Gate 与失败报告摘要")
        elif any(item is None for item in revision) or any(item is not None for item in rollback):
            raise ValueError("revision 记录必须且只能带目标摘要与修订号")
        if len({move.source for move in self.files}) != len(self.files):
            raise ValueError("归档清单不能重复")
        return self


def record_path(seq: int) -> str:
    return f".attempts/{seq:03d}/record.yaml"


def gate_control_paths(identity: str) -> list[str]:
    return [f".gates/{relative_path(identity)}/{name}.yaml" for name in GATE_CONTROL_FILES]


def records(loaded: LoadedPlan) -> list[AttemptRecord]:
    try:
        with directory(loaded.root, ".attempts") as fd:
            names = sorted(os.listdir(fd))
    except WorkflowError as exc:
        if isinstance(exc.__cause__, FileNotFoundError):
            return []
        raise
    if len(names) > 1024:
        raise WorkflowError("resource_limit", "重做记录过多")
    result = []
    bundle = ResourceBundle(loaded.root)
    for name in names:
        if not re.fullmatch(r"[0-9]{3,4}", name):
            continue
        try:
            record = bundle.model(f".attempts/{name}/record.yaml", AttemptRecord)
        except WorkflowError as exc:
            raise WorkflowError("history_integrity", "重做记录不完整或结构不合法") from exc
        if record.seq != int(name):
            raise WorkflowError("history_integrity", "重做记录序号与目录不一致")
        result.append(record)
    return result


def rollback_counts(items: list[AttemptRecord]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        if item.kind == "rollback" and item.gate:
            counts[item.gate] = counts.get(item.gate, 0) + 1
    return counts


def legal_source(nodes: list[ResolvedNode], reset: list[str], path: str) -> bool:
    """Only workflow paths of the reset nodes inside the Plan directory may be archived."""
    for node in nodes:
        if node.id not in reset:
            continue
        if node.generates and path.startswith("artifacts/"):
            if fnmatch.fnmatchcase(path, node.generates):
                return True
        if node.gate and path in (
            node.gate.outputs.pass_,
            node.gate.outputs.fail,
            *gate_control_paths(node.id),
        ):
            return True
    return False


def check_record(loaded: LoadedPlan, record: AttemptRecord) -> None:
    known = {node.id for node in loaded.spec.nodes}
    if not set(record.reset) <= known or (record.gate and record.gate not in record.reset):
        raise WorkflowError("history_integrity", "重做记录的节点不属于本 Plan")
    for move in record.files:
        relative_path(move.source)
        if move.destination != f".attempts/{record.seq:03d}/files/" + move.source:
            raise WorkflowError("history_integrity", "重做记录的归档目标越界")
        if not legal_source(loaded.spec.nodes, record.reset, move.source):
            raise WorkflowError("history_integrity", "重做记录只能归档 Plan 目录内的工作流路径")


def committed(loaded: LoadedPlan, record: AttemptRecord) -> bool:
    if record.kind == "revision":
        assert record.revision is not None
        return record.revision <= loaded.document.meta.revision
    return True


def committed_records(loaded: LoadedPlan) -> list[AttemptRecord]:
    return [record for record in records(loaded) if committed(loaded, record)]


def pending_sources(loaded: LoadedPlan) -> set[str]:
    """Sources of effective records not archived yet: they no longer count as outputs."""
    return {
        move.source
        for record in committed_records(loaded)
        for move in record.files
        if not exists(loaded.root, move.destination)
    }


def settle(loaded: LoadedPlan) -> None:
    """Finish archiving for every effective record; call under the Change write lock."""
    for record in committed_records(loaded):
        if any(not exists(loaded.root, move.destination) for move in record.files):
            finish(loaded, record)


def settled(ctx: ChangeContext, plan_id: str | None = None) -> LoadedPlan:
    loaded = active_plan(ctx, plan_id)
    settle(loaded)
    return loaded


def next_seq(loaded: LoadedPlan) -> int:
    """A revision record that never took effect is replaced rather than kept as history."""
    items = records(loaded)
    if items and not committed(loaded, items[-1]):
        return items[-1].seq
    return max((record.seq for record in items), default=0) + 1


def files_for(loaded: LoadedPlan, reset: list[str], last: str | None = None) -> list[str]:
    from .workflow_runtime import output_files

    selected: set[str] = set()
    for node in loaded.spec.nodes:
        if node.id not in reset:
            continue
        if node.generates:
            selected.update(output_files(loaded.root, node.generates))
        if node.gate:
            for path in [
                node.gate.outputs.pass_,
                node.gate.outputs.fail,
                *gate_control_paths(node.id),
            ]:
                if exists(loaded.root, path):
                    selected.add(path)
    ordered = sorted(selected - {last} if last else selected)
    return [*ordered, last] if last and last in selected else ordered


def build_record(
    loaded: LoadedPlan,
    kind: Literal["rollback", "revision"],
    reset: list[str],
    files: list[str],
    **extra: object,
) -> AttemptRecord:
    seq = next_seq(loaded)
    return AttemptRecord.model_validate(
        {
            "seq": seq,
            "kind": kind,
            "created": now(),
            "plan_digest": loaded.digest,
            "reset": reset,
            "files": [
                {
                    "source": path,
                    "destination": f".attempts/{seq:03d}/files/" + path,
                    "sha256": byte_hash(read_bytes(loaded.root, path)),
                }
                for path in files
            ],
            **extra,
        }
    )


def write_record(loaded: LoadedPlan, record: AttemptRecord) -> None:
    check_record(loaded, record)
    replacing = exists(loaded.root, record_path(record.seq))
    write_yaml(loaded.root, record_path(record.seq), record.model_dump(), exclusive=not replacing)


def finish(loaded: LoadedPlan, record: AttemptRecord) -> None:
    """Archive whatever the record still lists; verified by digest, never overwrites."""
    check_record(loaded, record)
    for move in record.files:
        source = exists(loaded.root, move.source)
        target = exists(loaded.root, move.destination)
        if target:
            if byte_hash(read_bytes(loaded.root, move.destination)) != move.sha256:
                raise WorkflowError(
                    "history_integrity", "归档文件内容与记录不符", "交给人核对 .attempts 后处理。"
                )
            continue
        if not source or byte_hash(read_bytes(loaded.root, move.source)) != move.sha256:
            raise WorkflowError(
                "history_integrity", "待归档文件缺失或内容已变化", "交给人核对 .attempts 后处理。"
            )
        archive_file(loaded.root, move.source, move.destination)


def downstream(nodes: list[ResolvedNode], seeds: set[str]) -> set[str]:
    graph = {node.id: set(node.requires) for node in nodes}
    result = set(seeds)
    for identity in build_order(graph):
        if graph[identity] & result:
            result.add(identity)
    return result
