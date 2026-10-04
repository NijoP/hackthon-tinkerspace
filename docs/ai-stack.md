# AI Stack

## Selection policy

Do not download large models until the laptop audit is complete:

- CPU
- RAM
- GPU
- VRAM
- disk space
- Python/PyTorch/Transformers compatibility

## Current choices

- Live visual reasoning: unified `scripts/live_kitchen_vlm.py` with two backends:
  - `claude` (Anthropic vision API) as the primary, high-quality endpoint path.
  - `local` SmolVLM2-500M-Video-Instruct as the on-device, fully-private fallback.
  - SmolVLM2-2.2B was dropped (unreliable local download; HF-endpoint path removed).
- Live object detection: evaluate YOLO26n first; evaluate YOLOE-26n if open-vocabulary kitchen objects are required.
- Speech-to-text: faster-whisper, smallest reliable local model.
- Text-to-speech: pyttsx3 / Windows SAPI.

## Verified environment

Validated on this laptop: AMD Ryzen 7 7840HS, 16 GB RAM, NVIDIA RTX 3050 Laptop
GPU (6 GB VRAM), Python 3.11, torch 2.6.0+cu124 with CUDA available, transformers
5.18. SmolVLM2-500M runs on CUDA using ~1.4 GB VRAM at ~8-9 s/frame. The Anthropic
`claude` backend requires `ANTHROPIC_API_KEY` and network access. See
`docs/local_live_vlm.md`.

## Source video

The mapping video to process is local:

```text
C:\Users\HP\Downloads\hackathon\WhatsApp Video 2026-10-03 at 22.46.42.mp4
```

The video should be used for visual understanding and transcription to build `kitchen_graph.json`.
