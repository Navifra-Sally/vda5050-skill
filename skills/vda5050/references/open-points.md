# What the spec leaves open

VDA 5050 fixes message shapes and a few hard rules ("shall"). Many operational decisions are handed to
the integrator ("can", "should", "defined during integration"). Most field incidents happen here, not
in the mandatory parts. For each point: what the spec says, the choices, and what each choice costs.
When a user asks about one of these, say that it is an integration decision and lay out the options
instead of presenting one as "the spec".

## 1. First node of the order after a cancel (6.1.3.1)

Spec: robot must accept both (a) a temporary node at its current position, and (b) the last traversed
node with an `allowedDeviationXY` large enough to contain the robot. Fleet control chooses.
- (a) keeps the graph clean but needs a fresh `nodeId` and position from the robot's last `state`. If
  the robot moved after that state, START_NODE_OUT_OF_RANGE.
- (b) reuses a real node but the robot then "traverses" it immediately, so any actions on it run again.
- Robots that localize only on nodes support only (b) with the node they stand on.
- Either way the `orderId` must be new. Reusing the cancelled id gives ORDER_UPDATE_FOLLOWING_CANCEL.

## 2. When a node counts as traversed (6.6.2)

Spec: "the mobile robot decides on its own", constrained only by `allowedDeviationXY` / `Theta`.
- Some robots report traversal on entering the deviation ellipse, some only after stopping, some on
  passing the node centre. A fleet that completes its own bookkeeping from the robot pose will disagree
  with the robot by one node in either direction.
- Safe rule: treat `lastNodeId` / `lastNodeSequenceId` from `state` as the only truth for progress and
  occupancy release. Never mark a node reached from pose alone.

## 3. Deviation ranges

Spec: `allowedDeviationXY` is an ellipse, `allowedDeviationTheta` optional, zero means "as exact as the
robot can". No default value is given.
- Too small: robots stall next to nodes without reporting traversal. Too large: robots cut corners into
  areas fleet control believes are free.
- Line-guided robots ignore XY for the trajectory but still use it as the traversal trigger.

## 4. Lost messages on QoS 0 (4.1, 6.1.4.5)

Spec: resend is allowed; a duplicate with identical content is silently ignored, a duplicate with
different content gives SAME_ORDER_UPDATE_ID. Nothing about when or how often to resend.
- Decide the acknowledgement signal: a `state` whose `orderUpdateId` equals the one sent (preferred), or
  a `state` with matching `headerId` reference in errors.
- Decide the retry interval (typically a few seconds) and a give-up limit that raises an operator
  alarm instead of resending forever.
- "Identical content" is not defined down to `headerId` / `timestamp`. Assume robots compare the body
  (orderId, orderUpdateId, nodes, edges) and expect some to reject on any byte difference.

## 5. Base extension timing and horizon length (6.1.2)

Spec: extend the base before the robot reaches the decision point; horizon may be any length or absent.
- Short base: safe traffic control, more messages, robots brake at every decision point when the
  network is slow. Use `newBaseRequest` from the robot as an early signal.
- Long horizon: robots can pre-plan (pre-lift, path smoothing) but everything in the horizon appears in
  `nodeStates` / `actionStates` as WAITING, and dropping it later must be handled.

## 6. Request / response timeouts (6.9), waitForTrigger timeout (6.2.3.1)

Spec: no response within "the time frame required by the application" means not granted; fleet
control is responsible for the waitForTrigger timeout and "shall cancel the order if necessary".
- Both numbers are yours. Define them, log them, and decide the outcome: cancel the order, report an
  error to the operator, or keep waiting.
- A robot waiting in `waitForTrigger` occupies its node. Long timeouts block traffic.

## 7. Liveness of a robot (6.5, 6.6)

Spec: `connection` is an MQTT-level signal and "not to be used for checking the mobile robot health";
`state` arrives at least every 30 s.
- Use `state` age with a threshold above the robot's actual period (30 s default, or the factsheet
  `minimumStateInterval` plus margin).
- A retained ONLINE on `connection` can be stale after a broker restart or a robot that died without
  the last will firing. Treat ONLINE as "was online at some point", CONNECTION_BROKEN as reliable.

## 8. Position source (6.6, 6.7)

Spec: position is `mobileRobotPosition` (2.x `agvPosition`) in `state`; `visualization` is an optional
high-rate copy "for visualization systems".
- Some robots publish position only on `visualization` and leave it out of `state`. Decide whether
  fleet control subscribes to `visualization` as a fallback, and what happens when the two disagree.
- Recommended: `state` is authoritative for logic; `visualization` is for UI only. If a robot cannot
  provide position in `state`, treat that as a robot-side gap, not something to patch around.

## 9. Instant actions while an order runs (6.2.1)

Spec: instant actions "shall not conflict with the content of the current order". What counts as a
conflict is not enumerated.
- Typical conflicts: `initializePosition` mid-order, `startCharging` while driving, a manufacturer action
  that moves the load handling device. Decide which instant actions fleet control may send while
  `driving` is true or `actionStates` has RUNNING entries.

## 10. Pause semantics vs cancel

Spec: `startPause` / `stopPause` keep the order and are mandatory; `cancelOrder` clears it. Both are
instant actions.
- A pause holds the robot in place with its occupancy. A cancel frees the robot for re-planning but
  costs a new order and a first-node decision (point 1).
- Hardware pause buttons also toggle `paused`; fleet control must handle `paused: true` that it did
  not request.

## 11. Rejection error lifetime (6.1.4)

Spec: rejection warnings are reported "until a new order is accepted".
- Robots differ: some clear on any accepted order, some on an accepted order with a new `orderId`,
  some on the next state message. Do not gate re-dispatch on the error disappearing; gate on the
  `state` reflecting your `orderId` / `orderUpdateId`.

## 12. Action parameters and manufacturer actions (6.2.3)

Spec: predefined parameters are optional, extra parameters allowed, manufacturer actions allowed.
- Read the factsheet `protocolFeatures.mobileRobotActions` (2.x: `protocolFeatures.agvActions`) for
  what the robot actually supports and which `blockingTypes` it accepts per action. Sending an unsupported one yields INVALID_ORDER_ACTION or
  INVALID_INSTANT_ACTION.
- Parameter `value` may be string, number, boolean or array. Robots are strict about the type.

## 13. Node and edge identity across order updates

Spec: the same `nodeId` may appear multiple times in one order; `sequenceId` is the unique key.
- Key every lookup on `sequenceId`, not `nodeId`. Loops (visit A, then B, then A) are legal and break
  `nodeId`-keyed maps.

## 14. Maps and mapId (6.3, 6.1.4.10)

Spec: `mapId` is unique per level; unknown `mapId` in an order gives UNKNOWN_MAP_ID; map switching is
done by the robot (`initializePosition` with a new `mapId`, 3.0 `enableMap`).
- Multi-floor: decide whether an order may span two `mapId`s (the spec allows nodes with different
  `mapId`, robots often do not) or whether every floor change is a separate order after a position
  initialization.

## 15. Operating mode transitions

Spec: MANUAL / SERVICE / TEACH_IN clear the order; INTERVENED keeps it; STARTUP state may be invalid.
- Decide what fleet control does with jobs when a robot leaves AUTOMATIC: hold, re-dispatch, or
  cancel. Decide how long a robot may stay in STARTUP before it is considered failed.
- `lastNodeId` may come back as `""` after these modes. A robot with empty `lastNodeId` needs an
  `initializePosition` or a first node by position before it can take an order.
