#!/usr/bin/env python3
"""Render VDA 5050 order / state / visualization messages as a self-contained HTML page or an SVG.

usage: render.py [--order order.json] [--state state.json] [--vis visualization.json] [-o out.html|out.svg]

Nodes at nodePosition (map metres, y up), base solid / horizon dashed with direction arrows,
allowedDeviationXY ellipses, lastNodeId ring, robot position and heading (state, else visualization),
per-node action badges coloured by actionStatus, grid with a scale bar, legend and title inside the SVG.
The HTML adds the state header, validator findings and the actionStates table. No JavaScript.
"""
import html
import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
try:
    from validate import order_semantics, state_semantics
except ImportError:  # pragma: no cover
    order_semantics = state_semantics = lambda m: []

W, H, PAD, TOP = 960, 660, 60, 95
C = {"base": "#1f2937", "horizon": "#9ca3af", "last": "#f59e0b", "robot": "#2563eb", "grid": "#e5e7eb", "dev": "#a7f3d0"}
STATUS = {"WAITING": ("#9ca3af", "W"), "INITIALIZING": ("#818cf8", "I"), "RUNNING": ("#2563eb", "R"), "PAUSED": ("#eab308", "P"),
          "RETRIABLE": ("#f97316", "T"), "FINISHED": ("#16a34a", "F"), "FAILED": ("#dc2626", "X"), None: ("#f97316", "?")}


def load(path):
    return json.load(open(path)) if path else None


def collect(order, state):
    nodes, edges = {}, {}
    if order:
        for n in order.get("nodes", []):
            nodes[n["sequenceId"]] = {"nodeId": n["nodeId"], "released": n.get("released", False),
                                      "pos": n.get("nodePosition"), "actions": n.get("actions", [])}
        for e in order.get("edges", []):
            edges[e["sequenceId"]] = {"released": e.get("released", False), "edgeId": e.get("edgeId", "")}
    if state:
        for n in state.get("nodeStates", []):
            cur = nodes.setdefault(n["sequenceId"], {"nodeId": n["nodeId"], "released": False, "pos": None, "actions": []})
            cur["pos"] = cur["pos"] or n.get("nodePosition")
            cur["released"] = n.get("released", cur["released"])
        for e in state.get("edgeStates", []):
            edges.setdefault(e["sequenceId"], {"released": e.get("released", False), "edgeId": e.get("edgeId", "")})
    return nodes, edges


def robot_pose(state, vis):
    for src, name in ((state, "state"), (vis, "visualization")):
        for key in ("mobileRobotPosition", "agvPosition"):
            if src and key in src:
                return src[key], name
    return None, None


def draw_svg(nodes, edges, robot, state):
    pts = [(n["pos"]["x"], n["pos"]["y"]) for n in nodes.values() if n.get("pos")]
    if robot:
        pts.append((robot[0]["x"], robot[0]["y"]))
    xs, ys = [p[0] for p in pts] or [0, 1], [p[1] for p in pts] or [0, 1]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    s = min((W - 2 * PAD) / max(maxx - minx, 1e-6), (H - TOP - PAD) / max(maxy - miny, 1e-6), 120)
    ox = PAD + ((W - 2 * PAD) - (maxx - minx) * s) / 2
    oy = PAD + ((H - TOP - PAD) - (maxy - miny) * s) / 2
    T = lambda x, y: (ox + (x - minx) * s, H - (oy + (y - miny) * s))
    o = []
    # grid every 1 m (or 5 m when dense) with a scale bar
    step = 1 if s > 25 else 5
    gx = math.floor(minx / step) * step
    while gx <= maxx + step:
        x, _ = T(gx, 0)
        o.append(f'<line x1="{x:.1f}" y1="{TOP}" x2="{x:.1f}" y2="{H - 10}" stroke="{C["grid"]}"/>')
        gx += step
    gy = math.floor(miny / step) * step
    while gy <= maxy + step:
        _, y = T(0, gy)
        o.append(f'<line x1="10" y1="{y:.1f}" x2="{W - 10}" y2="{y:.1f}" stroke="{C["grid"]}"/>')
        gy += step
    o.append(f'<line x1="{W - PAD - step * s:.1f}" y1="{H - 20}" x2="{W - PAD:.1f}" y2="{H - 20}" stroke="#374151" stroke-width="3"/>'
             f'<text x="{W - PAD - step * s / 2:.1f}" y="{H - 26}" font-size="11" text-anchor="middle" fill="#374151">{step} m</text>')
    # deviation ellipses
    for n in nodes.values():
        p = n.get("pos")
        d = (p or {}).get("allowedDeviationXY")
        if not p or not d:
            continue
        a, b, th = (d["a"], d.get("b", d["a"]), d.get("theta", 0.0)) if isinstance(d, dict) else (d, d, 0.0)
        x, y = T(p["x"], p["y"])
        o.append(f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{a * s:.1f}" ry="{b * s:.1f}" transform="rotate({-math.degrees(th):.1f} {x:.1f} {y:.1f})" fill="{C["dev"]}" fill-opacity="0.35" stroke="{C["dev"]}"><title>allowedDeviationXY a={a} b={b}</title></ellipse>')
    # edges with arrows
    for seq, e in sorted(edges.items()):
        a, b = nodes.get(seq - 1), nodes.get(seq + 1)
        if not (a and b and a.get("pos") and b.get("pos")):
            continue
        (x1, y1), (x2, y2) = T(a["pos"]["x"], a["pos"]["y"]), T(b["pos"]["x"], b["pos"]["y"])
        col = C["base"] if e["released"] else C["horizon"]
        dash = "" if e["released"] else ' stroke-dasharray="7 5"'
        o.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{col}" stroke-width="2.5"{dash} marker-end="url(#arr{"B" if e["released"] else "H"})"><title>edge seq {seq} {html.escape(e["edgeId"])} {"released" if e["released"] else "horizon"}</title></line>')
    # nodes, labels, badges
    last_seq = (state or {}).get("lastNodeSequenceId")
    act_state = {a["actionId"]: a for a in (state or {}).get("actionStates", [])}
    for seq, n in sorted(nodes.items()):
        if not n.get("pos"):
            continue
        x, y = T(n["pos"]["x"], n["pos"]["y"])
        if seq == last_seq:
            o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="17" fill="none" stroke="{C["last"]}" stroke-width="3.5"/>')
        fill, stroke = (C["base"], C["base"]) if n["released"] else ("#fff", C["horizon"])
        o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="10" fill="{fill}" stroke="{stroke}" stroke-width="2.5"><title>seq {seq}  {html.escape(n["nodeId"])}\n({n["pos"]["x"]:.3f}, {n["pos"]["y"]:.3f})  {"base" if n["released"] else "horizon"}</title></circle>')
        o.append(f'<text x="{x:.1f}" y="{y - 16:.1f}" font-size="12" font-weight="600" text-anchor="middle" fill="#111">{seq}</text>')
        for i, a in enumerate(n["actions"]):
            st = act_state.get(a["actionId"], {}).get("actionStatus")
            col, letter = STATUS.get(st, STATUS[None])
            bx, by = x + 14 + i * 16, y + 8
            o.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="14" height="14" rx="3" fill="{col}"><title>{html.escape(a["actionType"])} {a.get("blockingType", "")} -> {st or "NOT IN STATE"}</title></rect>'
                     f'<text x="{bx + 7:.1f}" y="{by + 11:.1f}" font-size="10" font-weight="700" text-anchor="middle" fill="#fff" pointer-events="none">{letter}</text>')
    if robot:
        p, src = robot
        x, y = T(p["x"], p["y"])
        th = p.get("theta", 0.0)
        pts_ = [(x + 26 * math.cos(th), y - 26 * math.sin(th)), (x + 9 * math.cos(th + 2.3), y - 9 * math.sin(th + 2.3)), (x + 9 * math.cos(th - 2.3), y - 9 * math.sin(th - 2.3))]
        o.append(f'<polygon points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in pts_)}" fill="{C["robot"]}" stroke="#fff" stroke-width="1.5"><title>robot ({src}) ({p["x"]:.3f}, {p["y"]:.3f}) theta {th:.2f} localized={p.get("localized")}</title></polygon>')
    s_ = state or {}
    title = f'orderId {s_.get("orderId", "-")}  update {s_.get("orderUpdateId", "-")}  lastNode seq {s_.get("lastNodeSequenceId", "-")}  driving {s_.get("driving", "-")}  mode {s_.get("operatingMode", "-")}' if state else "order"
    legend = (f'<g font-size="12" fill="#374151" transform="translate(14,40)">'
              f'<circle cx="6" cy="0" r="6" fill="{C["base"]}"/><text x="16" y="4">base node</text>'
              f'<circle cx="96" cy="0" r="6" fill="#fff" stroke="{C["horizon"]}" stroke-width="2"/><text x="106" y="4">horizon node</text>'
              f'<line x1="200" y1="0" x2="230" y2="0" stroke="{C["base"]}" stroke-width="2.5"/><text x="236" y="4">released edge</text>'
              f'<line x1="330" y1="0" x2="360" y2="0" stroke="{C["horizon"]}" stroke-width="2.5" stroke-dasharray="7 5"/><text x="366" y="4">unreleased edge</text>'
              f'<circle cx="480" cy="0" r="7" fill="none" stroke="{C["last"]}" stroke-width="3"/><text x="492" y="4">lastNodeId</text>'
              f'<polygon points="570,-6 584,0 570,6" fill="{C["robot"]}"/><text x="588" y="4">robot</text>'
              f'<ellipse cx="640" cy="0" rx="9" ry="6" fill="{C["dev"]}" stroke="{C["dev"]}"/><text x="652" y="4">allowedDeviationXY</text>'
              f'<rect x="782" y="-7" width="14" height="14" rx="3" fill="{STATUS["FINISHED"][0]}"/><text x="800" y="4">action (letter = status)</text></g>')
    defs = ''.join(f'<marker id="arr{k}" viewBox="0 0 10 10" refX="13" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>'
                   for k, c in (("B", C["base"]), ("H", C["horizon"])))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="system-ui,sans-serif">'
            f'<defs>{defs}</defs><rect width="{W}" height="{H}" fill="#fafafa" stroke="#d1d5db"/>'
            f'<text x="14" y="22" font-size="14" font-weight="600" fill="#111">VDA 5050 view  |  {html.escape(title)}</text>{legend}{"".join(o)}</svg>')


def findings_for(order, state, nodes, robot):
    f = []
    if order:
        f += [f"order: {m}" for m in order_semantics(order)]
    if state:
        f += [f"state: {m}" for m in state_semantics(state)]
        if order and order.get("orderId") != state.get("orderId"):
            f.append(f"state orderId {state.get('orderId')} != order orderId {order.get('orderId')}")
        elif order and order.get("orderUpdateId") != state.get("orderUpdateId"):
            f.append(f"state reflects orderUpdateId {state.get('orderUpdateId')}, order file is {order.get('orderUpdateId')}")
        act = {a["actionId"] for a in state.get("actionStates", [])}
        for seq, n in nodes.items():
            for a in n["actions"]:
                if a["actionId"] not in act:
                    f.append(f"action {a['actionType']} on node seq {seq} has no actionState (spec 6.6.9: base and horizon actions shall be reported)")
    if not robot:
        f.append("no robot position in the given messages")
    return f


def render(order, state, vis, out):
    nodes, edges = collect(order, state)
    pose, src = robot_pose(state, vis)
    robot = (pose, src) if pose else None
    svg = draw_svg(nodes, edges, robot, state)
    if out and out.endswith(".svg"):
        open(out, "w").write(svg)
        return
    findings = findings_for(order, state, nodes, robot)
    s = state or {}
    header = [("orderId", s.get("orderId")), ("orderUpdateId", s.get("orderUpdateId")),
              ("lastNode", f'{s.get("lastNodeId")} (seq {s.get("lastNodeSequenceId")})'),
              ("driving / paused", f'{s.get("driving")} / {s.get("paused")}'), ("operatingMode", s.get("operatingMode")),
              ("battery", (s.get("powerSupply") or s.get("batteryState") or {}).get("stateOfCharge")),
              ("errors", ", ".join(f'{e.get("errorType")}({e.get("errorLevel")})' for e in s.get("errors", [])) or "none"),
              ("nodeStates / edgeStates", f'{len(s.get("nodeStates", []))} / {len(s.get("edgeStates", []))}'),
              ("robot position from", robot[1] if robot else "none"), ("timestamp", s.get("timestamp"))] if state else []
    acts = "".join(f'<tr><td style="color:{STATUS.get(a.get("actionStatus"), STATUS[None])[0]}">{html.escape(str(a.get("actionStatus")))}</td><td>{html.escape(a.get("actionType", ""))}</td><td class="mono">{html.escape(a.get("actionId", ""))}</td><td>{html.escape(str(a.get("actionResult", "")))}</td></tr>'
                   for a in s.get("actionStates", []))
    doc = f"""<!doctype html><meta charset="utf-8"><title>VDA 5050 view</title>
<style>body{{font:14px system-ui,sans-serif;margin:16px;color:#222}}table{{border-collapse:collapse}}td,th{{padding:2px 8px;border-bottom:1px solid #eee;text-align:left;vertical-align:top}}.mono{{font-family:monospace;font-size:12px}}.f{{color:#b00}}</style>
{svg}
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
