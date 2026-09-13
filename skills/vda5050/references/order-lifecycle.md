# Order lifecycle (spec 3.0.0, section 6.1; identical logic in 2.x)

## Accepting an order or order update (Figure 8 of the spec)

1. Valid JSON and types? No -> VALIDATION_FAILURE.
2. `orderId` different from the order the robot holds? Yes -> new order path (3-5). No -> update path (6-10).
3. New order: robot idle and not waiting for an update (no horizon)? No -> OTHER_ORDER_ACTIVE.
4. New order: `orderUpdateId` == 0? No -> reject (VALIDATION_FAILURE in practice).
5. New order: first node within reach (on node or inside `allowedDeviationXY`)? No -> START_NODE_OUT_OF_RANGE.
6. Update: `orderUpdateId` lower than current? -> OUTDATED_ORDER_UPDATE, keep executing old order.
7. Update: order was cancelled? -> ORDER_UPDATE_FOLLOWING_CANCEL.
8. Update: `orderUpdateId` equal to current? Same content -> ignore silently. Different content -> SAME_ORDER_UPDATE_ID.
9. Update while still executing or holding a horizon: first node of the update must equal the last base node of the previous update (same `nodeId` and `sequenceId`). Otherwise reject.
10. Update after the previous base completed (idle, no horizon): same stitching rule as 9.
11. Accept: append new `nodeStates`, `edgeStates`, `actionStates`; publish state.

Additional rejections: UNSUPPORTED_PARAMETER (CRITICAL, robot cannot use an optional field),
INVALID_ORDER_ACTION (action it cannot perform), NO_ROUTE_TO_TARGET, MOBILE_ROBOT_NOT_AVAILABLE
(operating mode does not allow orders), UNKNOWN_MAP_ID, INSUFFICIENT_MEMORY (URGENT).
All are reported in `errors[]` until the next order is accepted (or until the mode allows orders).

## Base / horizon

- Base: released nodes and edges. Last base node = decision point. Robot stops there if no extension arrives.
- Horizon: unreleased nodes and edges. Fleet control may rewrite or drop the horizon in any update.
- Base is immutable. Fleet control shall assume the base has already been executed.
- Extend the base before the robot reaches the decision point to keep it moving. Robot may set
  `newBaseRequest: true` in state when its base runs short.
- Once a node is released its `sequenceId` never changes.
- `sequenceId` starts at 0 only for a new order (`orderUpdateId` 0). An order update starts at the
  stitching node's existing `sequenceId` (e.g. 88) and continues from there.

## Stitching example

Order (`orderUpdateId` 0): nodes f d g (released) b h (horizon), edges e1 e3 (released) e8 e9 (horizon).
Update (`orderUpdateId` 1): nodes g b h (released) i (horizon), edges e8 e9 (released) e10 (horizon).
Only g, the previous decision point, is resent from the old base. Its content (actions, deviation)
must be identical.

To release new actions on the node the robot is standing on: resend the decision node unchanged
(its actions may already be FINISHED), then append a node with the same position (same or different
`nodeId`) with `sequenceId` = decision `sequenceId` + 2 carrying the new actions, joined by an edge with
`sequenceId` + 1.

## Finishing

After the last released node is traversed and all order actions are FINISHED/FAILED the robot is idle
and accepts a new order. `orderId` / `orderUpdateId` / `lastNodeId` stay as they are.

## Cancelling (`cancelOrder` instant action, optional `orderId` parameter)

- Robot stops as soon as possible. Line-guided: next feasible node. Freely navigating: immediately.
- WAITING actions -> FAILED. RUNNING actions with `cancelAllowed` -> FAILED. Non-cancellable actions stay
  RUNNING until done, then FINISHED/FAILED.
- `cancelOrder` action state is RUNNING until all movement and actions stopped, then FINISHED.
- `orderId`, `orderUpdateId`, `lastNodeId`, `lastNodeSequenceId` unchanged. `nodeStates`, `edgeStates` emptied.
- Idle or orderId mismatch -> action FAILED, error NO_ORDER_TO_CANCEL (WARNING) with the `actionId` as reference.

## Next order after cancel

Robot that localizes only on nodes: first node = node it is standing on.
Robot that can stop between nodes, fleet control chooses one, robot must accept both:
- a temporary node at the robot's current position, or
- the last traversed node with `allowedDeviationXY` large enough to contain the robot.
Never send an update to the cancelled `orderId`.

## Corridors (3.0)

Optional edge attribute `corridor` (left/right boundary, `corridorReferencePoint` KINEMATICCENTER or
CONTOUR, `releaseRequired`). Leaving it -> OUTSIDE_OF_CORRIDOR (CRITICAL) and stop. With
`releaseRequired` the robot posts an `edgeRequest` in state and waits for a `responses` GRANTED.
