# 02 — Product Vision

## Core concept

```text
TEACH -> UNDERSTAND -> MEMORIZE -> QUERY -> GUIDE
```

The product concept is not merely detecting a kettle. The product learns an environment from a narrated walkthrough, represents that environment as a spatial-semantic graph, and uses the graph as memory while guiding a task.

## Demonstration story

1. A sighted helper records a narrated walkthrough of the kitchen.
2. The local system extracts keyframes and transcribes narration.
3. The system fuses visual and spoken evidence into a Kitchen Knowledge Graph.
4. During a safe tea-preparation demo, the system observes current camera frames.
5. The task engine queries the graph and speaks the next instruction.

## User feedback

Primary MVP feedback is laptop speaker audio. Haptic feedback is deferred and must not be implemented in this MVP without explicit scope change.

## Design principles

- Local-first and privacy-preserving.
- Evidence-based memory.
- Explicit uncertainty.
- Simple deterministic task control.
- Safe fallback on uncertainty.
- Low integration complexity suitable for a 24-hour hackathon.
