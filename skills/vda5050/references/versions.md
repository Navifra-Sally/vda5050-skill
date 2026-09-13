# Version differences

Semantic versioning: major = breaking (new required fields, renames), minor = additive. Topic prefix
carries only the major: `.../v2/...` for 2.x, `.../v3/...` for 3.x. The `version` header field carries
the full triple.

## 2.1.0 -> 3.0.0 (verified against both spec texts and schemas)

Wording: "AGV" -> "mobile robot", "master control" -> "fleet control" throughout.

Renamed fields
- state `agvPosition` -> `mobileRobotPosition` (same members: x, y, theta, mapId, mapDescription,
  positionInitialized, localizationScore, deviationRange, plus `localized` in 3.0).
- state `batteryState` -> `powerSupply`.
- state `safetyState.eStop` (AUTOACK|MANUAL|REMOTE|NONE) -> `safetyState.activeEmergencyStop` (MANUAL|REMOTE|NONE).
- connection `CONNECTIONBROKEN` -> `CONNECTION_BROKEN` (underscore added), plus new `HIBERNATING`.
- order and state top-level `zoneSetId` removed; zones now come via the `zoneSet` topic and `enableZoneSet`.
- factsheet `agvGeometry` -> `mobileRobotGeometry`, `vehicleConfig` -> `mobileRobotConfiguration`,
  `protocolFeatures.agvActions` -> `protocolFeatures.mobileRobotActions`.
- order gains optional `orderDescription`.
- `nodePosition.allowedDeviationXY` changes type: 2.x number (radius, m) -> 3.0 object
  `{a, b, theta}` (ellipse semi-major, semi-minor in m, rotation in rad). Sending a number to a 3.0
  robot fails schema validation.

New required in state: `instantActionStates` (instant action states no longer mixed into `actionStates`),
`powerSupply`. Optional new arrays: `zoneActionStates`, `maps`, `zoneSets`, `zoneRequests`,
`edgeRequests`, `plannedPath`, `intermediatePath`.

New topics: `zoneSet` (fleet -> robot, optional), `responses` (fleet -> robot, optional).

Actions
- New blockingType SINGLE (drive allowed, no parallel actions).
- New actionStatus RETRIABLE plus instant actions `retry`, `skipRetry`; order actions gain
  `cancelAllowed`, `pauseAllowed`, `retriable`.
- New predefined actions: trigger, enableMap, downloadMap, deleteMap, downloadZoneSet, enableZoneSet,
  deleteZoneSet, clearInstantActions, clearZoneActions, startHibernation, stopHibernation, shutdown,
  updateCertificate. `waitForTrigger` gains `triggerType` array (FLEET_CONTROL, LOCAL).
- `initializePosition` allowed as a node action (elevator case).

Connection: new value HIBERNATING.

Edges: optional `corridor` (leftWidth, rightWidth, corridorReferencePoint, releaseRequired,
releaseLossBehavior) and `edgeRequests` handshake.

Errors: new predefined types OUTSIDE_OF_CORRIDOR, DUPLICATE_MAP, DUPLICATE_ZONE_SET,
BLOCKED_ZONE_VIOLATION, RELEASE_LOST, ZONE_ACTION_CONFLICT, NODE_UNREACHABLE, LOCALIZATION_ERROR,
UNKNOWN_MAP_ID, INSUFFICIENT_MEMORY, INSTANT_ACTION_STATES_FULL, ZONE_ACTION_STATES_FULL,
MOBILE_ROBOT_NOT_AVAILABLE, ORDER_UPDATE_FOLLOWING_CANCEL. Error objects gain `errorHint` and
translation arrays.

Operating modes: INTERVENED added (HMI steers, order is kept, only cancelOrder allowed);
STARTUP, SERVICE, TEACH_IN semantics tabulated (see state-and-errors.md).

Schemas: the files tagged `3.0.0` in the upstream repo for order, factsheet and visualization are not
valid JSON (trailing commas). Use the `main` branch copies (bundled here from commit 0b2ae43).

## 2.0.0 -> 2.1.0

Additive release. Notable: factsheet became the documented source of protocol limits
(`protocolLimits.timing.minimumStateInterval`), `mapDescription`/`localizationScore` documented on
`agvPosition`, action parameter `value` accepts arrays, and several wording clarifications on order
stitching. Field names of order/state/instantActions are the same in 2.0 and 2.1; a 2.1 fleet control
can generally drive a 2.0 robot. Check the changelog in the spec repo for the exact list.

## Practical version handling

- Detect from the `version` header of the first `state`/`factsheet`; do not trust the topic prefix alone.
- Keep one parser per major version. Mapping 3.0 -> 2.x: `mobileRobotPosition` <-> `agvPosition`,
  `powerSupply` <-> `batteryState`, `activeEmergencyStop` <-> `eStop`, `CONNECTION_BROKEN` <->
  `CONNECTIONBROKEN`, merge `instantActionStates` into `actionStates`, drop SINGLE to HARD (or NONE,
  decide per action), map RETRIABLE to FAILED.
- Robots must reject optional fields they cannot use with UNSUPPORTED_PARAMETER (CRITICAL); so do not
  send 3.0-only fields to a 2.x robot.
