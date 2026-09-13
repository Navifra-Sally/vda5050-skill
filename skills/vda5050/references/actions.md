# Actions (spec 3.0.0, section 6.2)

## Blocking types

|                         | parallel allowed | parallel not allowed |
|-------------------------|------------------|----------------------|
| automatic driving allowed | NONE           | SINGLE (3.0 only)    |
| driving not allowed     | SOFT             | HARD                 |

Queue processing when a node/edge/zone is reached: actions are enqueued in array order. Any SOFT or
HARD in the queue stops driving. NONE/SOFT collect for parallel execution. SINGLE/HARD wait until all
collected parallel actions are FINISHED/FAILED. Driving resumes when no SOFT/HARD remain. Instant
actions always have blockingType NONE. Edge actions run only while the robot is on the edge.

## Action object (order / instantActions)

`actionType`, `actionId` (unique), `actionDescription`*, `blockingType`, `actionParameters[]`*
(`key`, `value` where value is string | number | boolean | array). 3.0 order actions also take
`cancelAllowed`*, `pauseAllowed`*, `retriable`* booleans.

## actionStatus

WAITING (received, node/edge not yet reached) -> INITIALIZING -> RUNNING -> PAUSED (pause action or
HW button) -> RETRIABLE (3.0; failed but `retriable`, waits for `retry`/`skipRetry`) -> FINISHED
(`actionResult` may carry a result) | FAILED. Instant actions may start directly in RUNNING or land
directly in FINISHED/FAILED. Horizon actions are always reported WAITING and are removed from
`actionStates` if the horizon is dropped. Base action states are never removed by an update.

## Predefined actions (3.0)

Every robot must support `cancelOrder`, `startPause`, `stopPause`.
Scope: I = instant, N = node, E = edge, Z = zone. Linked = state field that reflects the effect.

| actionType | scope | parameters | linked state / notes |
|---|---|---|---|
| startPause / stopPause | I | - | `paused`. Pauseable actions pause, others continue. Idempotent. |
| cancelOrder | I | orderId* | see order-lifecycle.md |
| startCharging / stopCharging | I N | - | `powerSupply.charging` (2.x: `batteryState.charging`). Charging spot or lane. Overcharge protection is the robot's job. |
| initializePosition | I N(elevator) | x, y, theta, mapId, lastNodeId | `mobileRobotPosition.*`, `lastNodeId` (2.x: `agvPosition`) |
| stateRequest | I | - | robot publishes a state |
| factsheetRequest | I | - | robot publishes factsheet |
| logReport | I | reason | log name in `actionResult` |
| pick / drop | N E | lhd*, stationType*, stationName*, loadType*, loadId*, height*, depth*, side* | `loads[]`. Not idempotent. Multiple LHDs need `lhd`. |
| detectObject | N E Z | objectType* | - |
| finePositioning | N E Z | stationType*, stationName* | robot may leave node position |
| waitForTrigger | N Z | triggerType [string] (FLEET_CONTROL, LOCAL, custom) | fleet control owns the timeout and cancels if needed |
| trigger | I | - | releases a waitForTrigger (3.0) |
| retry / skipRetry | I | actionId | leaves RETRIABLE (3.0) |
| enableMap / downloadMap / deleteMap | I (enableMap also N) | mapId, mapVersion, mapDownloadLink, mapHash* | `maps[]` with mapStatus ENABLED/DISABLED |
| downloadZoneSet / enableZoneSet / deleteZoneSet | I (enable also N) | zoneSetId, zoneSetDownloadLink, zoneSetHash* | `zoneSets[]` (3.0) |
| clearInstantActions / clearZoneActions | I N | - | prunes FINISHED/FAILED entries (3.0) |
| startHibernation / stopHibernation | I | wakeUpTime* | connection HIBERNATING / ONLINE, order cleared (3.0) |
| shutdown | I | - | needs idle robot, publishes connection OFFLINE (3.0) |
| updateCertificate | I | service, keyDownloadLink, certificateDownloadLink, certificateAuthorityDownloadLink* | (3.0) |

(* optional)

## Expected state transitions for the common ones

- startPause: RUNNING while preparing (may be skipped) -> FINISHED with `paused: true`. FAILED if a HW switch overrides.
- stopPause: mirror, FINISHED with `paused: false`.
- startCharging: RUNNING while talking to the charger -> FINISHED with `charging: true`. FAILED e.g. not aligned. RETRIABLE if waiting for intervention.
- stopCharging: FINISHED with `charging: false`. The robot or the charger may also stop charging on their own (battery full).
- initializePosition: RUNNING during confidence checks -> FINISHED when position fields and `lastNodeId` reflect the parameters. FAILED if pose invalid.
- pick/drop: INITIALIZING (pre-lift) -> RUNNING -> PAUSED (safety field) -> FINISHED with new load state. FAILED e.g. station empty/occupied; RETRIABLE if retriable.
- waitForTrigger: RUNNING until triggered -> FINISHED. FAILED if the order is cancelled.
- cancelOrder: RUNNING while stopping -> FINISHED when idle. FAILED when no active order / wrong orderId / already cancelled.

Unsupported instant action -> INVALID_INSTANT_ACTION (WARNING) with the `actionId` as errorReference.
Instant actions must not conflict with the current order (e.g. lower fork while the order raises it).
Manufacturer-specific actions are allowed when no predefined one fits.
