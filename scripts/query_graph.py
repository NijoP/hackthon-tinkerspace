from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SAFE_UNCERTAIN = "I am not certain. Please stop."


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower()).strip()


def wanted_object(question: str) -> str | None:
    q = normalize(question)
    known = ["glass", "tea", "kettle", "sugar", "spoon", "cup", "bottle", "towel", "toaster", "oven", "microwave"]
    for item in known:
        if re.search(rf"\b{re.escape(item)}\b", q):
            return item
    m = re.search(r"where is the ([a-z0-9 ]+)", q)
    return m.group(1).strip() if m else None


def object_matches(obj: dict[str, Any], target: str) -> bool:
    target = normalize(target)
    fields = [
        normalize(str(obj.get("object_type", ""))),
        normalize(str(obj.get("semantic_label", ""))),
        normalize(str(obj.get("object_id", ""))),
    ]
    return any(re.search(rf"\b{re.escape(target)}\b", f) for f in fields)


def best_fact(graph: dict[str, Any], target: str) -> dict[str, Any] | None:
    candidates = [o for o in graph.get("objects", []) if isinstance(o, dict) and object_matches(o, target)]
    usable = []
    for o in candidates:
        loc = str(o.get("location", "unknown")).strip()
        status = str(o.get("uncertainty_status", "uncertain")).lower()
        try:
            conf = float(o.get("confidence", 0.0) or 0.0)
        except Exception:
            conf = 0.0
        if loc and loc.lower() != "unknown" and status != "unknown" and conf >= 0.5:
            usable.append((conf, o))
    if not usable:
        return None
    usable.sort(key=lambda x: x[0], reverse=True)
    return usable[0][1]


def answer(graph: dict[str, Any], question: str) -> str:
    target = wanted_object(question)
    if not target:
        return SAFE_UNCERTAIN
    fact = best_fact(graph, target)
    if not fact:
        return SAFE_UNCERTAIN
    loc = str(fact.get("location", "unknown")).strip()
    label = str(fact.get("semantic_label") or target).strip()
    status = str(fact.get("uncertainty_status", "uncertain")).lower()
    prefix = "I am not fully certain, but " if status == "uncertain" else ""
    verb = "are" if label.lower().endswith("s") and not label.lower().endswith("ss") else "is"
    prep = "" if loc.lower().startswith(("at ", "near ", "in ", "on ", "inside ")) else "at "
    return f"{prefix}the {label} {verb} {prep}{loc}."


def main() -> None:
    parser = argparse.ArgumentParser(description="Answer kitchen location questions using graph facts only.")
    parser.add_argument("question")
    parser.add_argument("--graph", default="data/graphs/kitchen_graph.json")
    args = parser.parse_args()

    path = Path(args.graph)
    if not path.exists():
        print(SAFE_UNCERTAIN)
        raise SystemExit(1)
    graph = json.loads(path.read_text(encoding="utf-8"))
    print(answer(graph, args.question))


if __name__ == "__main__":
    main()
