from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2


def laplacian_score(frame) -> float:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract sharper full-resolution keyframes for VLM environment understanding.")
    parser.add_argument("--video", default="WhatsApp Video 2026-10-03 at 22.46.42.mp4")
    parser.add_argument("--out", default="artifacts/keyframes_quality")
    parser.add_argument("--window-seconds", type=float, default=4.0, help="Pick the sharpest frame from each time window.")
    parser.add_argument("--max-frames", type=int, default=24)
    args = parser.parse_args()

    video = Path(args.video)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise SystemExit(f"Could not open video: {video}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    duration = frame_count / fps if frame_count else 0.0
    window = max(1, int(args.window_seconds * fps))

    metadata = {
        "video": str(video),
        "width": width,
        "height": height,
        "fps": fps,
        "duration_seconds": duration,
        "strategy": "sharpest_frame_per_window_full_resolution",
        "keyframes": [],
    }

    written = 0
    start = 0
    while start < frame_count and written < args.max_frames:
        end = min(frame_count, start + window)
        best = None
        best_score = -1.0
        best_index = start
        for idx in range(start, end, max(1, int(fps / 3))):
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok:
                continue
            score = laplacian_score(frame)
            if score > best_score:
                best = frame
                best_score = score
                best_index = idx
        if best is not None:
            timestamp = best_index / fps
            path = out / f"quality_keyframe_{written:03d}_{timestamp:06.2f}s.jpg"
            cv2.imwrite(str(path), best, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            metadata["keyframes"].append({
                "path": str(path),
                "timestamp_seconds": round(timestamp, 3),
                "frame_index": best_index,
                "sharpness_score": round(best_score, 2),
                "width": width,
                "height": height,
            })
            print(path)
            written += 1
        start += window

    cap.release()
    meta_path = out / "metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Extracted {written} quality keyframes from {duration:.1f}s video into {out}")
    print(f"Metadata: {meta_path}")


if __name__ == "__main__":
    main()
