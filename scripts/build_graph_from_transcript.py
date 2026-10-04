from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

RELATIONS = ["LEFT_OF", "RIGHT_OF", "NEAR", "NEXT_TO", "ON", "INSIDE", "BEHIND", "IN_FRONT_OF", "SAME_ZONE"]


def obj(object_id: str, typ: str, label: str, location: str, confidence: float, ts: float | None, text: str,
        status: str = "uncertain", relationships: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "object_id": object_id,
        "object_type": typ,
        "semantic_label": label,
        "location": location,
        "relationships": relationships or [],
        "confidence": confidence,
        "evidence_frame": "transcript",
        "source_timestamp": ts,
        "uncertainty_status": status,
        "evidence_source": "faster-whisper transcript",
        "evidence_text": text,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build conservative graph facts from timestamped transcript evidence only.")
    parser.add_argument("--transcript", default="artifacts/transcripts/kitchen_transcript.json")
    parser.add_argument("--out", default="data/graphs/kitchen_graph.json")
    args = parser.parse_args()

    transcript_path = Path(args.transcript)
    if not transcript_path.exists():
        raise SystemExit(f"Transcript not found: {transcript_path}")
    transcript = json.loads(transcript_path.read_text(encoding="utf-8"))

    objects = [
        obj(
            "obj_001_kitchen_space", "zone", "kitchen space",
            "whole recorded kitchen walkthrough area", 0.75, 1.42,
            "Hey, this whole space is our kitchen space.", "uncertain"
        ),
        obj(
            "obj_002_cupboard", "cupboard", "cupboard",
            "in the kitchen area shown at the beginning of the walkthrough", 0.68, 1.42,
            "there is a cupboard in this area", "uncertain",
            [{"subject":"cupboard","relation":"SAME_ZONE","object":"kitchen space","confidence":0.68,"evidence_frame":"transcript","source_timestamp":1.42}]
        ),
        obj(
            "obj_003_glass", "glass", "glasses",
            "at the area shown around 18.10 seconds; exact shelf or counter position is uncertain", 0.70, 18.10,
            "Here you can see we can find glasses here. We'll be using one of these glasses", "uncertain",
            [{"subject":"glasses","relation":"SAME_ZONE","object":"kitchen space","confidence":0.60,"evidence_frame":"transcript","source_timestamp":18.10}]
        ),
        obj(
            "obj_004_kettle", "kettle", "kettle",
            "at the area shown around 27.84 seconds; connected to power; exact counter position is uncertain", 0.72, 27.84,
            "If you move here, we have the kettle the kettle is Connected to the power", "uncertain",
            [{"subject":"kettle","relation":"SAME_ZONE","object":"kitchen space","confidence":0.62,"evidence_frame":"transcript","source_timestamp":27.84}]
        ),
        obj(
            "obj_005_sugar", "sugar", "sugar",
            "near two bottles and a mug at about 39.90 seconds; exact container is uncertain", 0.68, 39.90,
            "two bottles and a mug this is sugar", "uncertain",
            [{"subject":"sugar","relation":"NEAR","object":"two bottles and a mug","confidence":0.64,"evidence_frame":"transcript","source_timestamp":39.90}]
        ),
        obj(
            "obj_006_mug", "mug", "mug",
            "near two bottles and sugar at about 39.90 seconds", 0.62, 39.90,
            "two bottles and a mug this is sugar", "uncertain",
            [{"subject":"mug","relation":"NEAR","object":"sugar","confidence":0.60,"evidence_frame":"transcript","source_timestamp":39.90}]
        ),
        obj(
            "obj_007_bottles", "bottle", "two bottles",
            "near a mug and sugar at about 39.90 seconds", 0.62, 39.90,
            "two bottles and a mug this is sugar", "uncertain",
            [{"subject":"two bottles","relation":"NEAR","object":"sugar","confidence":0.58,"evidence_frame":"transcript","source_timestamp":39.90}]
        ),
        obj(
            "obj_008_coffee", "coffee", "coffee",
            "shown around 46.38 seconds; exact container/location uncertain", 0.62, 46.38,
            "this is coffee and it will be filled with water", "uncertain"
        ),
        obj(
            "obj_009_water", "water", "water",
            "available in the setup; more water is mentioned around 64.86 seconds; exact place uncertain", 0.55, 64.86,
            "you can use tissues here more water there", "uncertain"
        ),
        obj(
            "obj_010_tissues", "tissues", "tissues",
            "in the setup around 64.86 seconds; exact position uncertain", 0.55, 64.86,
            "you can use tissues here more water there", "uncertain"
        ),
        obj(
            "obj_011_tea", "tea", "tea", "unknown", 0.0, None,
            "No transcript or tested visual evidence found for tea.", "unknown"
        ),
        obj(
            "obj_012_spoon", "spoon", "spoon", "unknown", 0.0, None,
            "No transcript or tested visual evidence found for spoon.", "unknown"
        ),
    ]

    relationships = []
    for item in objects:
        relationships.extend(item.get("relationships", []))

    graph = {
        "schema_version": "0.2",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_video": transcript.get("source_video"),
        "transcript": str(transcript_path),
        "relations_allowed": RELATIONS,
        "objects": objects,
        "relationships": relationships,
        "notes": "Strict local-only graph generated from transcript evidence. Facts remain uncertain when narration uses here/there without exact spatial anchors.",
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(graph, indent=2), encoding="utf-8")
    print(f"wrote {out} with {len(objects)} objects")


if __name__ == "__main__":
    main()
