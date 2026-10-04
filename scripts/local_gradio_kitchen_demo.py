from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    import gradio as gr
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"Gradio is not installed. Run: python -m pip install gradio\nImport error: {exc}")

from query_graph import answer

DEFAULT_GRAPH = "data/graphs/kitchen_graph.json"
DEFAULT_TRANSCRIPT = "artifacts/transcripts/kitchen_transcript.json"
SAFE_UNCERTAIN = "I am not certain. Please stop."


def load_json(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def graph_rows(graph: dict[str, Any]) -> list[list[Any]]:
    rows = []
    for obj in graph.get("objects", []):
        if not isinstance(obj, dict):
            continue
        rows.append([
            obj.get("object_id", ""),
            obj.get("object_type", ""),
            obj.get("semantic_label", ""),
            obj.get("location", ""),
            obj.get("confidence", ""),
            obj.get("uncertainty_status", ""),
            obj.get("source_timestamp", ""),
            obj.get("evidence_source", ""),
        ])
    return rows


def transcript_lines(transcript: dict[str, Any]) -> str:
    lines = []
    for seg in transcript.get("segments", []):
        lines.append(f"[{seg.get('start', 0):.2f}s → {seg.get('end', 0):.2f}s] {seg.get('text', '')}")
    return "\n".join(lines) if lines else "No transcript loaded."


def speak_local(text: str) -> str:
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
        return "Spoken locally."
    except Exception as exc:
        return f"TTS unavailable: {exc}"


def make_app(graph_path: str, transcript_path: str) -> gr.Blocks:
    graph = load_json(graph_path)
    transcript = load_json(transcript_path)
    rows = graph_rows(graph)
    transcript_text = transcript_lines(transcript)

    def ask(question: str, speak: bool) -> tuple[str, str]:
        q = (question or "").strip()
        if not q:
            result = SAFE_UNCERTAIN
        else:
            result = answer(graph, q)
        tts_status = "TTS not requested."
        if speak:
            tts_status = speak_local(result)
        return result, tts_status

    def preset(q: str) -> str:
        return q

    with gr.Blocks(title="Local Kitchen Memory Assistant") as demo:
        gr.Markdown(
            """
# 🍳 Local Kitchen Memory Assistant

Offline/local MVP for the kitchen guidance system.

Architecture: **PERCEPTION → MEMORY → DECISION → OUTPUT**

- Perception: extracted keyframes + local faster-whisper transcript
- Memory: local JSON Kitchen Knowledge Graph
- Decision: deterministic graph query logic
- Output: concise text first, optional local TTS

No kitchen images/video/transcripts are uploaded by this local app.
            """
        )

        with gr.Row():
            with gr.Column(scale=2):
                question = gr.Textbox(label="Ask a location question", value="Where is the kettle?")
                with gr.Row():
                    gr.Button("Glass").click(lambda: preset("Where is the glass?"), outputs=question)
                    gr.Button("Tea").click(lambda: preset("Where is the tea?"), outputs=question)
                    gr.Button("Kettle").click(lambda: preset("Where is the kettle?"), outputs=question)
                    gr.Button("Sugar").click(lambda: preset("Where is the sugar?"), outputs=question)
                    gr.Button("Spoon").click(lambda: preset("Where is the spoon?"), outputs=question)
                speak = gr.Checkbox(label="Speak answer locally with pyttsx3", value=False)
                ask_btn = gr.Button("Answer from local graph", variant="primary")
                response = gr.Textbox(label="Answer", lines=4)
                tts_status = gr.Textbox(label="TTS status", lines=1)
                ask_btn.click(ask, inputs=[question, speak], outputs=[response, tts_status])
            with gr.Column(scale=1):
                gr.Markdown("## Safety rule")
                gr.Textbox(value=SAFE_UNCERTAIN, label="If evidence is missing", interactive=False)
                gr.Markdown("## Local files")
                gr.Textbox(value=graph_path, label="Graph", interactive=False)
                gr.Textbox(value=transcript_path, label="Transcript", interactive=False)

        with gr.Tab("Kitchen Knowledge Graph"):
            gr.Dataframe(
                value=rows,
                headers=["object_id", "type", "label", "location", "confidence", "uncertainty", "timestamp", "source"],
                label="Graph facts",
                interactive=False,
                wrap=True,
            )

        with gr.Tab("Transcript evidence"):
            gr.Textbox(value=transcript_text, label="Timestamped transcript", lines=20, interactive=False)

        with gr.Tab("Demo script"):
            gr.Markdown(
                """
## Suggested presentation flow

1. Explain: the system first learned the kitchen from a narrated walkthrough video.
2. Show the transcript tab and graph tab.
3. Ask: **Where is the kettle?**
4. Ask: **Where is the sugar?**
5. Ask: **Where is the tea?** to demonstrate safe uncertainty.
6. Explain: if the graph lacks evidence, it refuses to guess and says: `I am not certain. Please stop.`

## Current known facts from transcript

- Glasses are mentioned around 18.10s.
- Kettle is mentioned around 27.84s and connected to power.
- Sugar is near two bottles and a mug around 39.90s.
- Tea and spoon were not found in reliable evidence, so answers are safe uncertainty.
                """
            )

    return demo


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local-only Gradio demo for kitchen graph Q&A.")
    parser.add_argument("--graph", default=DEFAULT_GRAPH)
    parser.add_argument("--transcript", default=DEFAULT_TRANSCRIPT)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--share", action="store_true", help="Do not use for private data unless explicitly intended")
    args = parser.parse_args()

    demo = make_app(args.graph, args.transcript)
    demo.launch(server_name=args.host, server_port=args.port, share=args.share)


if __name__ == "__main__":
    main()
