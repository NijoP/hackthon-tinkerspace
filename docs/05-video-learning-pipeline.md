# 05 — Video Learning Pipeline

## Source video

Original local fixture:

```text
C:\Users\HP\Downloads\WhatsApp Video 2026-10-03 at 22.46.42.mp4
```

Do not modify or commit this original file.

## Required conceptual pipeline

```text
RECORDED VIDEO
    -> FRAME EXTRACTION
    -> KEYFRAME SELECTION
    -> VISUAL UNDERSTANDING
    +
    -> AUDIO EXTRACTION
    -> SPEECH TRANSCRIPTION
    -> VISUAL + LANGUAGE FUSION
    -> OBJECTS + RELATIONSHIPS
    -> KNOWLEDGE GRAPH
    -> kitchen_graph.json
```

## Keyframe strategy

Do not send every frame through a heavyweight model. Extract frames at a moderate interval and select representative keyframes using simple criteria such as timestamp spacing, scene-change heuristics, blur filtering, or manual override for the demo.

## Evidence model

Each extracted fact should preserve:

- source timestamp,
- frame path or frame index,
- transcript segment if applicable,
- confidence,
- evidence type: visual, narration, or fused.

## Output artifacts

Planned generated artifacts should live under ignored local directories such as:

```text
data/
artifacts/keyframes/
artifacts/audio/
artifacts/transcripts/
artifacts/graphs/
```
