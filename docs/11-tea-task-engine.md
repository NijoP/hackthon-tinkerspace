# 11 — Tea Task Engine

## Deterministic state machine

The MVP task state machine is deterministic:

```text
START
    -> KITCHEN_READY
    -> FIND_KETTLE
    -> FIND_CUP
    -> FIND_TEA
    -> FIND_SUGAR
    -> FIND_SPOON
    -> TASK_COMPLETE
```

## Rule

Do not allow an LLM or VLM to directly control transitions. Perception can supply observations and confidence. The task engine decides the next state.

## Guidance examples

- `Welcome to the kitchen.`
- `The kettle is on your right.`
- `Move forward.`
- `The cup is beside the kettle.`
- `Tea is to the left of the kettle.`
- `Task complete.`

## Safe fallback

If graph memory or live perception is uncertain, the task engine should produce:

```text
I am not certain. Please stop.
```

## Test expectations

Basic tests should verify:

- initial state is `START`,
- state order is enforced,
- invalid transitions are rejected,
- guidance is generated from graph/task context,
- uncertainty produces the safe fallback.
