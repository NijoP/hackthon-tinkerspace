from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcribe the kitchen walkthrough video with faster-whisper.")
    parser.add_argument("--video", default="WhatsApp Video 2026-10-03 at 22.46.42.mp4")
    parser.add_argument("--out", default="artifacts/transcripts/kitchen_transcript.json")
    parser.add_argument("--model", default="base", help="faster-whisper model size/name, e.g. tiny, base, small")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--compute-type", default="auto", help="auto, int8, float16, int8_float16, etc.")
    args = parser.parse_args()

    try:
        from faster_whisper import WhisperModel
    except Exception as exc:
        raise SystemExit(f"faster-whisper is not installed or failed to import: {exc}")

    video = Path(args.video)
    if not video.exists():
        raise SystemExit(f"Video not found: {video}")

    device = args.device
    compute_type = args.compute_type
    if device == "auto":
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            device = "cpu"
    if compute_type == "auto":
        compute_type = "float16" if device == "cuda" else "int8"

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        model = WhisperModel(args.model, device=device, compute_type=compute_type)
        segments_iter, info = model.transcribe(str(video), beam_size=5, vad_filter=True)
        segments = []
        full_text_parts = []
        for seg in segments_iter:
            item = {
                "id": seg.id,
                "start": round(float(seg.start), 3),
                "end": round(float(seg.end), 3),
                "text": seg.text.strip(),
            }
            segments.append(item)
            full_text_parts.append(item["text"])
            print(f"[{item['start']:.2f}s -> {item['end']:.2f}s] {item['text']}")
        doc = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_video": str(video),
            "model": args.model,
            "device": device,
            "compute_type": compute_type,
            "language": getattr(info, "language", None),
            "language_probability": getattr(info, "language_probability", None),
            "duration": getattr(info, "duration", None),
            "text": " ".join(full_text_parts),
            "segments": segments,
        }
    except Exception as exc:
        doc = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_video": str(video),
            "model": args.model,
            "device": device,
            "compute_type": compute_type,
            "status": "blocked",
            "error": str(exc),
            "segments": [],
        }
        out.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        raise SystemExit(f"Transcription blocked: {exc}")

    out.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
