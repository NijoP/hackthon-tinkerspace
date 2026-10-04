# Live visual reasoning

Live frame reasoning is handled by a single unified worker, `scripts/live_kitchen_vlm.py`,
with two interchangeable backends selected by `--backend` or the `VLM_BACKEND` env var.

## Backends

| Backend | Engine | Quality | Latency | Privacy |
| --- | --- | --- | --- | --- |
| `claude` | Anthropic vision API | High | ~1-3 s/frame | Frames are uploaded to Anthropic |
| `local` | SmolVLM2-500M-Video-Instruct on CUDA/CPU | Low (generic, sometimes repetitive) | ~8-9 s/frame on RTX 3050 | Frames never leave this laptop |

`claude` is the default and the demo path. `local` is the offline / fully-private
fallback. If `--backend claude` is requested but the API key, SDK, or network is
unavailable, the worker automatically falls back to `local` unless `--no-fallback`
is passed.

Both backends write the same schema to `artifacts/live/vlm_reasoning.json`, so the
dashboard and the deterministic kitchen task engine do not need to know which
backend produced a given observation. VLM output is an observation, not a verified
graph fact or an action instruction; the deterministic kitchen graph remains the
authority for location answers.

## Configure

Copy `.env.example` to `.env` and set:

```ini
VLM_BACKEND=claude
ANTHROPIC_API_KEY=sk-ant-...
VLM_CLAUDE_MODEL=claude-3-5-sonnet-latest
```

Keep the key only in `.env` (git-ignored) or the shell. Never commit it, print it,
or paste it into chat or logs.

## Run

Start the laptop API servers first, then run the worker:

```powershell
cd C:\Users\HP\Downloads\hackathon
.\.venv\Scripts\Activate.ps1

# Fast cloud reasoning (uploads frames to Anthropic):
python scripts\live_kitchen_vlm.py --backend claude --source mobile

# Fully-local, private reasoning (SmolVLM2-500M on this laptop):
python scripts\live_kitchen_vlm.py --backend local --source mobile

# ESP32 camera stream instead of the mobile camera:
python scripts\live_kitchen_vlm.py --backend claude --source esp32
```

The worker samples only the newest unseen frame, keeps no inference queue, and
writes observations to `artifacts/live/vlm_reasoning.json`.

## Privacy note

The project was originally designed as local-only, with camera frames never leaving
the laptop. The `claude` backend intentionally changes that for the demo: it sends
the current kitchen frame to the Anthropic API for higher-quality reasoning. This is
an explicit, owner-approved trade-off. Use `--backend local` whenever frames must
stay on-device.

## Model history

- `SmolVLM2-500M-Video-Instruct` loaded on CUDA and processed live frames, but its
  descriptions were generic and sometimes repetitive, so it is kept only as the
  local/offline fallback, not as the primary reasoning quality target.
- `SmolVLM2-2.2B-Instruct` was dropped: the local download was unreliable and the
  remote HF-endpoint path was removed in favor of the Anthropic `claude` backend.
- The Ollama `qwen2.5vl:3b` path was removed; Anthropic is the chosen endpoint.
