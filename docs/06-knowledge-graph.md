# 06 — Kitchen Knowledge Graph

## Storage

Use JSON for the MVP. Neo4j and heavyweight database infrastructure are out of scope.

Optional NetworkX may be used in memory for graph traversal and query convenience.

## Graph schema direction

```json
{
  "version": "0.1",
  "source_video": "configurable path outside repo",
  "objects": [
    {
      "id": "obj_kettle_001",
      "type": "electric_kettle",
      "semantic_label": "electric kettle",
      "zone": "counter",
      "confidence": 0.86,
      "status": "semantically_confirmed",
      "evidence": [
        {
          "kind": "narration",
          "timestamp": 12.4,
          "text": "The electric kettle is on the right side of the counter."
        }
      ]
    }
  ],
  "relationships": [
    {
      "subject": "obj_kettle_001",
      "relation": "RIGHT_OF",
      "object": "zone_counter_center",
      "confidence": 0.78,
      "evidence": []
    }
  ]
}
```

## Relationship vocabulary

- `LEFT_OF`
- `RIGHT_OF`
- `NEAR`
- `ON`
- `INSIDE`
- `BEHIND`
- `IN_FRONT_OF`
- `NEXT_TO`
- `SAME_ZONE`

## Uncertainty rule

Do not invent centimeter-level positions or precise identities without evidence. If a container is visually detected but not identified, store it as:

```json
{
  "type": "ingredient_container",
  "semantic_label": "unknown",
  "status": "visually_detected"
}
```

Narration or later evidence may upgrade the fact to semantically confirmed.
