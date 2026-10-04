from __future__ import annotations

import argparse
from pathlib import Path

import cv2


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract evenly spaced keyframes from the kitchen walkthrough video.")
    parser.add_argument("--video", default="WhatsApp Video 2026-10-03 at 22.46.42.mp4")
    parser.add_argument("--out", default="artifacts/keyframes")
    parser.add_argument("--every-seconds", type=float, default=3.0)
    parser.add_argument("--max-frames", type=int, default=20)
    args = parser.parse_args()

    video = Path(args.video)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise SystemExit(f"Could not open video: {video}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = frame_count / fps if frame_count else 0
    step = max(1, int(fps * args.every_seconds))

    written = 0
    frame_index = 0
    while written < args.max_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = cap.read()
        if not ok:
            break
        timestamp = frame_index / fps
        path = out / f"keyframe_{written:03d}_{timestamp:06.2f}s.jpg"
        cv2.imwrite(str(path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        print(path)
        written += 1
        frame_index += step
        if frame_count and frame_index >= frame_count:
            break

    cap.release()
    print(f"Extracted {written} keyframes from {duration:.1f}s video into {out}")


if __name__ == "__main__":
    main()
