from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import torch
from PIL import Image
from transformers import AutoModelForImageTextToText, AutoProcessor

ALLOWED_RELATIONS = {
    "LEFT_OF", "RIGHT_OF", "NEAR", "NEXT_TO", "ON", "INSIDE", "BEHIND", "IN_FRONT_OF", "SAME_ZONE"
}
TARGET_OBJECTS = ["glass", "tea", "kettle", "sugar", "spoon", "cup", "bottle", "towel", "toaster", "oven", "microwave", "cabinet", "counter"]

PROMPT = """You are helping a visually impaired user by analyzing one frame from a kitchen walkthrough.
Return ONLY valid JSON. Be conservative and do not guess.
Schema:
{
  "zone": "short room/area name or unknown",
  "objects": [
    {"type":"object type", "label":"semantic label", "location":"where it is, or unknown", "confidence":0.0-1.0, "uncertainty":"certain|uncertain|unknown"}
  ],
  "relationships": [
    {"subject":"label", "relation":"LEFT_OF|RIGHT_OF|NEAR|NEXT_TO|ON|INSIDE|BEHIND|IN_FRONT_OF|SAME_ZONE", "object":"label", "confidence":0.0-1.0}
  ]
}
Only include objects and relations visible in the image. If unsure, mark uncertain or unknown.
"""


def timestamp_from_name(path: Path) -> float | None:
    m = re.search(r"_(\d+(?:\.\d+)?)s\.jpg$", path.name)
    return float(m.group(1)) if m else None


def assistant_text(decoded: str) -> str:
    if "Assistant:" in decoded:
        return decoded.split("Assistant:", 1)[1].strip()
    return decoded.strip()


def extract_jsonish(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        snippet = text[start : end + 1]
        try:
            return json.loads(snippet)
        except Exception:
            return {"parse_error": True, "raw": text}
    return {"parse_error": True, "raw": text}


def flatten_objects_from_any(data: Any, frame: str, ts: float | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    objects: list[dict[str, Any]] = []
    rels: list[dict[str, Any]] = []

    def add_obj(obj_type: str, label: str, location: str, confidence: float = 0.55, uncertainty: str = "uncertain") -> None:
        label = (label or obj_type or "unknown").strip().lower()
        obj_type = (obj_type or label or "unknown").strip().lower()
        if not label or label == "unknown":
            return
        objects.append({
            "object_type": obj_type,
            "semantic_label": label,
            "location": location or "unknown",
            "confidence": confidence,
            "evidence_frame": frame,
            "source_timestamp": ts,
            "uncertainty_status": uncertainty if uncertainty in {"certain", "uncertain", "unknown"} else "uncertain",
        })

    if isinstance(data, dict) and isinstance(data.get("objects"), list):
        for o in data.get("objects", []):
            if not isinstance(o, dict):
                continue
            conf = o.get("confidence", 0.6)
            try:
                conf = float(conf)
            except Exception:
                conf = 0.6
            add_obj(str(o.get("type") or o.get("object_type") or o.get("label") or "unknown"),
                    str(o.get("label") or o.get("semantic_label") or o.get("type") or "unknown"),
                    str(o.get("location") or data.get("zone") or "unknown"), conf,
                    str(o.get("uncertainty") or o.get("uncertainty_status") or "uncertain"))
        for r in data.get("relationships", []):
            if isinstance(r, dict) and str(r.get("relation", "")).upper() in ALLOWED_RELATIONS:
                rels.append({
                    "subject": str(r.get("subject", "unknown")).lower(),
                    "relation": str(r.get("relation")).upper(),
                    "object": str(r.get("object", "unknown")).lower(),
                    "confidence": float(r.get("confidence", 0.5) or 0.5),
                    "evidence_frame": frame,
                    "source_timestamp": ts,
                })
        return objects, rels

    # Fallback for model outputs that are JSON but not our requested schema, e.g. nested kitchen/counter/top/cup.
    def walk(node: Any, path: list[str]) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                key = str(k).lower()
                if key in TARGET_OBJECTS:
                    label = f"{v} {key}" if isinstance(v, str) and v.lower() not in {"unknown", key} else key
                    loc = " / ".join(path) if path else "unknown"
                    add_obj(key, label, loc, 0.55, "uncertain")
                    if path:
                        rels.append({
                            "subject": label.lower(), "relation": "SAME_ZONE", "object": path[-1].lower(),
                            "confidence": 0.45, "evidence_frame": frame, "source_timestamp": ts,
                        })
                walk(v, path + [key])
        elif isinstance(node, list):
            for item in node:
                walk(item, path)

    walk(data, [])
    return objects, rels


def merge_objects(objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for o in objects:
        key = re.sub(r"^(green|black|white|red|blue|pink|plastic|metal|glass)\s+", "", o["semantic_label"].lower())
        key = key or o["semantic_label"].lower()
        if key not in merged or float(o.get("confidence", 0)) > float(merged[key].get("confidence", 0)):
            merged[key] = dict(o)
            merged[key]["object_id"] = f"obj_{len(merged)+1:03d}_{re.sub(r'[^a-z0-9]+', '_', key).strip('_')}"
        else:
            ev = merged[key].setdefault("additional_evidence", [])
            ev.append({"evidence_frame": o.get("evidence_frame"), "source_timestamp": o.get("source_timestamp"), "location": o.get("location")})
    return list(merged.values())


def run_keyframe_extraction(max_frames: int, every_seconds: float) -> None:
    subprocess.run([
        "python", "scripts/extract_keyframes.py", "--max-frames", str(max_frames), "--every-seconds", str(every_seconds)
    ], check=True)


def integrate_transcript(graph: dict[str, Any], transcript_path: Path) -> None:
    if not transcript_path.exists():
        return
    try:
        transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    except Exception:
        return
    segments = transcript.get("segments", []) if isinstance(transcript, dict) else []
    for seg in segments:
        text = str(seg.get("text", "")).lower()
        for item in ["glass", "tea", "kettle", "sugar", "spoon"]:
            if item not in text:
                continue
            # Only accept explicit simple location phrases from narration.
            m = re.search(rf"{item}\s+(?:is|are)?\s*(?:in|inside|on|near|next to|beside)\s+([^.,;]+)", text)
            if not m:
                continue
            graph["objects"].append({
                "object_id": f"obj_transcript_{item}_{len(graph['objects'])+1}",
                "object_type": item,
                "semantic_label": item,
                "location": m.group(1).strip(),
                "relationships": [],
                "confidence": 0.7,
                "evidence_frame": "transcript",
                "source_timestamp": seg.get("start"),
                "uncertainty_status": "uncertain",
                "evidence_source": "transcript",
            })


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a conservative kitchen knowledge graph from walkthrough keyframes.")
    parser.add_argument("--model", default="HuggingFaceTB/SmolVLM2-500M-Video-Instruct")
    parser.add_argument("--keyframes", default="artifacts/keyframes")
    parser.add_argument("--raw-out", default="artifacts/vlm")
    parser.add_argument("--graph-out", default="data/graphs/kitchen_graph.json")
    parser.add_argument("--max-vlm-frames", type=int, default=5)
    parser.add_argument("--extract-if-missing", action="store_true")
    parser.add_argument("--transcript", default="artifacts/transcripts/kitchen_transcript.json")
    parser.add_argument("--max-new-tokens", type=int, default=384)
    args = parser.parse_args()

    keyframe_dir = Path(args.keyframes)
    if args.extract_if_missing and not list(keyframe_dir.glob("*.jpg")):
        run_keyframe_extraction(20, 3.0)

    frames = sorted(keyframe_dir.glob("*.jpg"))[: args.max_vlm_frames]
    if not frames:
        raise SystemExit(f"No keyframes found in {keyframe_dir}")

    raw_out = Path(args.raw_out)
    raw_out.mkdir(parents=True, exist_ok=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    processor = AutoProcessor.from_pretrained(args.model)
    model = AutoModelForImageTextToText.from_pretrained(args.model, torch_dtype=dtype, low_cpu_mem_usage=True).to(device)

    all_objects: list[dict[str, Any]] = []
    all_rels: list[dict[str, Any]] = []
    for frame in frames:
        image = Image.open(frame).convert("RGB")
        messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": PROMPT}]}]
        prompt = processor.apply_chat_template(messages, add_generation_prompt=True)
        inputs = processor(text=prompt, images=[image], return_tensors="pt").to(device)
        with torch.inference_mode():
            generated = model.generate(**inputs, max_new_tokens=args.max_new_tokens, do_sample=False)
        decoded = processor.batch_decode(generated, skip_special_tokens=True)[0]
        response = assistant_text(decoded)
        parsed = extract_jsonish(response)
        ts = timestamp_from_name(frame)
        raw_doc = {"model": args.model, "image": str(frame), "timestamp": ts, "device": device, "response": response, "parsed": parsed}
        (raw_out / f"{frame.stem}.json").write_text(json.dumps(raw_doc, indent=2), encoding="utf-8")
        objs, rels = flatten_objects_from_any(parsed, str(frame), ts)
        all_objects.extend(objs)
        all_rels.extend(rels)
        print(f"analyzed {frame}: {len(objs)} objects, {len(rels)} relationships")

    merged_objects = merge_objects(all_objects)
    # Attach matching relationships to object records and keep graph-level relationships too.
    for o in merged_objects:
        label = o["semantic_label"].lower()
        base = re.sub(r"^(green|black|white|red|blue|pink|plastic|metal|glass)\s+", "", label)
        o["relationships"] = [r for r in all_rels if r.get("subject") in {label, base}]

    graph = {
        "schema_version": "0.1",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_video": "WhatsApp Video 2026-10-03 at 22.46.42.mp4",
        "model": args.model,
        "relations_allowed": sorted(ALLOWED_RELATIONS),
        "objects": merged_objects,
        "relationships": all_rels,
        "notes": "Conservative local-only graph. Unknown/uncertain retained when evidence is weak.",
    }
    integrate_transcript(graph, Path(args.transcript))
    out = Path(args.graph_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(graph, indent=2), encoding="utf-8")
    print(f"wrote {out} with {len(graph['objects'])} objects")


if __name__ == "__main__":
    main()
