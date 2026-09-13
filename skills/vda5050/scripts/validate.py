#!/usr/bin/env python3
"""Validate a VDA 5050 message against the bundled official JSON schema.

usage: validate.py <topic> <message.json> [--spec 3.0.0|2.1.0]
topic: order | instantActions | state | connection | factsheet | visualization | zoneSet | responses

Spec version is auto-detected from the message "version" header (major 2 -> 2.1.0, 3 -> 3.0.0).
Also runs order-semantic checks the schema cannot express (section 6.1 of the spec).
"""
import json
import pathlib
import sys

try:
    import jsonschema
except ImportError:  # pragma: no cover
    sys.exit("pip install jsonschema")

SCHEMAS = pathlib.Path(__file__).resolve().parent.parent / "references" / "schemas"


def order_semantics(msg):
    nodes, edges = msg.get("nodes", []), msg.get("edges", [])
    errs = []
    if not nodes:
        errs.append("order needs at least one node")
        return errs
    if len(edges) != len(nodes) - 1:
        errs.append(f"edges ({len(edges)}) must equal nodes - 1 ({len(nodes) - 1})")
    seq = sorted([(n["sequenceId"], "node", n) for n in nodes] + [(e["sequenceId"], "edge", e) for e in edges])
    for i, (sid, kind, _) in enumerate(seq):
        if sid != i:
            errs.append(f"sequenceId not continuous: expected {i}, got {sid} ({kind})")
            break
        if (i % 2 == 0) != (kind == "node"):
            errs.append(f"sequenceId {sid} should be a {'node' if i % 2 == 0 else 'edge'}")
            break
    if not nodes[0].get("released", False):
        errs.append("first node (sequenceId 0) must be released")
    released = [x.get("released", False) for _, _, x in seq]
    if any(released[i] and not released[i - 1] for i in range(1, len(released))):
        errs.append("a released node/edge follows an unreleased one (base must be a prefix)")
    by_seq = {x["sequenceId"]: x for _, _, x in seq}
    for e in edges:
        a, b = by_seq.get(e["sequenceId"] - 1), by_seq.get(e["sequenceId"] + 1)
        if e.get("released") and not (a and b and a.get("released") and b.get("released")):
            errs.append(f"edge {e.get('edgeId')} released but its nodes are not")
        if a and b and (e.get("startNodeId") != a.get("nodeId") or e.get("endNodeId") != b.get("nodeId")):
            errs.append(f"edge {e.get('edgeId')} start/end do not match neighbouring nodes")
    ids = [a["actionId"] for x in nodes + edges for a in x.get("actions", [])]
    if len(ids) != len(set(ids)):
        errs.append("duplicate actionId")
    return errs


def main(argv):
    if len(argv) < 3:
        sys.exit(__doc__)
    topic, path = argv[1], argv[2]
    spec = argv[argv.index("--spec") + 1] if "--spec" in argv else None
    msg = json.load(open(path))
    if spec is None:
        major = str(msg.get("version", "")).split(".")[0]
        spec = {"2": "2.1.0", "3": "3.0.0"}.get(major)
        if spec is None:
            sys.exit("cannot detect spec version from message 'version'; pass --spec")
    schema_file = SCHEMAS / spec / f"{topic}.schema.json"
    if not schema_file.exists():
        sys.exit(f"no schema for topic '{topic}' in spec {spec}: {sorted(p.stem.split('.')[0] for p in (SCHEMAS / spec).glob('*.json'))}")
    schema = json.load(open(schema_file))
    problems = [f"schema: {'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
                for e in jsonschema.Draft7Validator(schema).iter_errors(msg)]
    if topic == "order":
        problems += [f"semantic: {m}" for m in order_semantics(msg)]
    for p in problems:
        print(p)
    print(f"{'FAIL' if problems else 'OK'}: {topic} ({spec}) {path}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
