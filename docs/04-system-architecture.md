# 04 — System Architecture

## Local-only architecture

```text
Narrated walkthrough video
    -> video/audio processing
    -> keyframe visual understanding + timestamped transcription
    -> Kitchen Knowledge Graph JSON

XIAO ESP32-S3 camera
    -> Wi-Fi JPEG/frame upload
    -> FastAPI local server
    -> live object detection
    -> graph query
    -> tea task state machine
    -> local TTS
    -> laptop speaker
```

## Mandatory layer separation

```text
PERCEPTION -> MEMORY -> DECISION -> OUTPUT
```

### Perception

- Live/keyframe visual reasoning via `scripts/live_kitchen_vlm.py`: `claude` (Anthropic vision API) primary, SmolVLM2-500M local fallback.
- Live frame detection with a lightweight YOLO model after dependency validation.
- Speech transcription with faster-whisper.

### Memory

- JSON Kitchen Knowledge Graph.
- Optional NetworkX in memory for querying.
- Stores objects, zones, relationships, confidence, evidence, timestamps, and uncertainty.

### Decision

- Deterministic tea task state machine.
- No LLM directly controls task transitions.

### Output

- Local TTS through laptop speaker.
- Repetition/cooldown logic to avoid constant repeated speech.

## Local server responsibilities

FastAPI endpoints should remain simple:

- `GET /health`
- `POST /mapping/process`
- `GET /graph`
- `POST /graph/query`
- `POST /frames`
- `GET /task`
- `POST /task/start`
- `POST /task/reset`
- `GET /guidance`
- `POST /device/status`

## ESP32 responsibilities

The ESP32 is a dumb edge device. It captures frames and sends them to the local server. It does not run models, graph logic, LLMs, task planning, or haptics.
