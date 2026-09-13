---
name: vda5050
description: VDA 5050 reference (mobile robot / AGV / AMR <-> fleet control MQTT interface). Use for ANY question or task that mentions VDA5050 / VDA 5050, even a simple field-name or enum lookup, because version 3.0 (2026) renamed many fields and answers from memory are usually the old 2.x names. Covers order, instantActions, state, connection, factsheet, visualization, zoneSet and responses messages; MQTT topic layout; order updates and stitching; cancelOrder; action blocking types and action states; error types; operating modes; spec version differences 2.0 / 2.1 / 3.0; and validating a VDA5050 JSON message against the official schema.
---

# VDA 5050

Facts below are taken from the official spec (github.com/VDA5050/VDA5050). When a detail is not
here, open the matching file in `references/` before answering. Do not guess field names or enums.

## Versions and topics

- Spec versions: 2.0.0 (2021), 2.1.0 (2024-08), 3.0.0 (2026-03). Most deployed robots speak 2.x.
  Ask which version the target uses if unclear; field names differ (see `references/versions.md`).
  Key 3.0 renames: state `agvPosition` -> `mobileRobotPosition`, `batteryState` -> `powerSupply`,
  `safetyState.eStop` -> `activeEmergencyStop`, connection `CONNECTIONBROKEN` -> `CONNECTION_BROKEN`.
  New in 3.0: blockingType SINGLE, actionStatus RETRIABLE, connection HIBERNATING, topics `responses`
  and `zoneSet`; `allowedDeviationXY` is an ellipse object `{a, b, theta}`, not a number.
  Do not answer 3.0 questions with 2.x names.
- Topic layout: `interfaceName/majorVersion/manufacturer/serialNumber/topic`,
  e.g. `uagv/v2/KIT/0001/order` or `vda5050/v3/KIT/0001/state`. No `/`, `+`, `#`, `$` in any level.
- Topics (3.0): fleet -> robot: `order`, `instantActions`, `zoneSet`*, `responses`*.
  robot -> fleet: `state`, `connection`, `factsheet`, `visualization`*. (* optional)
- QoS 0 for everything except `connection` (QoS 1). `connection` and `factsheet` are retained.
- Every message starts with the same header: `headerId` (uint32, per topic, +1 per sent message),
  `timestamp` (ISO 8601 UTC with ms: `2017-04-15T11:40:03.123Z`), `version` (`3.0.0`),
  `manufacturer`, `serialNumber`.

## Order rules that break integrations

- `sequenceId`: first node 0, first edge 1, next node 2, ... Continuous. Edge n joins nodes n-1 and n+1.
  Nodes count = edges count + 1. At least one node.
- First node (`sequenceId` 0) must be trivially reachable (robot on it or inside `allowedDeviationXY`)
  and released. It is never reported in `nodeStates`.
- Base = released nodes/edges. Horizon = unreleased. An edge can be released only if both its nodes are.
  Nothing released may follow an unreleased edge. Base can never be changed once sent.
- Order update: same `orderId`, `orderUpdateId` + 1, first node = last base node of previous update
  (the stitching / decision point), resent with identical content. Horizon may change freely.
  To run new actions on the node the robot already stands on: resend that node unchanged, then add a
  new node at the same position with `sequenceId` = decision node + 2 carrying the new actions.
- New order: different `orderId`, `orderUpdateId` 0, only accepted when the robot is idle
  (`nodeStates` and `edgeStates` empty, all `actionStates` FINISHED or FAILED).
- Rejections are reported as `errors[]` entries with level WARNING (mostly) until the next accepted
  order: VALIDATION_FAILURE, OUTDATED_ORDER_UPDATE, SAME_ORDER_UPDATE_ID, OTHER_ORDER_ACTIVE,
  START_NODE_OUT_OF_RANGE, NO_ROUTE_TO_TARGET, ORDER_UPDATE_FOLLOWING_CANCEL, ... Full acceptance
  decision tree and rejection table: `references/order-lifecycle.md`.
- `cancelOrder` (instant action): robot stops ASAP, WAITING actions -> FAILED, running cancellable
  actions -> FAILED, action stays RUNNING until movement and actions stop, then FINISHED. `orderId`,
  `orderUpdateId`, `lastNodeId` are kept, `nodeStates`/`edgeStates` emptied. No further updates to a
  cancelled orderId. cancelOrder while idle or with a wrong orderId -> FAILED + NO_ORDER_TO_CANCEL.

## State rules

- Single `state` topic. Publish on every relevant change and at least every 30 s. Minimum interval
  comes from factsheet `protocolLimits.timing.minimumStateInterval`.
- Node traversed = robot removes its `nodeState`, sets `lastNodeId`/`lastNodeSequenceId`, triggers the
  node's actions, leaves the previous edge, enters the next edge (unless a SOFT/HARD action stops it).
- `lastNodeId` only changes for released nodes of the active order. It becomes `""` when the robot
  enters SERVICE or TEACH_IN, or MANUAL when the order cannot be continued.
- Idle definition, operating-mode table, clearing rules, error levels (WARNING/URGENT/CRITICAL/FATAL),
  predefined `errorType` values and the request/response mechanism: `references/state-and-errors.md`.
- Fleet control must read robot position from `state`, not from `visualization`. `visualization` is a
  high-rate optional copy for UIs; a robot may send it without ever putting a position in `state`.

## Actions

- `blockingType`: NONE (drive + parallel), SOFT (no drive, parallel), SINGLE (drive, no parallel; 3.0
  only), HARD (no drive, no parallel). Instant actions are always NONE.
- `actionStatus`: WAITING -> INITIALIZING -> RUNNING -> (PAUSED | RETRIABLE) -> FINISHED | FAILED.
  RETRIABLE is 3.0 only. Horizon actions are reported as WAITING.
- Every robot must support `cancelOrder`, `startPause`, `stopPause`. Charging is `startCharging` /
  `stopCharging` (instant or node action). Position reset is `initializePosition`.
- Full predefined action table with parameters, scope (instant/node/edge/zone) and expected state
  transitions: `references/actions.md`.

## Connection

- On connect: set last will on `.../connection` = `CONNECTION_BROKEN` (retained), then publish
  `ONLINE` (retained). Graceful exit: publish `OFFLINE`, then disconnect. 3.0 adds `HIBERNATING`.
  2.x spells the last-will value `CONNECTIONBROKEN` (no underscore).
- Fleet control must not use `connection` as a health check; it is an MQTT-level signal. Use `state`
  age for liveness. A retained `ONLINE` can be stale after a broker restart.

## Integration pitfalls (learned the hard way)

- QoS 0 means orders can be lost. Resend when no `state` with the expected `orderUpdateId` arrives.
  A robot that already has that update ignores an identical resend (no error).
- Never let fleet control fabricate robot-side messages (state, action results). If the robot rejects,
  treat it as rejected; do not "self-heal" by pretending success.
- After a mid-edge cancel, the next order's first node must be either a temporary node at the robot's
  current position or the last traversed node with a wide `allowedDeviationXY`. Sending the next graph
  node causes START_NODE_OUT_OF_RANGE.
- `orderId` must be new after cancel. Reusing the cancelled id with a higher `orderUpdateId` yields
  ORDER_UPDATE_FOLLOWING_CANCEL.
- Track `headerId` gaps per topic to detect dropped messages; do not treat them as errors.
- Do not infer progress from your own order; use `lastNodeId`/`lastNodeSequenceId` and the shrinking
  `nodeStates`/`edgeStates`. Order tail reached = `lastNodeSequenceId` equals the last released node.
- `instantActionStates` grow until fleet control sends `clearInstantActions` (3.0). Clear regularly.

## Validate a message

```bash
python3 scripts/validate.py order  my_order.json          # version auto-detected from "version"
python3 scripts/validate.py state  my_state.json --spec 2.1.0
```

Checks JSON Schema (bundled, `references/schemas/<version>/`) plus semantics the schema cannot
express. Order: sequenceId continuity, node/edge counts, release ordering, first node released.
State: duplicate or out-of-order sequenceIds, released prefix, position missing while driving
(warning). Needs `pip install jsonschema`.

## Draw an order / state

```bash
python3 scripts/render.py --order o.json --state s.json --vis v.json -o view.html
```

Self-contained HTML with inline SVG: nodes at `nodePosition`, base solid / horizon dashed, `lastNodeId`
ring, robot position, per-node action badges coloured by `actionStatus`, state header and validator
findings. Use it whenever the user wants to "see" an order, a state, or why a robot stopped; open the
result or describe what it shows. Any subset of the three inputs works.

Note: the schemas tagged `3.0.0` upstream contain invalid JSON (trailing commas in order, factsheet,
visualization). The bundled 3.0.0 set is taken from upstream `main` at commit 0b2ae43, which parses.

## References

- `references/order-lifecycle.md` - acceptance decision tree, rejections, cancel, finishing
- `references/actions.md` - predefined actions, blocking types, action states
- `references/state-and-errors.md` - state triggers, traversal, idle, operating modes, errors, requests
- `references/versions.md` - 2.0 / 2.1 / 3.0 differences and renames
- `references/open-points.md` - decisions the spec leaves to the integrator, with options and costs.
  Open this whenever a question is about "how should we handle ..." rather than "what does the spec say"
- `references/examples/` - captured, anonymized 3.0 state and visualization messages with notes on
  what to look at, message sizes and publish rates for capacity planning
- `references/schemas/` - official JSON schemas (MIT, VDA), 2.1.0 and 3.0.0
- Spec text: https://github.com/VDA5050/VDA5050/blob/main/VDA5050_EN.md
