#!/usr/bin/env python3
"""Render VDA 5050 order / state / visualization messages as one self-contained HTML (inline SVG).

usage: render.py [--order order.json] [--state state.json] [--vis visualization.json] [-o out.html]

Draws nodes at nodePosition, base solid / horizon dashed, lastNodeId ring, robot position (state or
visualization), per-node action badges (order actions matched to state actionStates by actionId), the
state header, and the semantic findings from validate.py. No JavaScript, no external assets.
"""
import html
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
try:
    from validate import order_semantics, state_semantics
except ImportError:  # pragma: no cover
    order_semantics = state_semantics = lambda m: []

W, H, PAD = 960, 620, 50
STATUS_COLOR = {"WAITING": "#9aa4b2", "INITIALIZING": "#7c9cf5", "RUNNING": "#2d7ff9", "PAUSED": "#e0a800",
                "RETRIABLE": "#e07b00", "FINISHED": "#2e9e5b", "FAILED": "#d33", None: "#e07b00"}


def load(path):
    return json.load(open(path)) if path else None


def collect(order, state):
    """Return {sequenceId: node dict} with nodeId, released, pos, actions(list), plus edges list."""
    nodes, edges = {}, []
    if order:
        for n in order.get("nodes", []):
            nodes[n["sequenceId"]] = {"nodeId": n["nodeId"], "released": n.get("released", False),
                                      "pos": n.get("nodePosition"), "actions": n.get("actions", [])}
        for e in order.get("edges", []):
            edges.append({"seq": e["sequenceId"], "released": e.get("released", False), "edgeId": e.get("edgeId", "")})
    if state:
        for n in state.get("nodeStates", []):
            cur = nodes.setdefault(n["sequenceId"], {"nodeId": n["nodeId"], "released": n.get("released", False),
                                                     "pos": None, "actions": []})
            cur["pos"] = cur["pos"] or n.get("nodePosition")
            cur["released"] = n.get("released", cur["released"])
        known = {e["seq"] for e in edges}
        for e in state.get("edgeStates", []):
            if e["sequenceId"] not in known:
                edges.append({"seq": e["sequenceId"], "released": e.get("released", False), "edgeId": e.get("edgeId", "")})
    return nodes, edges


def transform(points):
    xs = [p[0] for p in points] or [0]
    ys = [p[1] for p in points] or [0]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    sx = (W - 2 * PAD) / max(maxx - minx, 1e-6)
    sy = (H - 2 * PAD) / max(maxy - miny, 1e-6)
    s = min(sx, sy)
    ox = PAD + ((W - 2 * PAD) - (maxx - minx) * s) / 2
    oy = PAD + ((H - 2 * PAD) - (maxy - miny) * s) / 2
    return lambda x, y: (ox + (x - minx) * s, H - (oy + (y - miny) * s))  # map y up -> screen y down


def render(order, state, vis, out):
    nodes, edges = collect(order, state)
    robot = None
    for src, key in ((state, "mobileRobotPosition"), (state, "agvPosition"), (vis, "mobileRobotPosition"), (vis, "agvPosition")):
        if src and key in src:
            robot = (src[key], "state" if src is state else "visualization")
            break
    pts = [(n["pos"]["x"], n["pos"]["y"]) for n in nodes.values() if n.get("pos")]
    if robot:
        pts.append((robot[0]["x"], robot[0]["y"]))
    T = transform(pts)
    action_state = {a["actionId"]: a for a in (state or {}).get("actionStates", [])}
    last_seq = (state or {}).get("lastNodeSequenceId")
    svg = []
    for e in sorted(edges, key=lambda e: e["seq"]):
        a, b = nodes.get(e["seq"] - 1), nodes.get(e["seq"] + 1)
        if not (a and b and a.get("pos") and b.get("pos")):
            continue
        (x1, y1), (x2, y2) = T(a["pos"]["x"], a["pos"]["y"]), T(b["pos"]["x"], b["pos"]["y"])
        dash = "" if e["released"] else ' stroke-dasharray="6 5"'
        svg.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{"#333" if e["released"] else "#999"}" stroke-width="2.5"{dash}><title>edge seq {e["seq"]} {html.escape(e["edgeId"])}</title></line>')
    for seq, n in sorted(nodes.items()):
        if not n.get("pos"):
            continue
        x, y = T(n["pos"]["x"], n["pos"]["y"])
        fill = "#333" if n["released"] else "#fff"
        ring = f'<circle cx="{x:.1f}" cy="{y:.1f}" r="15" fill="none" stroke="#e0a800" stroke-width="3"/>' if seq == last_seq else ""
        svg.append(f'{ring}<circle cx="{x:.1f}" cy="{y:.1f}" r="9" fill="{fill}" stroke="#333" stroke-width="2"><title>seq {seq} {html.escape(n["nodeId"])} ({n["pos"]["x"]:.2f}, {n["pos"]["y"]:.2f}) {"base" if n["released"] else "horizon"}</title></circle>')
        svg.append(f'<text x="{x:.1f}" y="{y - 14:.1f}" font-size="11" text-anchor="middle" fill="#333">{seq}</text>')
        for i, a in enumerate(n["actions"]):
            st = action_state.get(a["actionId"], {}).get("actionStatus")
            svg.append(f'<rect x="{x + 12 + i * 12:.1f}" y="{y + 6:.1f}" width="10" height="10" rx="2" fill="{STATUS_COLOR.get(st, STATUS_COLOR[None])}"><title>{html.escape(a["actionType"])} {a.get("blockingType", "")} -> {st or "NOT IN STATE"}</title></rect>')
    if robot:
        p, src = robot
        x, y = T(p["x"], p["y"])
        import math
        th = p.get("theta", 0.0)
        tip = (x + 18 * math.cos(th), y - 18 * math.sin(th))
        svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="#2d7ff9"/><line x1="{x:.1f}" y1="{y:.1f}" x2="{tip[0]:.1f}" y2="{tip[1]:.1f}" stroke="#2d7ff9" stroke-width="3"><title>robot from {src}: ({p["x"]:.2f}, {p["y"]:.2f}, theta {th:.2f}) localized={p.get("localized")}</title></line>')
    findings = []
    if order:
        findings += [f"order: {m}" for m in order_semantics(order)]
    if state:
        findings += [f"state: {m}" for m in state_semantics(state)]
        if order and order.get("orderId") == state.get("orderId") and order.get("orderUpdateId") != state.get("orderUpdateId"):
            findings.append(f"state reflects orderUpdateId {state.get('orderUpdateId')}, order file is {order.get('orderUpdateId')}")
        if order and order.get("orderId") != state.get("orderId"):
            findings.append(f"state orderId {state.get('orderId')} != order orderId {order.get('orderId')}")
        for seq, n in nodes.items():
            for a in n["actions"]:
                if a["actionId"] not in action_state:
                    findings.append(f"action {a['actionType']} on node seq {seq} has no actionState (spec 6.6.9: base and horizon actions shall be reported)")
    if not robot:
        findings.append("no robot position in the given messages")
    s = state or {}
    header = []
    if state:
        header = [("orderId", s.get("orderId")), ("orderUpdateId", s.get("orderUpdateId")),
                  ("lastNode", f'{s.get("lastNodeId")} (seq {s.get("lastNodeSequenceId")})'),
                  ("driving / paused", f'{s.get("driving")} / {s.get("paused")}'), ("operatingMode", s.get("operatingMode")),
                  ("battery", (s.get("powerSupply") or s.get("batteryState") or {}).get("stateOfCharge")),
                  ("errors", ", ".join(f'{e.get("errorType")}({e.get("errorLevel")})' for e in s.get("errors", [])) or "none"),
                  ("nodeStates / edgeStates", f'{len(s.get("nodeStates", []))} / {len(s.get("edgeStates", []))}'),
                  ("timestamp", s.get("timestamp"))]
    acts = "".join(f'<tr><td style="color:{STATUS_COLOR.get(a.get("actionStatus"), "#333")}">{html.escape(str(a.get("actionStatus")))}</td><td>{html.escape(a.get("actionType", ""))}</td><td class="mono">{html.escape(a.get("actionId", ""))}</td><td>{html.escape(str(a.get("actionResult", "")))}</td></tr>'
                   for a in s.get("actionStates", []))
    doc = f"""<!doctype html><meta charset="utf-8"><title>VDA 5050 view</title>
<style>body{{font:14px system-ui,sans-serif;margin:16px;color:#222}}table{{border-collapse:collapse}}td,th{{padding:2px 8px;border-bottom:1px solid #eee;text-align:left;vertical-align:top}}.mono{{font-family:monospace;font-size:12px}}.legend span{{display:inline-block;margin-right:14px}}.f{{color:#b00}}svg{{border:1px solid #ddd;background:#fafafa}}</style>
<h2>VDA 5050 view</h2>
<div class="legend"><span>&#9679; base node</span><span>&#9675; horizon node</span><span>&#9473; released edge</span><span>&#8230; unreleased edge</span><span style="color:#e0a800">&#9711; lastNodeId</span><span style="color:#2d7ff9">&#9679; robot</span><span>&#9632; action badge: grey WAITING, blue RUNNING, green FINISHED, red FAILED, orange no state</span></div>
<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}">{"".join(svg)}</svg>
{"<table>" + "".join(f"<tr><th>{k}</th><td>{html.escape(str(v))}</td></tr>" for k, v in header) + "</table>" if header else ""}
<h3>Findings</h3>{"<ul>" + "".join(f'<li class="f">{html.escape(f)}</li>' for f in findings) + "</ul>" if findings else "<p>none</p>"}
{"<h3>actionStates</h3><table><tr><th>status</th><th>type</th><th>actionId</th><th>result</th></tr>" + acts + "</table>" if acts else ""}
"""
    (open(out, "w") if out else sys.stdout).write(doc)


def main(argv):
    args = dict(zip(argv[1::2], argv[2::2]))
    if not any(k in args for k in ("--order", "--state", "--vis")):
        sys.exit(__doc__)
    render(load(args.get("--order")), load(args.get("--state")), load(args.get("--vis")), args.get("-o"))


if __name__ == "__main__":
    main(sys.argv)
