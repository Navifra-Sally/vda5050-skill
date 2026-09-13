# Example messages (captured, anonymized)

Real 3.0.0 messages from a fleet simulation, with manufacturer, serial numbers, ids and vendor tag
names replaced. Structure, field set, array lengths and byte sizes are as captured. Both files pass
`scripts/validate.py`.

| file | topic | what it shows | pretty size | compact size |
|---|---|---|---|---|
| `state-driving-3.0.json` | state | robot driving mid-order: 8 nodeStates (2 base + 6 horizon), 7 edgeStates, 9 FINISHED node actions kept from the base, 3 enabled maps, no `mobileRobotPosition` | 6.7 KB | 5.4 KB |
| `visualization-3.0.json` | visualization | position + velocity only, `referenceStateHeaderId` links it to the state above | 0.44 KB | 0.38 KB |

## What to notice in the state example

- `lastNodeSequenceId` is 88 and `nodeStates` starts at 90: the traversed node is gone from the list,
  only upcoming nodes remain. Base = the released ones (90, 92), horizon = the rest.
- `actionStates` still lists the nine FINISHED actions from earlier base nodes. Base action states are
  never removed by an order update; they stay until the order ends. This is why `actionStates` grows
  with long orders and why the message is 5 KB while carrying only 8 nodes.
- The actions are manufacturer-specific (`vendorPlcRead` / `vendorPlcWrite`) with a free-text
  `actionResult`. Fleet control needs the factsheet `protocolFeatures.mobileRobotActions` to know
  they exist; the spec defines none of this.
- `edgeId` is a concatenation of two node ids. Any string is legal; do not parse it.
- Three maps are ENABLED at once. Allowed, because they have different `mapId`s; the rule is at most
  one ENABLED version per `mapId`.
- There is no `mobileRobotPosition` in the state although the robot is `driving`. The schema allows
  that (the field is optional), the spec text says a robot that can determine its position "shall
  publish it via `mobileRobotPosition`". This robot publishes position only on `visualization`.
  Fleet control that reads position from `state` alone sees a robot with no position. Treat it as a
  robot-side gap to raise with the vendor; `scripts/validate.py state` prints a warning for it.
- The original capture had one `nodeStates` entry duplicated (sequenceId 90 twice). The schema does
  not catch that; `validate.py state` now does. Key everything on `sequenceId` and expect duplicates
  from simulators.

## What to notice in the visualization example

- `referenceStateHeaderId` (3.0) tells you which state message this position belongs to.
- `localized` and `localizationScore` live inside `mobileRobotPosition`.
- 0.4 KB per message; this topic is meant for high rate and carries nothing fleet logic should depend
  on.

## Sizes and rates for capacity planning

The spec gives only "on every relevant change and at least every 30 s" for `state` and "rate defined
by the integrator" for `visualization`. Numbers from this capture:

- state: 5 to 7 KB with a short order. Grows with horizon length (about 250 B per node with position)
  and with the number of finished base actions (about 200 B each). A long order with 40 nodes and 30
  actions is 15 to 20 KB.
- visualization: about 0.4 KB, constant.
- In this capture the robot had published 3.3 visualization messages per state message (headerId
  23173 vs 7064 at the same instant). With state at about 1 Hz while driving that puts visualization
  around 3 Hz; many robots use 5 to 10 Hz.

Rough bandwidth per robot = state_bytes x state_rate + vis_bytes x vis_rate.
Example: 6 KB x 1 Hz + 0.4 KB x 5 Hz = 8 KB/s per robot, 100 robots = 0.8 MB/s into the broker plus
one copy per subscriber. Fleet control should subscribe to `state` only; let UIs subscribe to
`visualization`.

State bursts: a new order or order update triggers a state, and so does every node traversal, action
state change and `driving` toggle. Expect 3 to 5 state messages within a second around each node.
