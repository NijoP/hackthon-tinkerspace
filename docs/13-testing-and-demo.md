# 13 — Testing and Demo

## Minimum feature tests

- Server: `GET /health` returns success.
- Video: keyframe extraction produces image files from the source video.
- Speech: faster-whisper generates timestamped transcript segments.
- Vision: selected keyframes produce structured observations.
- Graph: valid Kitchen Knowledge Graph JSON is produced.
- Query: known relationship queries return expected facts.
- Task: deterministic state transitions are tested.
- Audio: laptop speaker produces audible guidance.
- ESP32: a camera frame reaches the server.
- Live: current frame can produce object detections.
- End-to-end: video -> graph -> task -> speech works locally.

## Demo safety

The blindfold demo must be controlled and safe:

- no genuinely boiling water,
- no dangerous electrical manipulation,
- no hazardous kitchen activity,
- stop on uncertainty.

## Demo success criteria

1. The walkthrough video is processed locally.
2. Visual information is extracted.
3. Narration is transcribed.
4. A Kitchen Knowledge Graph is generated.
5. The graph can be queried.
6. The ESP32 camera can provide live frames.
7. The server can process current observations.
8. The tea task engine runs through its states.
9. The laptop speaker provides understandable guidance.
10. Documentation and roadmap match the real state.
