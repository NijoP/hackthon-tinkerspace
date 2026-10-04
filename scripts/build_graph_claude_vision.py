#!/usr/bin/env python3
"""Build the Kitchen Knowledge Graph from a frame-by-frame visual review of the walkthrough.

Source of truth for this graph:
  * Visual review: Claude (vision) inspected 52 frames sampled every 1.5 s across the
    77.8 s walkthrough video (contact sheets in artifacts/claude_vision/).
  * Narration: faster-whisper transcript (artifacts/transcripts/kitchen_transcript.json).

The visual review was done once, offline, as an authoring step. This script only encodes
those reviewed observations, extracts one evidence frame per object from the video, and
writes data/graphs/kitchen_graph.json. No cloud call happens here.

Spatial convention used in every location string:
  "Facing the counter" = standing at the counter, looking at the wall behind it.
  Left end = the corner nearest the door, with the switchboard and dish rack.
  Right end = the far corner under the wall fan, with the big water bottle and pink cloth.

Run:  .venv\\Scripts\\python.exe scripts\\build_graph_claude_vision.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
VIDEO_CANDIDATES = [
    ROOT / "WhatsApp Video 2026-10-03 at 22.46.42.mp4",
    ROOT.parent / "WhatsApp Video 2026-10-03 at 22.46.42.mp4",
]
GRAPH_PATH = ROOT / "data" / "graphs" / "kitchen_graph.json"
EVIDENCE_DIR = ROOT / "artifacts" / "kitchen_evidence"

CONFIRMED = "confirmed"      # seen clearly AND named in the narration
VISUAL = "visual"            # seen clearly, not named in the narration
UNCERTAIN = "uncertain"      # partly seen or inferred
UNKNOWN = "unknown"          # never shown

# Each entry: id, type, label, location (spoken form), status, confidence, best frame time,
# narration evidence (or None), visual evidence, relationships [(relation, other_label)].
OBJECTS = [
    dict(id="obj_kettle", type="kettle", label="electric kettle",
         location="on the counter, just right of the dish rack. It is a steel kettle with a black handle, plugged into the wall socket above the dish rack",
         status=CONFIRMED, conf=0.97, t=30.0,
         said="If you move here, we have the kettle. The kettle is connected to the power.",
         seen="Stainless steel electric kettle with black handle and lid button on a black base, cord running to the socket above the dish rack.",
         rel=[("RIGHT_OF", "dish rack"), ("LEFT_OF", "sugar jar"), ("ON", "kitchen counter")]),
    dict(id="obj_kettle_switch", type="switch", label="kettle power switch",
         location="on the wall above the left end of the counter, behind the dish rack. Press the switch down to turn the kettle on",
         status=CONFIRMED, conf=0.9, t=33.0,
         said="Connected to the power and turn down and this makes it turn on.",
         seen="Wall switchboard with the kettle plug; the narrator presses the switch beside the plug.",
         rel=[("BEHIND", "dish rack"), ("NEAR", "electric kettle")]),
    dict(id="obj_sugar_jar", type="sugar", label="sugar jar",
         location="on the counter, right of the kettle. It is the first of two jars, clear with a brown lid, holding white sugar with a spoon inside",
         status=CONFIRMED, conf=0.95, t=43.5,
         said="This is sugar.",
         seen="Clear plastic jar, brown screw lid, white granulated sugar, a steel spoon standing inside.",
         rel=[("RIGHT_OF", "electric kettle"), ("LEFT_OF", "coffee jar"), ("NEXT_TO", "coffee jar")]),
    dict(id="obj_coffee_jar", type="coffee", label="coffee jar",
         location="on the counter, right of the sugar jar. It is the second jar with a brown lid, holding dark coffee powder with a spoon inside",
         status=CONFIRMED, conf=0.95, t=46.5,
         said="You can see this is coffee.",
         seen="Clear jar with brown lid, filled with dark brown coffee powder, a spoon inside.",
         rel=[("RIGHT_OF", "sugar jar"), ("LEFT_OF", "glass water jug")]),
    dict(id="obj_spoon", type="spoon", label="spoons",
         location="inside the jars. One spoon is in the sugar jar and one is in the coffee jar",
         status=VISUAL, conf=0.85, t=43.5,
         said=None,
         seen="A steel spoon is visible inside the sugar jar when lifted at 43.5 s, and inside the coffee jar at 46.5 s.",
         rel=[("INSIDE", "sugar jar"), ("INSIDE", "coffee jar")]),
    dict(id="obj_water_jug", type="jug", label="glass water jug",
         location="on the counter, right of the coffee jar. It is a clear glass jug with a handle and a lid, used for water",
         status=CONFIRMED, conf=0.88, t=51.0,
         said="It will be filled with water. When you are making coffee you take water.",
         seen="Clear patterned glass jug with handle and lid; the narrator lifts it while talking about water.",
         rel=[("RIGHT_OF", "coffee jar"), ("LEFT_OF", "large water bottle")]),
    dict(id="obj_water_bottle", type="water", label="large water bottle",
         location="on the counter toward the right end, against the wall, right of the glass jug. It is a big clear bottle with a green cap and handle, for more drinking water",
         status=CONFIRMED, conf=0.9, t=48.0,
         said="More water there.",
         seen="Large clear plastic water bottle, about five litres, green cap with a carry handle.",
         rel=[("RIGHT_OF", "glass water jug"), ("NEAR", "pink cloth")]),
    dict(id="obj_dish_rack", type="dish rack", label="dish rack",
         location="on the counter at the left end, between the tissue box and the kettle",
         status=VISUAL, conf=0.95, t=19.5,
         said=None,
         seen="Black metal two-tier dish rack: plates upright on top, glasses and mugs below, green-handled cutlery holder on its right side.",
         rel=[("LEFT_OF", "electric kettle"), ("RIGHT_OF", "tissue box"), ("ON", "kitchen counter")]),
    dict(id="obj_glass_cup", type="glass", label="drinking glasses",
         location="in the dish rack, on the lower shelf at the left side. There are about four clear glasses, upside down",
         status=CONFIRMED, conf=0.93, t=25.5,
         said="Here you can see we can find glasses here. We'll be using one of these glasses for making coffee.",
         seen="Clear drinking glasses on the lower tier of the dish rack, left of the black mugs. At 63 s one glass is taken out and placed in front of the kettle.",
         rel=[("INSIDE", "dish rack"), ("LEFT_OF", "black mugs")]),
    dict(id="obj_mug_cup", type="mug", label="black mugs",
         location="in the dish rack, on the lower shelf at the right side, next to the glasses",
         status=VISUAL, conf=0.9, t=22.5,
         said=None,
         seen="Several black ceramic mugs with a light rim on the lower tier of the dish rack.",
         rel=[("INSIDE", "dish rack"), ("RIGHT_OF", "drinking glasses")]),
    dict(id="obj_plates", type="plate", label="white plates",
         location="standing upright on the top shelf of the dish rack",
         status=VISUAL, conf=0.92, t=19.5,
         said=None,
         seen="Five or six white plates standing in the top tier of the dish rack.",
         rel=[("ON", "dish rack")]),
    dict(id="obj_tissues", type="tissues", label="tissue box",
         location="on the counter at the far left end, in the corner against the wall, left of the dish rack",
         status=CONFIRMED, conf=0.92, t=28.5,
         said="You can use tissues here.",
         seen="Colourful printed tissue box with a tissue pulled up, in the left corner of the counter.",
         rel=[("LEFT_OF", "dish rack"), ("ON", "kitchen counter")]),
    dict(id="obj_pink_cloth", type="cloth", label="pink cloth",
         location="on the counter at the far right end, in the corner",
         status=VISUAL, conf=0.85, t=10.5,
         said=None,
         seen="Pink or magenta hand cloth lying on the right end of the counter.",
         rel=[("NEAR", "large water bottle")]),
    dict(id="obj_small_jar", type="jar", label="small brown jar",
         location="on the counter at the right end, behind the water bottle near the pink cloth. Its contents were not shown",
         status=UNCERTAIN, conf=0.55, t=10.5,
         said=None,
         seen="A third brown container partly hidden behind the water bottle; never opened or named.",
         rel=[("BEHIND", "large water bottle")]),
    dict(id="obj_counter", type="counter", label="kitchen counter",
         location="along the left wall as you walk in. It has a black stone top with white cabinets below",
         status=VISUAL, conf=0.97, t=6.0,
         said=None,
         seen="Long black granite counter with white cabinet doors underneath.",
         rel=[]),
    dict(id="obj_cupboard", type="cupboard", label="cupboard",
         location="below the counter. These are the white cabinet doors under the counter top",
         status=UNCERTAIN, conf=0.7, t=6.0,
         said="As you can see, there is a cupboard in this area.",
         seen="White under-counter cabinets are the only cupboards visible while the narrator says this.",
         rel=[("SAME_ZONE", "kitchen counter")]),
    dict(id="obj_wall_fan", type="fan", label="wall fan",
         location="high on the back wall, above the right end of the counter",
         status=VISUAL, conf=0.93, t=15.0,
         said=None,
         seen="White wall-mounted fan with a switch box below it.",
         rel=[]),
    dict(id="obj_camera_mount", type="camera position", label="camera mounting spot",
         location="planned to be clipped high near the wall fan, pointing down at the counter",
         status=UNCERTAIN, conf=0.6, t=15.0,
         said="We'll be clipping the camera over there somewhere pointing downwards. Camera over there.",
         seen="The narrator points up toward the wall near the fan while describing the camera position.",
         rel=[("NEAR", "wall fan")]),
    dict(id="obj_chairs", type="chair", label="two black chairs",
         location="on the other side of the room from the counter, near the back wall",
         status=CONFIRMED, conf=0.9, t=73.5,
         said="Chair if in case.",
         seen="Two black mesh chairs facing into the room; one has a brown paper bag on it.",
         rel=[]),
    dict(id="obj_paper_bag", type="bag", label="brown paper bag",
         location="on the seat of the chair nearest the door, with a food box inside",
         status=VISUAL, conf=0.75, t=73.5,
         said=None,
         seen="Brown paper bag holding a white food container, resting on a chair.",
         rel=[("ON", "two black chairs")]),
    dict(id="obj_tea", type="tea", label="tea",
         location="unknown. Tea was not shown in the walkthrough; the routine shown is for coffee",
         status=UNKNOWN, conf=0.0, t=None,
         said=None, seen="No tea, tea bags or tea leaves appear in any sampled frame.",
         rel=[]),
]

COFFEE_ROUTINE = [
    {"step": 1, "say": "Take water from the glass water jug or the large water bottle.", "objects": ["glass water jug", "large water bottle"], "narration_t": 52.8},
    {"step": 2, "say": "Open the kettle lid.", "objects": ["electric kettle"], "narration_t": 54.8},
    {"step": 3, "say": "Pour the water into the kettle and close it.", "objects": ["electric kettle"], "narration_t": 56.9},
    {"step": 4, "say": "Turn the kettle on with the switch above the dish rack and let it heat.", "objects": ["kettle power switch"], "narration_t": 58.9},
    {"step": 5, "say": "Take one glass from the lower shelf of the dish rack.", "objects": ["drinking glasses"], "narration_t": 60.9},
    {"step": 6, "say": "Add coffee and sugar with the spoons in each jar, then mix.", "objects": ["coffee jar", "sugar jar", "spoons"], "narration_t": 62.9},
]


def find_video() -> Path:
    for p in VIDEO_CANDIDATES:
        if p.exists():
            return p
    raise SystemExit("Walkthrough video not found.")


def extract_evidence(video: Path) -> dict[float, str]:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video))
    out: dict[float, str] = {}
    for t in sorted({o["t"] for o in OBJECTS if o["t"] is not None}):
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            continue
        name = f"evidence_{t:05.1f}s.jpg"
        cv2.imwrite(str(EVIDENCE_DIR / name), frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
        out[t] = name
    cap.release()
    return out


def main() -> None:
    video = find_video()
    frames = extract_evidence(video)
    objects = []
    for o in OBJECTS:
        sources = ["claude-vision frame review"] + (["faster-whisper narration"] if o["said"] else [])
        objects.append({
            "object_id": o["id"],
            "object_type": o["type"],
            "semantic_label": o["label"],
            "location": o["location"],
            "relationships": [
                {"subject": o["label"], "relation": r, "object": other, "confidence": round(min(o["conf"], 0.95), 2),
                 "evidence_frame": frames.get(o["t"]), "source_timestamp": o["t"]}
                for r, other in o["rel"]
            ],
            "confidence": o["conf"],
            "uncertainty_status": o["status"],
            "evidence_type": "visual+narration" if o["said"] and o["status"] == CONFIRMED else ("visual" if o["status"] != UNKNOWN else "none"),
            "evidence_frame": frames.get(o["t"]),
            "evidence_image": f"/kitchen-evidence/{frames[o['t']]}" if o["t"] in frames else None,
            "source_timestamp": o["t"],
            "evidence_source": " + ".join(sources),
            "evidence_text": o["said"],
            "visual_evidence": o["seen"],
        })
    graph = {
        "schema_version": "0.3",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source_video": video.name,
        "method": "Claude vision review of 52 frames (every 1.5 s) fused with the faster-whisper narration transcript.",
        "transcript": "artifacts\\transcripts\\kitchen_transcript.json",
        "spatial_convention": "Facing the counter: left end is the corner nearest the door (switchboard, tissue box, dish rack); right end is the far corner under the wall fan (water bottle, pink cloth).",
        "counter_order_left_to_right": ["tissue box", "dish rack", "electric kettle", "sugar jar", "coffee jar", "glass water jug", "large water bottle", "pink cloth"],
        "relations_allowed": ["LEFT_OF", "RIGHT_OF", "NEAR", "NEXT_TO", "ON", "INSIDE", "BEHIND", "IN_FRONT_OF", "SAME_ZONE"],
        "routines": {"make_coffee": COFFEE_ROUTINE},
        "notes": [
            "The narrated walkthrough demonstrates making coffee, not tea. Tea is recorded as unknown.",
            "The transcript phrase 'two bottles and a mug' is a speech-recognition error; the video shows two jars (sugar and coffee).",
        ],
        "objects": objects,
    }
    GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    GRAPH_PATH.write_text(json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(objects)} objects to {GRAPH_PATH}")
    print(f"Evidence frames: {len(frames)} in {EVIDENCE_DIR}")


if __name__ == "__main__":
    main()
