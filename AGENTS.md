# Project Agent Instructions

## Project goal

Build a local-only hackathon MVP of an AI-assisted kitchen guidance system for a visually impaired user. The system learns a kitchen from one narrated walkthrough video, stores that learning as a spatial-semantic Kitchen Knowledge Graph, and uses that memory plus live camera observations to guide a simplified tea-preparation task through laptop speaker audio.

## Repository and privacy rule

- The project owner published this repository publicly on GitHub (`NijoP/hackthon-tinkerspace`) on 2026-10-04. Pushing to that repository is allowed.
- AI inference stays local where possible. Remote endpoints (Anthropic vision, NVIDIA Nemotron) are opt-in via `.env` and must be documented.
- Never commit secrets, credentials, tokens, private keys, TLS certificates, `.env`, `firmware/include/secrets.h`, the original walkthrough video, phone camera captures, microphone recordings or logs. `.gitignore` enforces this; check `git status` before every commit.

## Current MVP scope

In scope:

- One camera-equipped Seeed Studio XIAO ESP32-S3 / Sense variant.
- One local Windows laptop/server.
- Local AI inference only.
- One kitchen walkthrough video.
- One JSON Kitchen Knowledge Graph.
- One simplified tea-preparation task.
- Laptop speaker voice guidance.

Out of scope:

- Haptic feedback.
- Wearable hardware beyond the camera board.
- Multiple cameras.
- SLAM or 3D reconstruction.
- Robotics.
- Cloud GPU or cloud AI APIs.
- Neo4j or heavyweight database infrastructure.
- Production deployment or safety certification.

## Architecture boundaries

Keep these layers separate:

```text
PERCEPTION -> MEMORY -> DECISION -> OUTPUT
```

- Perception: YOLO / SmolVLM / faster-whisper outputs observations and evidence.
- Memory: Kitchen Knowledge Graph stores objects, zones, relationships, confidence, and evidence.
- Decision: deterministic tea task state machine chooses the next task action.
- Output: laptop speaker TTS speaks guidance.

The ESP32 is a dumb edge device. It only initializes the camera, connects to Wi-Fi, captures frames/JPEGs, sends them to the local server, reports basic status, and handles minimal transport/control logic. Do not add AI, semantic reasoning, LLM logic, haptics, or task planning to firmware.

## Uncertainty rule

Never hallucinate environment facts. If an object is uncertain, store it as uncertain with evidence and confidence. Distinguish visually detected facts from semantically confirmed facts. If guidance is uncertain, use a safe fallback such as: `I am not certain. Please stop.`

## Safety rule

This is a hackathon prototype, not a safety-certified assistive device. For any blindfolded demonstration:

- Do not use genuinely boiling water.
- Do not require dangerous electrical manipulation.
- Avoid hazardous kitchen activity.
- Use a controlled or simulated tea-preparation sequence.

## Coding conventions

- Prefer simple, inspectable Python modules.
- Use FastAPI for the local server.
- Keep APIs small and local.
- Use JSON for graph persistence.
- Use PlatformIO for ESP32 firmware.
- Keep embedded code minimal.
- Write basic tests for each meaningful feature.
- Update `docs/roadmap.html` after every meaningful development cycle.

## Testing expectations

Minimum evidence by area:

- Server: `GET /health` succeeds.
- Video: keyframes are extracted from the walkthrough video.
- Speech: timestamped transcript is generated.
- Vision: selected keyframes produce structured observations.
- Graph: valid graph JSON is produced.
- Query: known relationships can be queried.
- Task: tea state transitions are deterministic and tested.
- Audio: local TTS produces audible laptop speaker output.
- ESP32: camera frame reaches server.
- End-to-end: video -> graph -> task -> speech flow works locally.

## Current MVP status

Phase 0 and Phase 1 are being established. Runtime shell execution is currently blocked in the Pi/Herdr environment because Bash/Git Bash is not discoverable, so dependency and hardware commands still require verification from a working shell.
