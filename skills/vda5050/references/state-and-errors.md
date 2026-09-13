# State, operating modes, errors, requests (spec 3.0.0, sections 6.5, 6.6, 6.9)

## Connection topic

- Retained, QoS 1. Values 3.0: ONLINE, OFFLINE, CONNECTION_BROKEN, HIBERNATING.
  Values 2.x: ONLINE, OFFLINE, CONNECTIONBROKEN (no underscore).
- Connect: set last will `CONNECTION_BROKEN` on `.../connection`, then publish `ONLINE`.
- Graceful disconnect: publish `OFFLINE`, then MQTT disconnect.
- The last-will message has stale `headerId`/`timestamp` by nature.
- Not a health check for fleet control; it is an MQTT-level signal only.

## State publish triggers

Publish on any of: order or update received; change in `load`, `errors`, `operatingMode`, `driving`,
`paused`, `safetyState`, `newBaseRequest`, `lastNodeId`/`lastNodeSequenceId`, `edgeRequests`/
`zoneRequests`, `powerSupply.charging`, `nodeStates`/`edgeStates`, `actionStates`/
`instantActionStates`/`zoneActionStates`, `zoneSets`, `maps`. Otherwise at least every 30 s.
Coalesce correlated events into one message. Respect factsheet `minimumStateInterval`.

Required top-level fields (3.0 schema): header, `orderId`, `orderUpdateId`, `lastNodeId`,
`lastNodeSequenceId`, `nodeStates`, `edgeStates`, `driving`, `actionStates`, `instantActionStates`,
`powerSupply`, `operatingMode`, `errors`, `safetyState`. 2.1 has `batteryState` instead of
`powerSupply` and no `instantActionStates` (instant action states live in `actionStates`).

## Traversal

- Robot decides when a node counts as traversed: control point inside `allowedDeviationXY` (an ellipse
  around the node) and heading inside `allowedDeviationTheta`.
- On traversal: remove the `nodeState`, set `lastNodeId`/`lastNodeSequenceId`, start node actions,
  remove the incoming edge from `edgeStates` and finish its actions, enter the next edge and start its
  actions (unless a SOFT/HARD action holds the robot on the node).
- `lastNodeId` changes only for released nodes of the active order. A physical marker outside the order
  must not update it.
- `nodeStates`/`edgeStates` list all upcoming nodes and edges (base + horizon). The first node of an
  order is never listed.
- Freely navigating robots publish `plannedPath` (NURBS, covers at least the base) and
  `intermediatePath` (polyline with ETA per waypoint, restarts at the current position every message).

## Idle

`nodeStates` and `edgeStates` empty and every entry of `actionStates` FINISHED or FAILED.
New orders are accepted only when idle. Updates are accepted when idle or executing. Instant actions
are accepted when idle.

## Operating modes

| mode | fleet in control | orders allowed | instant actions allowed | clears order on entry | sets lastNodeId "" |
|---|---|---|---|---|---|
| AUTOMATIC | yes | yes | yes | no | no |
| SEMIAUTOMATIC (speed by HMI) | yes | yes | yes | no | no |
| INTERVENED (HMI steers, order kept for later) | no | yes | cancelOrder only | no | no |
| MANUAL | no | no | no | yes | if the order cannot be continued |
| STARTUP (state may be invalid) | no | no | no | yes | yes |
| SERVICE | no | no | no | yes | yes |
| TEACH_IN | no | no | no | yes | yes |

Robot must not switch to MANUAL/SERVICE/TEACH_IN while order actions are still running; it empties
`nodeStates`/`edgeStates` only after reporting the new mode. Orders received in a non-order mode ->
MOBILE_ROBOT_NOT_AVAILABLE (WARNING) until the mode allows orders again.

## Clearing the order (MANUAL/STARTUP/SERVICE/TEACH_IN entry, cancelOrder, startHibernation)

Scheduled actions -> FAILED; running cancellable -> FAILED; non-cancellable finish normally.
`orderId`, `orderUpdateId`, `lastNodeId`, `lastNodeSequenceId` unchanged. `nodeStates`/`edgeStates`
emptied. All requests removed. Only fleet control can trigger a cancellation.

## Error levels

- WARNING: no action needed, order continues, new orders accepted.
- URGENT: needs attention soon, order continues, new orders accepted.
- CRITICAL: robot stops, cannot continue this order, can accept a new one.
- FATAL: user intervention, no continue, no new orders.
Errors never clear the order by themselves. `errorReferences[]` carries `referenceKey`/`referenceValue`
pairs (headerId, topic, orderId, orderUpdateId, actionId, parameter names). `errorDescription`,
`errorHint` plus `...Translations` (ISO 639-1) are human-readable.

## Predefined errorType values

| errorType | level | reported until |
|---|---|---|
| VALIDATION_FAILURE | WARNING | next accepted order |
| UNSUPPORTED_PARAMETER | CRITICAL | next accepted order |
| INVALID_ORDER_ACTION | WARNING | next accepted order |
| INVALID_INSTANT_ACTION | WARNING | next accepted instant action |
| OUTDATED_ORDER_UPDATE | WARNING | next accepted order |
| SAME_ORDER_UPDATE_ID | WARNING | next accepted order |
| ORDER_UPDATE_FOLLOWING_CANCEL | WARNING | next accepted order |
| OTHER_ORDER_ACTIVE | WARNING | next accepted order |
| START_NODE_OUT_OF_RANGE | WARNING | next accepted order |
| NO_ROUTE_TO_TARGET | WARNING | next accepted order |
| NO_ORDER_TO_CANCEL | WARNING | next accepted order |
| MOBILE_ROBOT_NOT_AVAILABLE | WARNING | operating mode allows orders |
| UNKNOWN_MAP_ID | WARNING | next accepted order |
| INSUFFICIENT_MEMORY | URGENT | next accepted order |
| NODE_UNREACHABLE | CRITICAL | next accepted order |
| OUTSIDE_OF_CORRIDOR | CRITICAL | back inside corridor |
| BLOCKED_ZONE_VIOLATION | CRITICAL | outside the zone |
| RELEASE_LOST | CRITICAL | outside zone or re-granted |
| ZONE_ACTION_CONFLICT | CRITICAL | conflict resolved |
| LOCALIZATION_ERROR | FATAL | localized again (`localized: false`, no driving) |
| DUPLICATE_MAP / DUPLICATE_ZONE_SET | WARNING | next map/zone action |
| INSTANT_ACTION_STATES_FULL / ZONE_ACTION_STATES_FULL | URGENT | list cleared |

The enum is extensible; vendor types are allowed.

## Request / response (3.0)

Robot puts a request object in state (`zoneRequests[]` for ACCESS / REPLANNING zones,
`edgeRequests[]` for CORRIDOR) with a per-robot unique `requestId` and `requestStatus` REQUESTED.
Fleet control answers on `responses` with `grantType` GRANTED | QUEUED | REJECTED | REVOKED and an
optional `leaseExpiry` (only with GRANTED; can be extended by resending). Robot status moves to
GRANTED / REVOKED / EXPIRED. No answer within the integration-defined timeout = not granted.
On REVOKED/expiry inside the resource the robot runs the resource's `releaseLossBehavior`
(STOP -> RELEASE_LOST error, CONTINUE, EVACUATE). Requests are removed from state once the operation
completed, aborted or was rejected. INTERVENED mode drops all zone requests.

## safetyState

- 3.0: `activeEmergencyStop`: MANUAL (acknowledge on the robot) | REMOTE (acknowledge remotely) | NONE.
  `fieldViolation`: boolean.
- 2.x: `eStop`: AUTOACK | MANUAL | REMOTE | NONE. `fieldViolation`: boolean.
