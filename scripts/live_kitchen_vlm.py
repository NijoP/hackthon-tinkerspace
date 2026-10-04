from __future__ import annotations

"""Unified live kitchen visual reasoning.

Two interchangeable backends, selected with --backend or the VLM_BACKEND env var:

  claude : Anthropic vision API. Fast, high quality. Sends the current camera
           frame to Anthropic. Requires ANTHROPIC_API_KEY. Not local-only.
  local  : SmolVLM2-500M-Video-Instruct via transformers on CUDA/CPU. Slower and
           lower quality, but every frame stays on this laptop.

If --backend claude is requested but the key/SDK/network is unavailable, and a
local fallback is allowed, the worker automatically falls back to the local
SmolVLM2-500M model so the demo keeps running.

Both backends write the same schema to artifacts/live/vlm_reasoning.json so the
dashboard and task engine never need to know which backend produced it.
"""

import argparse
import base64
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import urlopen

try:  # Load .env if python-dotenv is present; otherwise rely on real env vars.
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except Exception:
    pass

LOCAL_MODEL = "HuggingFaceTB/SmolVLM2-500M-Video-Instruct"
DEFAULT_CLAUDE_MODEL = os.getenv("VLM_CLAUDE_MODEL", "claude-3-5-sonnet-latest")

PROMPT = """You are a conservative visual observer for a kitchen assistant that helps a visually impaired person. Analyze only this single latest kitchen camera frame.
Return concise JSON exactly in this schema and nothing else:
{"summary":"one short sentence describing only clearly visible evidence","objects":[{"label":"object name","location":"visually supported position (left/center/right, foreground/background) or unknown","confidence":0.0,"uncertainty":"certain|uncertain|unknown"}],"safety_notes":["only directly visible hazards, otherwise empty list"]}
Rules: Do not identify any person by name or infer identity. Do not claim an object is present if it is unclear. Do not give action or safety instructions. If a visual fact is uncertain, mark it uncertain. Do not assume anything from earlier frames. No Markdown code fences."""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_state(path: Path, state: dict[str, Any]) -> None:
    # Per-process temp name avoids cross-process collisions on Windows (WinError 5),
    # and os.replace is retried briefly to ride out transient AV/indexer locks.
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    for attempt in range(5):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.1)
    # Last resort: leave the temp file rather than crash the worker.
    try:
        os.replace(tmp, path)
    except PermissionError:
        pass


def get_json(url: str, timeout: float = 3.0) -> dict[str, Any]:
    with urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def get_frame(url: str, timeout: float = 4.0) -> bytes:
    with urlopen(url, timeout=timeout) as response:
        return response.read()


def parse_response(text: str) -> dict[str, Any]:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    if "Assistant:" in cleaned:
        cleaned = cleaned.rsplit("Assistant:", 1)[-1].strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(cleaned[start:end + 1])
            if isinstance(parsed, dict):
                parsed.setdefault("objects", [])
                parsed.setdefault("safety_notes", [])
                return parsed
        except json.JSONDecodeError:
            pass
    return {
        "summary": cleaned[:1000] or "No visual description returned.",
        "objects": [],
        "safety_notes": [],
        "parse_warning": "Model did not return valid JSON.",
    }


# --------------------------------------------------------------------------- #
# Backends
# --------------------------------------------------------------------------- #
class ClaudeBackend:
    """Anthropic vision backend. Camera frames are uploaded to Anthropic."""

    name = "claude"
    local_only = False

    def __init__(self, model: str, max_tokens: int, timeout: float) -> None:
        import anthropic  # imported lazily so local-only installs do not need it

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set. Put it in .env or the shell; never in code or chat.")
        self.model = model
        self.model_name = model
        self.max_tokens = max_tokens
        self.client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
        self.device = f"Anthropic API ({model})"
        self._validate()

    def _validate(self) -> None:
        """Fail fast on an unusable key (e.g. a Claude Code 'sk-ant-usr-' token,
        wrong model, or no API credits) so main() can fall back to local."""
        try:
            self.client.messages.create(
                model=self.model,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
        except Exception as exc:
            raise RuntimeError(
                f"Anthropic API key/model check failed: {type(exc).__name__}: {str(exc)[:200]}. "
                "A Console API key (sk-ant-api03-...) with API credits is required; "
                "Claude Code tokens (sk-ant-usr-...) do not work with the Messages API."
            ) from exc

    def infer(self, frame: bytes) -> str:
        b64 = base64.b64encode(frame).decode("ascii")
        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            # temperature is passed via extra_body for SDK variants that do not
            # expose it as a typed keyword argument.
            extra_body={"temperature": 0},
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                    {"type": "text", "text": PROMPT},
                ],
            }],
        )
        parts = [block.text for block in message.content if getattr(block, "type", None) == "text"]
        return "\n".join(parts)


class LocalBackend:
    """SmolVLM2-500M backend. Frames never leave this laptop."""

    name = "local"
    local_only = True

    def __init__(self, model: str, max_tokens: int) -> None:
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor

        self._torch = torch
        self.max_tokens = max_tokens
        self.model_name = model
        if torch.cuda.is_available():
            self.device, dtype = "cuda", torch.float16
        else:
            self.device, dtype = "cpu", torch.float32
        self.processor = AutoProcessor.from_pretrained(model, local_files_only=True)
        self.net = AutoModelForImageTextToText.from_pretrained(
            model, torch_dtype=dtype, low_cpu_mem_usage=True, local_files_only=True
        ).to(self.device)
        self.net.eval()

    def infer(self, frame: bytes) -> str:
        import io

        from PIL import Image

        image = Image.open(io.BytesIO(frame)).convert("RGB")
        messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": PROMPT}]}]
        chat = self.processor.apply_chat_template(messages, add_generation_prompt=True)
        inputs = self.processor(text=chat, images=[image], return_tensors="pt").to(self.device)
        with self._torch.inference_mode():
            result = self.net.generate(**inputs, max_new_tokens=self.max_tokens, do_sample=False)
        return self.processor.batch_decode(result, skip_special_tokens=True)[0]


def build_backend(name: str, args: argparse.Namespace):
    if name == "claude":
        return ClaudeBackend(args.claude_model, args.max_tokens, args.timeout)
    return LocalBackend(LOCAL_MODEL, args.max_tokens)


# --------------------------------------------------------------------------- #
# Main loop
# --------------------------------------------------------------------------- #
def main() -> None:
    parser = argparse.ArgumentParser(description="Unified live kitchen visual reasoning (Claude endpoint or local SmolVLM2-500M).")
    parser.add_argument("--backend", choices=["claude", "local"], default=os.getenv("VLM_BACKEND", "claude"))
    parser.add_argument("--source", choices=["mobile", "esp32"], default="mobile")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--claude-model", default=DEFAULT_CLAUDE_MODEL)
    parser.add_argument("--interval", type=float, default=0.25, help="Polling interval; inference only runs on a new latest frame.")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--max-tokens", type=int, default=240)
    parser.add_argument("--state", default="artifacts/live/vlm_reasoning.json")
    parser.add_argument("--once", action="store_true", help="Analyze one fresh frame, write state, then exit.")
    parser.add_argument("--no-fallback", action="store_true", help="Do not fall back to the local model if Claude is unavailable.")
    args = parser.parse_args()

    requested = args.backend
    state_path = Path(args.state)
    root = args.base_url.rstrip("/")
    status_url = root + "/status"
    frame_url = root + ("/api/latest.jpg" if args.source == "esp32" else "/api/mobile/latest.jpg")
    frame_key = "latest_frame" if args.source == "esp32" else "latest_mobile_frame"
    camera_key = "camera" if args.source == "esp32" else "mobile_camera"

    base_state: dict[str, Any] = {
        "status": "loading_backend", "backend": requested, "source": args.source,
        "last_observation": None, "last_error": None, "started_at": now_iso(),
    }
    write_state(state_path, base_state)

    # Build the requested backend, with optional automatic fallback to local.
    try:
        backend = build_backend(requested, args)
    except Exception as exc:
        if requested == "claude" and not args.no_fallback:
            print(f"Claude backend unavailable ({type(exc).__name__}: {exc}); falling back to local SmolVLM2-500M.")
            backend = build_backend("local", args)
        else:
            base_state.update({"status": "error", "last_error": f"{type(exc).__name__}: {str(exc)[:400]}", "updated_at": now_iso()})
            write_state(state_path, base_state)
            raise SystemExit(str(exc))

    note = (
        "Local inference; camera frames stay on this laptop."
        if backend.local_only
        else "Camera frames are uploaded to the Anthropic API for visual reasoning."
    )
    print(f"Backend ready: {backend.name} ({backend.device}); source={args.source}. {note}")

    state: dict[str, Any] = {
        **base_state,
        "status": "running", "backend": backend.name, "requested_backend": requested,
        "model": backend.model_name, "device": backend.device,
        "local_only": backend.local_only, "endpoint_configured": not backend.local_only,
        "note": note,
    }
    write_state(state_path, state)

    last_frame_id: Any = None
    while True:
        try:
            status = get_json(status_url)
            info = status.get(frame_key, {})
            if status.get(camera_key) != "CONNECTED" or not info.get("available"):
                state.update({"status": "waiting_for_camera", "last_error": None, "frame_age_ms": info.get("age_ms")})
                write_state(state_path, state)
                time.sleep(max(0.1, args.interval))
                continue

            frame_id = info.get("frame_id")
            if frame_id == last_frame_id:
                state["status"] = "waiting_for_new_frame"
                write_state(state_path, state)
                time.sleep(max(0.1, args.interval))
                continue

            frame = get_frame(frame_url)
            started = time.monotonic()
            raw = backend.infer(frame)
            latency_ms = round((time.monotonic() - started) * 1000)
            observation = parse_response(raw)
            state.update({
                "status": "running", "backend": backend.name, "device": backend.device,
                "last_observation": observation, "last_error": None, "last_frame_id": frame_id,
                "frame_age_ms_at_inference": info.get("age_ms"), "latency_ms": latency_ms,
                "updated_at": now_iso(), "note": note,
            })
            last_frame_id = frame_id
            write_state(state_path, state)
            print(f"{backend.name} inference {latency_ms} ms; frame={frame_id}; {str(observation.get('summary',''))[:160]}")
            if args.once:
                break
        except KeyboardInterrupt:
            break
        except Exception as exc:
            # Never log tokens, keys, request payloads, or image bytes.
            state.update({"status": "error", "last_error": f"{type(exc).__name__}: {str(exc)[:400]}", "updated_at": now_iso()})
            write_state(state_path, state)
            print(f"{backend.name} inference error: {type(exc).__name__}: {str(exc)[:200]}")
            time.sleep(1)

    state.update({"status": "stopped", "updated_at": now_iso()})
    write_state(state_path, state)
    print(f"{backend.name} VLM stopped.")


if __name__ == "__main__":
    main()
