# 14 — Development Roadmap

## Cycle plan

0. Environment + dependency audit.
1. Project documentation.
2. Local server skeleton.
3. Mapping video ingestion.
4. Keyframe extraction.
5. Speech transcription.
6. Vision understanding.
7. Knowledge graph generation.
8. Graph query engine.
9. Tea task state machine.
10. Local TTS / speaker feedback.
11. PlatformIO XIAO ESP32-S3 camera firmware.
12. ESP32 -> laptop communication.
13. Live visual detection.
14. End-to-end integration.
15. Blindfold demo test.
16. Stabilization + final documentation.
17. Final demo readiness.

## Near-term dependency order

1. Restore a working shell/toolchain in Herdr/Pi.
2. Verify Python, FFmpeg, Git, PlatformIO, Node if needed, CPU/RAM/GPU/VRAM, and disk.
3. Confirm model compatibility before large downloads.
4. Create project-local `.venv` and requirements.
5. Implement the FastAPI health endpoint and tests.

## Roadmap source of truth

`docs/roadmap.html` is the live visual roadmap and must be updated after every meaningful development cycle.
