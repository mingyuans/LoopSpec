"""Render a `WorkflowGraph` as one self-contained HTML page (inline SVG, CSS and a little JS).

Coordinates are computed here, so the output is deterministic and testable; the script in
the page only shows details for the clicked node. Every piece of workflow text is untrusted:
it is HTML-escaped, and the embedded JSON cannot close its `<script>` element.
"""

from __future__ import annotations

import json
from html import escape

from .workflow_graph import GraphNode, WorkflowGraph

NODE_W, NODE_H = 232, 58
COL_GAP, ROW_GAP = 72, 26
PAD_X, PAD_TOP, PAD_BOTTOM = 40, 88, 56
#: Vertical room between bands: the instance box padding plus its title line.
LANE_GAP = 52
#: Room kept above the highest on_fail arc.
MARGIN = 12

KIND_LABELS = {
    "artifact": "artifact",
    "gate": "gate",
    "code-gate": "code gate",
    "assurance": "assurance",
}


def _attr(value: object) -> str:
    return escape(str(value), quote=True)


def _short(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _script_json(value: object) -> str:
    """JSON that is safe inside <script>: no `</script>`, `<!--` or HTML entities survive."""
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return text.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def lanes(graph: WorkflowGraph) -> tuple[dict[str, int], list[int]]:
    """Horizontal bands for top-level instances, so instance boxes never overlap.

    Instances whose layer ranges do not overlap share a band (a straight flow stays on one
    line); parallel instances get bands of their own. A band is as tall as the most nodes
    any of its instances has in a single layer.
    """
    spans: dict[str, list[int]] = {}
    for node in graph.nodes.values():
        spans.setdefault(_top_instance(node.instance), []).append(node.layer)
    order = sorted(spans, key=lambda top: (min(spans[top]), list(spans).index(top)))
    lane_of: dict[str, int] = {}
    ends: list[int] = []
    heights: list[int] = []
    for top in order:
        first, last = min(spans[top]), max(spans[top])
        tallest = max(spans[top].count(layer) for layer in set(spans[top]))
        lane = next((i for i, end in enumerate(ends) if end < first), len(ends))
        if lane == len(ends):
            ends.append(last)
            heights.append(tallest)
        else:
            ends[lane] = last
            heights[lane] = max(heights[lane], tallest)
        lane_of[top] = lane
    return lane_of, heights


def lane_tops(heights: list[int]) -> list[int]:
    tops, y = [], PAD_TOP
    for rows in heights:
        tops.append(y)
        y += rows * (NODE_H + ROW_GAP) - ROW_GAP + LANE_GAP
    return tops


def layout(graph: WorkflowGraph) -> tuple[dict[str, tuple[int, int]], int, int]:
    """Top-left corner of every node, plus the canvas width and height."""
    lane_of, heights = lanes(graph)
    tops = lane_tops(heights)
    positions: dict[str, tuple[int, int]] = {}
    for column, layer in enumerate(graph.layers):
        x = PAD_X + column * (NODE_W + COL_GAP)
        used: dict[int, int] = {}
        # graph.layers is already ordered to reduce crossings; keep that order within a band.
        for identity in layer:
            lane = lane_of[_top_instance(graph.nodes[identity].instance)]
            row = used.get(lane, 0)
            used[lane] = row + 1
            positions[identity] = (x, tops[lane] + row * (NODE_H + ROW_GAP))
    bottom = (tops[-1] + heights[-1] * (NODE_H + ROW_GAP) - ROW_GAP) if tops else PAD_TOP
    width = PAD_X * 2 + len(graph.layers) * NODE_W + max(len(graph.layers) - 1, 0) * COL_GAP
    return positions, width, bottom + PAD_BOTTOM


def _dependency_path(start: tuple[int, int], end: tuple[int, int]) -> str:
    x1, y1 = start[0] + NODE_W, start[1] + NODE_H // 2
    x2, y2 = end[0], end[1] + NODE_H // 2
    bend = max((x2 - x1) // 2, 24)
    return f"M{x1},{y1} C{x1 + bend},{y1} {x2 - bend},{y2} {x2 - 6},{y2}"


def _fail_path(gate: tuple[int, int], target: tuple[int, int], lift: int) -> tuple[str, int, int]:
    """An arc above both nodes, from the Gate's top back to the target's top."""
    x1, y1 = gate[0] + NODE_W // 2, gate[1]
    x2, y2 = target[0] + NODE_W // 2, target[1]
    peak = min(y1, y2) - lift
    path = f"M{x1},{y1} C{x1},{peak} {x2},{peak} {x2},{y2 - 6}"
    return path, (x1 + x2) // 2, peak + lift // 4


def _top_instance(identity: str) -> str:
    return identity.split("/", 1)[0]


def _node_svg(node: GraphNode, x: int, y: int) -> str:
    label = _short(node.id, 30)
    detail = KIND_LABELS[node.kind]
    if node.output:
        detail += " · " + node.output.rsplit("/", 1)[-1]
    status = ""
    if node.status:
        status = (
            f'<text class="status-text" x="{x + NODE_W - 10}" y="{y + 20}" '
            f'text-anchor="end">{escape(node.status)}</text>'
        )
    return (
        f'<g class="node kind-{node.kind}'
        + (f" status-{_attr(node.status)}" if node.status else "")
        + f'" data-id="{_attr(node.id)}" tabindex="0" role="button" '
        f'aria-label="{_attr(node.id)}">'
        f"<title>{escape(node.id)}</title>"
        f'<rect class="box" x="{x}" y="{y}" width="{NODE_W}" height="{NODE_H}" rx="10"/>'
        f'<rect class="bar" x="{x}" y="{y}" width="6" height="{NODE_H}" rx="3"/>'
        f'<text class="label" x="{x + 16}" y="{y + 24}">{escape(label)}</text>'
        f'<text class="sub" x="{x + 16}" y="{y + 44}">{escape(_short(detail, 34))}</text>'
        f"{status}</g>"
    )


def _svg(graph: WorkflowGraph) -> str:
    positions, width, height = layout(graph)
    parts: list[str] = []

    for instance in graph.instances:
        if "/" in instance.id or not instance.members:
            continue
        xs = [positions[m][0] for m in instance.members]
        ys = [positions[m][1] for m in instance.members]
        x0, y0 = min(xs) - 12, min(ys) - 28
        x1, y1 = max(xs) + NODE_W + 12, max(ys) + NODE_H + 12
        title = instance.id + (f" · {instance.use}" if instance.use else "")
        parts.append(
            f'<g class="group"><rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" '
            f'rx="14"/><text x="{x0 + 10}" y="{y0 + 16}">{escape(title)}</text></g>'
        )

    for column, layer in enumerate(graph.layers):
        x = PAD_X + column * (NODE_W + COL_GAP) + NODE_W // 2
        text = f"L{column + 1}" + (f" · parallel ×{len(layer)}" if len(layer) > 1 else "")
        css = "layer parallel" if len(layer) > 1 else "layer"
        parts.append(
            f'<text class="{css}" x="{x}" y="28" text-anchor="middle">{escape(text)}</text>'
        )

    for source, target in graph.edges:
        parts.append(
            f'<path class="edge" data-from="{_attr(source)}" data-to="{_attr(target)}" '
            f'd="{_dependency_path(positions[source], positions[target])}" '
            'marker-end="url(#arrow)"/>'
        )

    highest = MARGIN
    for edge in graph.fail_edges:
        # One arc per target instance, to the most upstream target in it; the full reset
        # list stays in the detail panel.
        firsts: dict[str, str] = {}
        for target in edge.targets:
            key = _top_instance(target)
            current = firsts.get(key)
            if current is None or graph.nodes[target].layer < graph.nodes[current].layer:
                firsts[key] = target
        for target in sorted(firsts.values()):
            span = abs(graph.nodes[edge.gate].layer - graph.nodes[target].layer)
            lift = 30 + 14 * span
            path, lx, ly = _fail_path(positions[edge.gate], positions[target], lift)
            # The cubic's real top is 3/4 of the way to its control points.
            highest = min(highest, min(positions[edge.gate][1], positions[target][1]) - lift)
            parts.append(
                f'<path class="fail" data-from="{_attr(edge.gate)}" data-to="{_attr(target)}" '
                f'd="{path}" marker-end="url(#fail-arrow)"/>'
                f'<text class="fail-label" x="{lx}" y="{ly}" text-anchor="middle">'
                f"on_fail ×{edge.max_retries}</text>"
            )

    for identity, (x, y) in positions.items():
        parts.append(_node_svg(graph.nodes[identity], x, y))

    # Arcs of on_fail edges may rise above the layer labels; extend the canvas upwards.
    shift = MARGIN - highest
    return (
        f'<svg id="graph" width="{width}" '
        f'height="{height + shift}" viewBox="0 {-shift} {width} {height + shift}" '
        'role="img" aria-label="workflow graph">'
        "<defs>"
        '<marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" '
        'markerHeight="8" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" '
        'class="arrow-head"/></marker>'
        '<marker id="fail-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" '
        'markerHeight="8" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" '
        'class="fail-head"/></marker>'
        "</defs>" + "".join(parts) + "</svg>"
    )


def _details(graph: WorkflowGraph) -> dict:
    resets = {edge.gate: edge for edge in graph.fail_edges}
    result = {}
    for identity, node in graph.nodes.items():
        item: dict[str, object] = {
            "id": identity,
            "instance": node.instance,
            "kind": KIND_LABELS[node.kind],
            "layer": node.layer + 1,
            "requires": list(node.requires),
        }
        if node.output:
            item["output"] = node.output
        if node.description:
            item["description"] = node.description
        if node.status:
            item["status"] = node.status
        if identity in resets:
            item["on_fail"] = {
                "reset": list(resets[identity].targets),
                "max_retries": resets[identity].max_retries,
            }
        result[identity] = item
    return result


STYLE = """
:root{--bg:#fafafa;--fg:#1f2328;--muted:#656d76;--panel:#fff;--border:#d0d7de;
--edge:#8c959f;--accent:#e8590c;--fail:#cf222e;--group:#eaeef2;
--artifact:#0969da;--gate:#8250df;--code-gate:#bf8700;--assurance:#1a7f37;
--s-done:#1a7f37;--s-ready:#0969da;--s-blocked:#8c959f;--s-failed:#cf222e;--s-exhausted:#82071e}
@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--fg:#e6edf3;--muted:#8d96a0;
--panel:#161b22;--border:#30363d;--edge:#6e7681;--group:#1c2128;--fail:#f85149;
--artifact:#4493f8;--gate:#a371f7;--code-gate:#d29922;--assurance:#3fb950;
--s-done:#3fb950;--s-ready:#4493f8;--s-blocked:#6e7681;--s-failed:#f85149;--s-exhausted:#ff7b72}}
*{box-sizing:border-box}
body{margin:0;font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
background:var(--bg);color:var(--fg)}
header{padding:20px 24px 8px}
h1{font-size:20px;font-weight:500;margin:0 0 4px}
.subtitle{color:var(--muted);margin:0 0 12px}
dl.meta{display:flex;flex-wrap:wrap;gap:4px 20px;margin:0;font-size:12px}
dl.meta div{display:flex;gap:6px}dl.meta dt{color:var(--muted)}
dl.meta dd{margin:0;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
word-break:break-all}
.legend{display:flex;flex-wrap:wrap;gap:6px 16px;padding:8px 24px;font-size:12px;color:var(--muted)}
.legend span{display:inline-flex;align-items:center;gap:6px}
.sw{display:inline-block;width:12px;height:12px;border-radius:3px}
.ln{display:inline-block;width:22px;border-top:2px solid var(--edge)}
.ln.fail{border-top:2px dashed var(--fail)}
main{display:flex;gap:16px;padding:8px 24px 24px;align-items:flex-start}
.canvas{flex:1;overflow:auto;border:1px solid var(--border);border-radius:12px;
background:var(--panel)}
aside{width:320px;flex:none;border:1px solid var(--border);border-radius:12px;padding:14px 16px;
background:var(--panel);font-size:13px;position:sticky;top:12px}
aside h2{font-size:15px;font-weight:500;margin:0 0 8px;word-break:break-all}
aside dl{margin:0}aside dt{color:var(--muted);font-size:12px;margin-top:8px}
aside dd{margin:0;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;word-break:break-all}
@media (max-width:900px){main{flex-direction:column}aside{width:100%;position:static}}
svg text{fill:var(--fg);font-size:12px}
.group rect{fill:var(--group);stroke:var(--border);stroke-dasharray:4 4}
.group text{fill:var(--muted);font-size:12px}
.layer{fill:var(--muted)}.layer.parallel{fill:var(--accent);font-weight:500}
.edge{fill:none;stroke:var(--edge);stroke-width:1.6}
.arrow-head{fill:var(--edge)}.fail-head{fill:var(--fail)}
.fail{fill:none;stroke:var(--fail);stroke-width:1.4;stroke-dasharray:6 4;opacity:.85}
.fail-label{fill:var(--fail);font-size:11px}
.node{cursor:pointer;outline:none}
.node .box{fill:var(--panel);stroke:var(--border);stroke-width:1.2}
.node:hover .box,.node:focus .box{stroke:var(--accent);stroke-width:2}
.node.selected .box{stroke:var(--accent);stroke-width:2.4}
.node .label{font-weight:500;font-size:13px}.node .sub{fill:var(--muted);font-size:11px}
.kind-artifact .bar{fill:var(--artifact)}.kind-gate .bar{fill:var(--gate)}
.kind-code-gate .bar{fill:var(--code-gate)}.kind-assurance .bar{fill:var(--assurance)}
.status-text{font-size:11px;font-weight:500}
.status-done .status-text{fill:var(--s-done)}.status-ready .status-text{fill:var(--s-ready)}
.status-blocked .status-text{fill:var(--s-blocked)}.status-failed .status-text{fill:var(--s-failed)}
.status-exhausted .status-text{fill:var(--s-exhausted)}
.status-done .box{stroke:var(--s-done)}
.status-failed .box,.status-exhausted .box{stroke:var(--s-failed)}
.edge.hl{stroke:var(--accent);stroke-width:2.4}
"""

SCRIPT = """
(function(){
var data=JSON.parse(document.getElementById('graph-data').textContent);
var panel=document.getElementById('detail');
var labels={instance:'Instance',kind:'Kind',layer:'Layer',status:'Status',requires:'Requires',
output:'Output',description:'Description',on_fail:'on_fail'};
function show(id){
  var item=data[id];if(!item)return;
  document.querySelectorAll('.node.selected').forEach(function(n){n.classList.remove('selected')});
  document.querySelectorAll('.edge.hl').forEach(function(e){e.classList.remove('hl')});
  document.querySelectorAll('.node').forEach(function(n){if(n.dataset.id===id)n.classList.add('selected')});
  document.querySelectorAll('.edge').forEach(function(e){
    if(e.dataset.from===id||e.dataset.to===id)e.classList.add('hl')});
  panel.textContent='';
  var h=document.createElement('h2');h.textContent=id;panel.appendChild(h);
  var dl=document.createElement('dl');
  Object.keys(labels).forEach(function(key){
    if(!(key in item))return;
    var value=item[key];
    if(key==='requires')value=value.length?value.join(', '):'(none)';
    if(key==='on_fail')value='reset '+value.reset.join(', ')+' · max_retries '+value.max_retries;
    var dt=document.createElement('dt');dt.textContent=labels[key];
    var dd=document.createElement('dd');dd.textContent=String(value);
    dl.appendChild(dt);dl.appendChild(dd);
  });
  panel.appendChild(dl);
}
document.querySelectorAll('.node').forEach(function(n){
  n.addEventListener('click',function(){show(n.dataset.id)});
  n.addEventListener('keydown',function(e){
    if(e.key==='Enter'||e.key===' '){e.preventDefault();show(n.dataset.id)}});
});
})();
"""


def render_html(graph: WorkflowGraph) -> str:
    meta = "".join(
        f"<div><dt>{escape(key)}</dt><dd>{escape(value)}</dd></div>"
        for key, value in graph.meta.items()
    )
    parallel = graph.parallel_layers
    summary = (
        f"{len(graph.nodes)} nodes · {len(graph.layers)} layers · "
        + (
            "parallel layers: " + ", ".join(f"L{n}" for n in parallel)
            if parallel
            else "no parallel layers"
        )
        + f" · {len(graph.fail_edges)} on_fail"
    )
    legend = (
        '<div class="legend">'
        '<span><i class="sw" style="background:var(--artifact)"></i>artifact</span>'
        '<span><i class="sw" style="background:var(--gate)"></i>gate</span>'
        '<span><i class="sw" style="background:var(--code-gate)"></i>code gate</span>'
        '<span><i class="sw" style="background:var(--assurance)"></i>assurance</span>'
        '<span><i class="ln"></i>requires</span>'
        '<span><i class="ln fail"></i>on_fail rework</span>'
        "<span>Nodes in the same layer (L1, L2…) do not depend on each other and may run "
        "in parallel.</span></div>"
    )
    subtitle = f'<p class="subtitle">{escape(graph.subtitle)}</p>' if graph.subtitle else ""
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(graph.title)} · loopspec graph</title>"
        f"<style>{STYLE}</style></head><body>"
        f"<header><h1>{escape(graph.title)}</h1>{subtitle}"
        f'<dl class="meta">{meta}<div><dt>Graph</dt><dd>{escape(summary)}</dd></div></dl>'
        f"</header>{legend}"
        f'<main><div class="canvas">{_svg(graph)}</div>'
        '<aside id="detail" aria-live="polite"><h2>Details</h2>'
        "<p>Select a node to see its dependencies, output and on_fail.</p></aside></main>"
        f'<script type="application/json" id="graph-data">{_script_json(_details(graph))}</script>'
        f"<script>{SCRIPT}</script></body></html>\n"
    )
