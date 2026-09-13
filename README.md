# vda5050 skill for Claude Code

A Claude Code plugin that gives Claude an accurate, citable VDA 5050 reference while you build or debug
fleet-control / AMR integrations.

- Topic layout, header, QoS and retain rules
- Order semantics: base/horizon, stitching, acceptance decision tree, rejection error types, cancel
- State semantics: traversal, idle, operating modes, error levels, request/response
- Predefined actions, blocking types, action state machine
- 2.1 vs 3.0 differences and renames
- Official JSON schemas (2.1.0 and 3.0.0) and `scripts/validate.py` for schema + order-semantic checks

## Install

```
/plugin marketplace add Navifra-Sally/vda5050-skill
/plugin install vda5050@vda5050-skill
```

Or try it locally: `claude --plugin-dir ./vda5050-skill`.

## Validate a message

```
python3 skills/vda5050/scripts/validate.py order  my_order.json
python3 skills/vda5050/scripts/validate.py state  my_state.json --spec 2.1.0
```

## Licensing

Skill text and script: MIT (see LICENSE). JSON schemas under `skills/vda5050/references/schemas/` are
copyright Verband der Automobilindustrie, MIT (see `LICENSE-VDA5050.txt` there), taken from
https://github.com/VDA5050/VDA5050. The 3.0.0 set is from `main` at commit 0b2ae43 because the files
tagged 3.0.0 contain invalid JSON.
