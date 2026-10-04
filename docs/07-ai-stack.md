# 07 — AI Stack

## Current model plan

### Vision-language understanding

Live visual reasoning runs through `scripts/live_kitchen_vlm.py` with two backends:

- `claude` (Anthropic vision API) — primary. Fast (~1-3 s/frame) and high quality.
  Uploads the current frame to Anthropic; requires `ANTHROPIC_API_KEY`.
- `local` SmolVLM2-500M-Video-Instruct — on-device fallback. Fully private but
  slower (~8-9 s/frame) and generic in quality.

Used for selected keyframe analysis, ambiguous visual relationship interpretation,
semantic object/relationship extraction, and graph evidence generation.

SmolVLM2-2.2B-Instruct was dropped: the local download was unreliable and the
remote HF-endpoint path was replaced by the Anthropic `claude` backend. See
`docs/local_live_vlm.md` for configuration and the privacy trade-off.

### Live detection

Preferred lightweight detector: YOLO26n if available and compatible with the local environment.

Planned use:

- live camera object detection,
- bounding boxes,
- small configurable vocabulary.

Initial useful labels:

- person,
- electric kettle,
- cup,
- glass,
- tea,
- sugar,
- spoon,
- water,
- counter,
- table,
- stove,
- dish rack.

### Speech-to-text

Preferred library: faster-whisper.

Transcript must retain timestamps:

```json
{
  "start": 12.4,
  "end": 17.1,
  "text": "The electric kettle is on the right side of the counter."
}
```

### Text-to-speech

Preferred first implementation: pyttsx3 using Windows SAPI-compatible speech.

## Compatibility gate

Before downloading large models, verify:

- CPU,
- RAM,
- GPU,
- VRAM,
- disk space,
- Python version,
- PyTorch compatibility,
- Transformers version compatibility for SmolVLM2.

## Current assessment

Compatibility is command-verified on this laptop: RTX 3050 Laptop GPU (6 GB VRAM),
torch 2.6.0+cu124 with CUDA available, transformers 5.18, Python 3.11. SmolVLM2-500M
loads on CUDA (~1.4 GB VRAM, ~8-9 s/frame) but its descriptions are generic, so it
serves only as the local fallback. The `claude` backend is the primary reasoning
path for quality and latency.

## Dependency installation principle

Install only required packages. The vision stack now requires `anthropic` and
`python-dotenv` (added to `requirements.txt`) in addition to the local transformers
stack kept for the SmolVLM2-500M fallback.
