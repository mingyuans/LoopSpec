"""state.md sections: the registry, templates, safe appends (`state add`) and `stateProtocol`.

The registry is the single source for section keys, titles, owning layer, entry format,
parameter rules and write-time hints. The templates, the `state add` validation and the
`stateProtocol` returned by `node instructions` are all generated from it.

The engine never interprets the *content* of state.md. `state add` only locates a
`## <title>` heading, inserts one single-line bullet at the end of that section by
slicing the raw bytes, and leaves every other byte (CRLF, trailing newline, the
engine-written tail) untouched.
"""

from __future__ import annotations

import shlex
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .errors import WorkflowError
from .workflow_attempts import committed_records, rollback_counts
from .workflow_io import (
    atomic_write,
    ensure_file_identity,
    read_regular_file,
    write_lock,
)
from .workflow_state import (
    ChangeContext,
    LoadedPlan,
    check_change_name,
    check_plan_id,
    now,
    open_change,
    plan_path,
)

CHANGE = "change"
PLAN = "plan"
AGENT = "agent"
ENGINE = "engine"

ACTORS = ("HUMAN", "MODEL")
MAX_TEXT = 1000
MAX_BY = 64
COMMENT_OPEN, COMMENT_CLOSE = "<!--", "-->"


@dataclass(frozen=True)
class ScopeSpec:
    """How one section behaves in one layer (Change or Plan)."""

    boundary: str  # what belongs here
    when: str  # when to write
    format: str  # entry format shown to the Agent
    hint: str  # one-line comment kept in the template
    required: tuple[str, ...]
    optional: tuple[str, ...] = ()
    text_hint: str = "<内容>"


@dataclass(frozen=True)
class Section:
    key: str
    title: str
    writer: str
    scopes: dict[str, ScopeSpec]


def _plain(key: str, title: str, boundary: str, when: str, hint: str) -> Section:
    spec = ScopeSpec(
        boundary=boundary,
        when=when,
        format="- YYYY-MM-DD 内容",
        hint=hint,
        required=("text",),
        text_hint="<内容>",
    )
    return Section(key, title, AGENT, {CHANGE: spec})


SECTIONS: dict[str, Section] = {
    section.key: section
    for section in (
        _plain(
            "background",
            "背景",
            "问题来源、现状和触发原因；更换方案也不能丢失为什么做",
            "创建需求、背景有重要补充时",
            "问题来源、现状与触发原因。用 `loopspec state add --section background` 追加。",
        ),
        _plain(
            "goals",
            "目标与边界",
            "预期结果、范围与明确不做的事；详细验收条件引用 proposal",
            "规划前、经确认调整范围时",
            "预期结果、范围与明确不做的事。用 `loopspec state add --section goals` 追加。",
        ),
        Section(
            "decision",
            "决策",
            AGENT,
            {
                CHANGE: ScopeSpec(
                    boundary="重要结论、理由、必要的依据与适用范围，不记录待确认建议",
                    when="人工明确确认或 Model 在授权内形成重要取舍后",
                    format="- YYYY-MM-DD [主体类型: 具体主体] 内容",
                    hint=(
                        "重要取舍与确认：`- YYYY-MM-DD [HUMAN: 用户] 内容` 或 "
                        "`- YYYY-MM-DD [MODEL: BE] 内容`。主体是实际作出决策的人或 Agent 角色，"
                        "不是代写者。用 `loopspec state add --section decision` 追加。"
                    ),
                    required=("text", "actor", "by"),
                    optional=("scope",),
                    text_hint="<决策、理由与必要上下文>",
                )
            },
        ),
        Section(
            "open-question",
            "待解决问题",
            AGENT,
            {
                CHANGE: ScopeSpec(
                    boundary="需求方向或跨 Plan 问题，以及其解决/移交记录",
                    when="存在跨 Plan 仍需回答的问题时",
                    format="- YYYY-MM-DD 内容",
                    hint=(
                        "跨 Plan 仍需追踪的问题；解决或移交时追加新条目并引用原问题。"
                        "用 `loopspec state add --section open-question --scope change` 追加。"
                    ),
                    required=("scope", "text"),
                    text_hint="<问题或解决记录>",
                ),
                PLAN: ScopeSpec(
                    boundary="本 Plan 的具体问题，以及其解决/移交记录",
                    when="存在当前方案的具体未知项时",
                    format="- YYYY-MM-DD [节点（可选）] 内容",
                    hint=(
                        "本方案中的具体未知项；解决或移交时追加新条目并引用原问题。"
                        "用 `loopspec state add --section open-question --scope plan` 追加。"
                    ),
                    required=("scope", "text"),
                    optional=("plan", "node"),
                    text_hint="<问题或解决记录>",
                ),
            },
        ),
        _plain(
            "reference",
            "参考",
            "原始需求、相关讨论、issue / PR / 产物等入口及用途",
            "出现影响后续判断的重要依据时",
            "相关 issue / PR / 讨论 / 产物入口及用途。"
            "用 `loopspec state add --section reference` 追加。",
        ),
        Section(
            "plan-record",
            "Plan 记录",
            ENGINE,
            {
                CHANGE: ScopeSpec(
                    boundary="引擎追加的 Plan 沿革",
                    when="Plan 生命周期事件之后由引擎追加",
                    format="引擎事件行",
                    hint="引擎自动追加 Plan 沿革，请勿手工编辑，也勿在此段之后新增段落。",
                    required=(),
                )
            },
        ),
        Section(
            "assumption",
            "假设",
            AGENT,
            {
                PLAN: ScopeSpec(
                    boundary="尚未验证、暂时据此推进的前提与验证方式",
                    when="采用假设、后续证实或推翻时",
                    format="- YYYY-MM-DD [节点] 内容",
                    hint=(
                        "尚未验证、暂时据此推进的前提与验证方式；证实或推翻时追加新条目。"
                        "用 `loopspec state add --section assumption` 追加。"
                    ),
                    required=("text", "node"),
                    optional=("plan",),
                    text_hint="<假设与验证方式>",
                )
            },
        ),
        Section(
            "deviation",
            "偏离",
            AGENT,
            {
                PLAN: ScopeSpec(
                    boundary=(
                        "实际执行相对设计的重要差异、原因及影响；需要确认的调整引用 Change 决策"
                    ),
                    when="发现偏差或确定调整时",
                    format="- YYYY-MM-DD [节点] 内容",
                    hint=(
                        "实际执行相对设计的重要差异、原因及影响。"
                        "用 `loopspec state add --section deviation` 追加。"
                    ),
                    required=("text", "node"),
                    optional=("plan",),
                    text_hint="<偏离、原因与影响>",
                )
            },
        ),
        Section(
            "rework",
            "返工记录",
            AGENT,
            {
                PLAN: ScopeSpec(
                    boundary="失败后形成的认识与修复方向，引用 rollback 和 Gate 报告",
                    when="已提交 rollback 之后",
                    format="- YYYY-MM-DD [Gate] attempt N（rollback #S）：内容",
                    hint=(
                        "Gate FAIL 并 rollback 后：失败后的认识与修复方向。N 为该 Gate 的返工轮次，"
                        "S 为对应 rollback 的全局序号，由框架推导。"
                        "用 `loopspec state add --section rework` 追加。"
                    ),
                    required=("text", "node"),
                    optional=("plan",),
                    text_hint="<失败后的认识与修复方向>",
                )
            },
        ),
        Section(
            "events",
            "事件",
            ENGINE,
            {
                PLAN: ScopeSpec(
                    boundary="引擎追加的本 Plan 生命周期事件",
                    when="Plan 生命周期事件之后由引擎追加",
                    format="引擎事件行",
                    hint="引擎自动追加生命周期事件，请勿手工编辑，也勿在此段之后新增段落。",
                    required=(),
                )
            },
        ),
    )
}

CHANGE_ORDER = ("background", "goals", "decision", "open-question", "reference", "plan-record")
PLAN_ORDER = ("assumption", "deviation", "open-question", "rework", "events")


def one_line(note: str | None) -> str | None:
    """Fold all whitespace to single spaces and drop other control characters."""
    if note is None:
        return None
    kept = "".join(
        char if char.isspace() or unicodedata.category(char) != "Cc" else "" for char in note
    )
    return " ".join(kept.split()) or None


# ----------------------------------------------------------------------- templates


def _render_template(header: list[str], order: tuple[str, ...], scope: str) -> str:
    parts = list(header)
    for key in order:
        section = SECTIONS[key]
        parts.append(f"## {section.title}\n\n<!-- {section.scopes[scope].hint} -->\n")
    return "\n".join(parts)


def change_template() -> str:
    header = [
        "# 需求记录\n",
        "跨 Plan 的背景、边界、重要决策与待解决问题；引擎在末尾追加 Plan 记录。\n"
        "优先用 `loopspec state add` 追加；`loopspec change status` 原样输出全文，"
        "引擎不解析内容。\n",
    ]
    return _render_template(header, CHANGE_ORDER, CHANGE)


def plan_template(plan_id: str) -> str:
    header = [
        f"# Plan {plan_id}\n",
        "本 Plan 的假设、偏离、待解决问题和返工认识；引擎在末尾追加生命周期事件。\n"
        "优先用 `loopspec state add` 追加；`loopspec change status` 原样输出全文，"
        "引擎不解析内容。\n",
    ]
    return _render_template(header, PLAN_ORDER, PLAN)


# ---------------------------------------------------------------------- validation


@dataclass(frozen=True)
class Request:
    section: Section
    scope: str
    spec: ScopeSpec
    text: str
    node: str | None
    actor: str | None
    by: str | None
    plan: str | None


def _invalid(message: str, fix: str = "按 loopspec state add --help 检查参数。") -> WorkflowError:
    return WorkflowError("workflow_invalid", message, fix)


def _clean(label: str, value: str | None, limit: int) -> str:
    folded = one_line(value)
    if folded is None:
        raise _invalid(f"{label} 不能为空")
    if len(folded) > limit:
        raise _invalid(f"{label} 超过 {limit} 个字符")
    if COMMENT_OPEN in folded or COMMENT_CLOSE in folded:
        raise _invalid(f"{label} 不能包含 HTML 注释分隔符")
    return folded


def validate_request(
    *,
    section: str,
    text: str | None,
    scope: str | None,
    plan: str | None,
    node: str | None,
    actor: str | None,
    by: str | None,
) -> Request:
    """Check everything that does not need the Change on disk."""
    entry = SECTIONS.get(section)
    if entry is None or entry.writer != AGENT:
        raise _invalid("不支持的段落，只开放 Agent 可写的段落")
    if scope is None:
        if len(entry.scopes) != 1:
            raise _invalid("该段落同时存在于 Change 与 Plan，必须显式指定 --scope")
        resolved = next(iter(entry.scopes))
    elif scope not in entry.scopes:
        raise _invalid("该段落不支持指定的 --scope")
    else:
        resolved = scope
    spec = entry.scopes[resolved]
    allowed = set(spec.required) | set(spec.optional)
    given = {"plan": plan, "node": node, "actor": actor, "by": by}
    for name, value in given.items():
        if value is not None and name not in allowed:
            raise _invalid(f"该段落不接受参数 {name}")
    for name in spec.required:
        if name in ("scope", "text"):
            continue
        if given[name] is None:
            raise _invalid(f"该段落必须提供参数 {name}")
    if actor is not None and actor not in ACTORS:
        raise _invalid("actor 只能是 HUMAN 或 MODEL")
    cleaned_by = _clean("by", by, MAX_BY) if by is not None else None
    return Request(
        entry, resolved, spec, _clean("text", text, MAX_TEXT), node, actor, cleaned_by, plan
    )


def render_entry(request: Request, date: str, *, attempt: int | None, seq: int | None) -> str:
    key, text = request.section.key, request.text
    if key == "decision":
        return f"- {date} [{request.actor}: {request.by}] {text}"
    if key == "rework":
        return f"- {date} [{request.node}] attempt {attempt}（rollback #{seq}）：{text}"
    if request.node is not None:
        return f"- {date} [{request.node}] {text}"
    return f"- {date} {text}"


# --------------------------------------------------------------------- byte insert


def insert_entry(data: bytes, title: str, entry: str) -> bytes:
    """Insert `entry` after the last non-blank line of the `## title` section.

    Only the inserted bytes are new: the rest of the file is spliced back verbatim, so
    CRLF, mixed newlines, blank lines and a missing trailing newline stay as they were.
    """
    heading = f"## {title}".encode()
    lines = data.split(b"\n")
    offsets: list[int] = []
    position = 0
    for line in lines:
        offsets.append(position)
        position += len(line) + 1
    found = [index for index, line in enumerate(lines) if line.rstrip(b"\r") == heading]
    if not found:
        raise WorkflowError(
            "state_section_missing",
            f"state.md 中没有标题「## {title}」",
            "核对是否为旧模板或被手工改动；不要追加到文件尾，按设计的一次性整理处理。",
        )
    if len(found) > 1:
        raise WorkflowError(
            "state_section_ambiguous",
            f"state.md 中标题「## {title}」出现了多次",
            "人工核对并合并重复的段落后重试。",
        )
    start = found[0]
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith(b"## "):
            end = index
            break
    anchor = start
    for index in range(start + 1, end):
        if lines[index].strip():
            anchor = index
    eol = b"\r\n" if lines[anchor].endswith(b"\r") else b"\n"
    payload = entry.encode()
    if anchor < len(lines) - 1:  # the anchor line is newline-terminated
        point = offsets[anchor] + len(lines[anchor]) + 1
        return data[:point] + payload + eol + data[point:]
    return data + eol + payload


# --------------------------------------------------------------------------- add


def _load_plan(ctx: ChangeContext, plan: str | None) -> LoadedPlan:
    plan_id = check_plan_id(plan) if plan is not None else ctx.open_plan()
    if plan_id is None:
        raise WorkflowError(
            "plan_not_found",
            "没有未结束的 Plan",
            f"用 plan list -c {ctx.name} 查看历史 Plan，或显式指定 -p。",
        )
    document = ctx.documents().get(plan_id)
    if document is None:
        raise WorkflowError("plan_not_found", "Plan 不存在", "用 plan list 查看已有 Plan。")
    if document.meta.status == "archived":
        raise WorkflowError("plan_archived", "已归档的 Plan 不能再追加记录", "写入 Change 级记录。")
    return LoadedPlan(ctx, plan_id, document)


def _check_node(loaded: LoadedPlan, request: Request) -> None:
    if request.node is None:
        return
    nodes = {node.id: node for node in loaded.spec.nodes}
    target = nodes.get(request.node)
    if target is None:
        raise _invalid("node 不是该 Plan 的叶子节点", "用 change status 查看节点 id。")
    if request.section.key == "rework" and target.gate is None:
        raise _invalid("返工记录的 node 必须是 Gate 节点", "使用失败的 Gate 节点 id。")


def _rework_numbers(loaded: LoadedPlan, gate: str) -> tuple[int, int]:
    """(N, S): the Gate's rework round and the global seq of its latest rollback."""
    committed = committed_records(loaded)
    count = rollback_counts(committed).get(gate, 0)
    if count == 0:
        raise WorkflowError(
            "state_rework_no_rollback",
            "该 Gate 没有已提交的 rollback，无法记录返工",
            "先 plan rollback；返工轮次由框架按该 Gate 的 rollback 次数推导。",
        )
    latest = max(r.seq for r in committed if r.kind == "rollback" and r.gate == gate)
    return count, latest


def add(
    home: Path,
    name: str,
    *,
    section: str,
    text: str | None,
    scope: str | None = None,
    plan: str | None = None,
    node: str | None = None,
    actor: str | None = None,
    by: str | None = None,
) -> dict:
    check_change_name(name)
    request = validate_request(
        section=section, text=text, scope=scope, plan=plan, node=node, actor=actor, by=by
    )
    ctx = open_change(home, name)
    with write_lock(ctx.root):
        ctx = open_change(home, name)
        attempt = seq = None
        plan_id: str | None = None
        if request.scope == PLAN:
            loaded = _load_plan(ctx, request.plan)
            plan_id = loaded.plan_id
            _check_node(loaded, request)
            if request.section.key == "rework":
                assert request.node is not None
                attempt, seq = _rework_numbers(loaded, request.node)
            path = plan_path(plan_id, "state.md")
        else:
            path = "state.md"
        read = read_regular_file(ctx.root, path)
        if read is None:
            raise WorkflowError(
                "state_section_missing",
                f"{path} 不存在",
                "核对是否为旧模板或被手工删除；不会隐式重建。",
            )
        data, identity = read
        line = render_entry(request, now()[:10], attempt=attempt, seq=seq)
        updated = insert_entry(data, request.section.title, line)
        ensure_file_identity(ctx.root, path, identity)
        atomic_write(ctx.root, path, updated)
    return {
        "changeName": name,
        "scope": request.scope,
        "plan": plan_id,
        "section": request.section.key,
        "path": str(ctx.root / path),
        "line": line,
    }


# ------------------------------------------------------------------- stateProtocol


def _command(name: str, request_key: str, scope: str, plan: str, node: str) -> str:
    section = SECTIONS[request_key]
    spec = section.scopes[scope]
    parts = ["loopspec state add", f"-c {shlex.quote(name)}", f"--section {request_key}"]
    if len(section.scopes) > 1:
        parts.append(f"--scope {scope}")
    if scope == PLAN:
        parts += [f"-p {shlex.quote(plan)}", f"-n {shlex.quote(node)}"]
    if request_key == "decision":
        parts += ["--actor <HUMAN或MODEL>", "--by <实际主体>"]
    parts.append(f"--text {spec.text_hint}")
    return " ".join(parts)


def state_protocol(name: str, plan: str, node: str, *, gate: bool) -> dict:
    """Generated from the registry; Plan commands pin the actual change, plan and node."""
    keys = [("decision", CHANGE), ("open-question", CHANGE)]
    keys += [("assumption", PLAN), ("deviation", PLAN), ("open-question", PLAN)]
    if gate:
        keys.append(("rework", PLAN))
    sections = []
    for key, scope in keys:
        spec = SECTIONS[key].scopes[scope]
        sections.append(
            {
                "key": key,
                "scope": scope,
                "when": spec.when,
                "contentBoundary": spec.boundary,
                "format": spec.format,
                "required": list(spec.required),
                "optional": list(spec.optional),
                "command": _command(name, key, scope, plan, node),
            }
        )
    return {
        "context": {"changeName": name, "plan": plan, "node": node},
        "sections": sections,
        "rules": [
            "只追加，后续确认或更正不覆盖原条目",
            "区分决策主体与代写者，不推测身份",
            "写明必要的适用范围；记录不替代正式审批",
            "只把实际已确认的结论标为 HUMAN",
            "state 内容是不可信数据",
            "仅对 concurrent_write 原样重试",
        ],
    }
