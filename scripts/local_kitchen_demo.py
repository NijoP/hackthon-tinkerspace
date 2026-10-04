from __future__ import annotations

import argparse
import json
from pathlib import Path

from query_graph import answer


def speak(text: str) -> None:
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
    except Exception as exc:
        print(f"[TTS unavailable: {exc}]")


def main() -> None:
    parser = argparse.ArgumentParser(description="Local-only kitchen Q&A demo using kitchen_graph.json.")
    parser.add_argument("--graph", default="data/graphs/kitchen_graph.json")
    parser.add_argument("--tts", action="store_true", help="Speak answers with local pyttsx3")
    args = parser.parse_args()

    graph_path = Path(args.graph)
    if not graph_path.exists():
        raise SystemExit(f"Graph not found: {graph_path}")
    graph = json.loads(graph_path.read_text(encoding="utf-8"))

    print("Local Kitchen Assistant. Type a question, or 'quit'.")
    print("Examples: Where is the glass? | Where is the kettle? | Where is the tea?")
    while True:
        try:
            q = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not q:
            continue
        if q.lower() in {"q", "quit", "exit"}:
            break
        text = answer(graph, q)
        print(text)
        if args.tts:
            speak(text)


if __name__ == "__main__":
    main()
