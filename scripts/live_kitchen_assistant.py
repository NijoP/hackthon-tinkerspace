from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import cv2
import numpy as np

from query_graph import answer as graph_answer
from audio_io import Microphone, Speaker, Transcriber, voice_turn, list_devices
from brain import build_brain

SAFE_UNCERTAIN = "I am not certain. Please stop."
VLM_STATE_PATH = "artifacts/live/vlm_reasoning.json"


def read_vision_summary(path: str = VLM_STATE_PATH) -> str | None:
    """Latest camera scene description from the local SmolVLM2 worker, if fresh."""
    try:
        state = json.loads(Path(path).read_text(encoding="utf-8"))
        obs = state.get("last_observation") or {}
        summary = obs.get("summary")
        return summary.strip() if isinstance(summary, str) and summary.strip() else None
    except Exception:
        return None


def graph_facts(graph: dict[str, Any]) -> str | None:
    """Compact 'label: location' list to give the brain trusted kitchen context."""
    parts = []
    for obj in (graph.get("objects") or []):
        label = obj.get("semantic_label") or obj.get("object_type")
        loc = obj.get("location")
        if label and loc:
            parts.append(f"{label}: {loc}")
    return "; ".join(parts[:12]) if parts else None


@dataclass
class AssistantState:
    user_name: str = "Jarvis"
    welcomed: bool = False
    current_task: str = "idle"
    tea_step: int = 0
    last_transcript: str = ""
    last_answer: str = ""
    last_person_seen_at: float | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    history: list[dict[str, str]] = field(default_factory=list)

    def remember(self, user_text: str, reply: str) -> None:
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": reply})
        self.history = self.history[-12:]

    def log(self, event: str, detail: str = "") -> None:
        item = {"time": time.strftime("%H:%M:%S"), "event": event, "detail": detail}
        self.events.append(item)
        self.events = self.events[-50:]
        print(f"[{item['time']}] {event}: {detail}")


def load_graph(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {"objects": []}
    return json.loads(p.read_text(encoding="utf-8"))


def fetch_latest_frame(url: str) -> np.ndarray | None:
    try:
        data = urlopen(url, timeout=1.0).read()
        arr = np.frombuffer(data, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return frame
    except Exception:
        return None


def detect_person_hog(frame: np.ndarray) -> tuple[bool, list[tuple[int, int, int, int]]]:
    # Classical local CPU person detector. Works best for upright humans; weak for unusual ESP camera angles.
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    resized = frame
    h, w = frame.shape[:2]
    if w > 640:
        scale = 640 / w
        resized = cv2.resize(frame, (640, int(h * scale)))
    boxes, weights = hog.detectMultiScale(resized, winStride=(8, 8), padding=(8, 8), scale=1.05)
    good = []
    for (x, y, bw, bh), weight in zip(boxes, weights):
        if float(weight) >= 0.35:
            good.append((int(x), int(y), int(bw), int(bh)))
    return bool(good), good


def detect_face_or_person(frame: np.ndarray) -> bool:
    # Face fallback helps when camera sees upper body/face but HOG misses full body.
    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        face_cascade = cv2.CascadeClassifier(cascade_path)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4, minSize=(40, 40))
        if len(faces) > 0:
            return True
    except Exception:
        pass
    found, _ = detect_person_hog(frame)
    return found


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower()).strip()


def intent_from_text(text: str) -> str:
    t = normalize(text)
    if any(phrase in t for phrase in ["make tea", "prepare tea", "want tea", "i want to make tea", "tea"]):
        return "make_tea"
    if t.startswith("where") or "where is" in t:
        return "where"
    if any(x in t for x in ["stop", "quit", "exit", "cancel"]):
        return "stop"
    if any(x in t for x in ["repeat", "again"]):
        return "repeat"
    return "unknown"


def tea_guidance(state: AssistantState, graph: dict[str, Any]) -> str:
    steps = [
        "First, locate the glass. " + graph_answer(graph, "Where is the glass?"),
        "Next, locate the kettle. " + graph_answer(graph, "Where is the kettle?"),
        "Now locate the sugar. " + graph_answer(graph, "Where is the sugar?"),
        "Please add water to the kettle only if you are sure it is safe and stable.",
        "Heat the water, then pour carefully. Stop if anything feels unsafe.",
        "Mix the drink carefully. The tea task guidance is complete."
    ]
    idx = min(state.tea_step, len(steps) - 1)
    text = steps[idx]
    state.tea_step += 1
    if state.tea_step >= len(steps):
        state.current_task = "idle"
        state.tea_step = 0
    return text


def decide(text: str, state: AssistantState, graph: dict[str, Any], brain=None, vision_summary: str | None = None) -> str:
    intent = intent_from_text(text)
    if intent == "stop":
        state.current_task = "idle"
        state.tea_step = 0
        return "Stopping current task. Please stay safe."
    if intent == "make_tea":
        state.current_task = "make_tea"
        state.tea_step = 0
        return "Okay. I will guide you to make tea. " + tea_guidance(state, graph)
    if intent == "where":
        ans = graph_answer(graph, text)
        # Graph is authoritative for locations. If it is uncertain, let the brain
        # try using the live camera view before giving up.
        if ans == SAFE_UNCERTAIN and brain is not None:
            try:
                return brain.answer(text, vision_summary=vision_summary,
                                    graph_facts=graph_facts(graph), history=state.history,
                                    user_name=state.user_name)
            except Exception:
                return ans
        return ans
    if intent == "repeat":
        return state.last_answer or SAFE_UNCERTAIN
    if state.current_task == "make_tea":
        return tea_guidance(state, graph)
    # General 'ask me anything' question -> Nemotron reasoning brain with context.
    if brain is not None:
        try:
            return brain.answer(text, vision_summary=vision_summary,
                                graph_facts=graph_facts(graph), history=state.history,
                                user_name=state.user_name)
        except Exception as exc:
            print(f"brain error: {type(exc).__name__}: {str(exc)[:160]}")
            return "Sorry, my reasoning service is not reachable right now. Please try again."
    return "I heard you, but I am not certain what task you want. You can say: I want to make tea."


def write_state(path: str, state: AssistantState) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "user_name": state.user_name,
        "welcomed": state.welcomed,
        "current_task": state.current_task,
        "tea_step": state.tea_step,
        "last_transcript": state.last_transcript,
        "last_answer": state.last_answer,
        "last_person_seen_at": state.last_person_seen_at,
        "events": state.events,
    }, indent=2), encoding="utf-8")


def keyboard_listen() -> str:
    return input("USER> ").strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Live local kitchen assistant: ESP camera trigger + mic transcription + graph decision + TTS.")
    parser.add_argument("--user-name", default="Jarvis")
    parser.add_argument("--frame-url", default="http://127.0.0.1:8000/api/latest.jpg")
    parser.add_argument("--graph", default="data/graphs/kitchen_graph.json")
    parser.add_argument("--state-out", default="artifacts/live/assistant_state.json")
    parser.add_argument("--whisper-model", default="small.en")
    parser.add_argument("--device", default=None, choices=["cuda", "cpu"], help="Whisper device (default: auto-detect)")
    parser.add_argument("--listen-seconds", type=float, default=15.0, help="Max utterance length for VAD recording")
    parser.add_argument("--poll-seconds", type=float, default=0.5)
    parser.add_argument("--mic-device", default=None, help="Input device index or name substring (default: system default)")
    parser.add_argument("--speaker-device", default=None, help="Output device index or name substring (default: system default)")
    parser.add_argument("--voice", default=None, help="TTS voice id/name substring, e.g. Zira or David")
    parser.add_argument("--rate", type=int, default=165, help="TTS speech rate (words per minute)")
    parser.add_argument("--no-earcons", action="store_true", help="Disable listening/done beeps")
    parser.add_argument("--list-devices", action="store_true", help="List audio devices and exit")
    parser.add_argument("--no-tts", action="store_true")
    parser.add_argument("--keyboard", action="store_true", help="Use typed input instead of microphone after welcome")
    parser.add_argument("--force-welcome", action="store_true", help="Skip person detection and start interaction immediately")
    parser.add_argument("--no-brain", action="store_true", help="Disable the Nemotron reasoning brain (kitchen-graph answers only)")
    args = parser.parse_args()

    if args.list_devices:
        print(list_devices())
        return

    state = AssistantState(user_name=args.user_name)
    graph = load_graph(args.graph)
    tts_enabled = not args.no_tts

    # Agent 3: the reasoning brain (NVIDIA Nemotron). Optional - the assistant
    # still answers kitchen/location questions from the graph without it.
    brain = None
    if not args.no_brain:
        brain = build_brain(user_name=args.user_name)
        if brain is not None:
            try:
                brain.validate()
                state.log("brain_ready", f"Nemotron reasoning brain online ({brain.model})")
            except Exception as exc:
                state.log("brain_unavailable", f"{type(exc).__name__}: {str(exc)[:160]}")
                brain = None
        else:
            state.log("brain_unavailable", "NVIDIA_API_KEY not set; using kitchen-graph answers only")

    # Build the laptop audio layer once (reused for the whole session).
    speaker = Speaker(
        enabled=tts_enabled,
        device=args.speaker_device,
        voice=args.voice,
        rate=args.rate,
        earcons=not args.no_earcons,
    )

    def speak(text: str) -> None:
        speaker.speak(text)

    use_mic = not args.keyboard
    mic = None
    transcriber = None
    if use_mic:
        if Microphone.available():
            mic = Microphone(device=args.mic_device, max_duration=args.listen_seconds)
            transcriber = Transcriber(model_name=args.whisper_model, device=args.device)
            state.log("audio_ready", f"mic+whisper({transcriber.model_name}/{transcriber.device}) ready")
            # Warm up the model so the first real turn is not slow/silent.
            print("Loading speech model (one-time)...")
            try:
                transcriber._load()  # noqa: SLF001 - intentional warmup
            except Exception as exc:
                state.log("whisper_warmup_failed", str(exc))
        else:
            use_mic = False
            state.log("mic_fallback", "sounddevice unavailable; using keyboard input")

    state.log("startup", "Live assistant loop started")
    write_state(args.state_out, state)

    if args.force_welcome:
        state.welcomed = True
        speak(f"Hey {state.user_name}, welcome to the kitchen. What are the things you planned for today?")

    while True:
        if not state.welcomed:
            frame = fetch_latest_frame(args.frame_url)
            if frame is not None and detect_face_or_person(frame):
                state.last_person_seen_at = time.time()
                state.welcomed = True
                state.log("person_detected", "Camera trigger fired")
                speak(f"Hey {state.user_name}, welcome to the kitchen. What are the things you planned for today?")
                write_state(args.state_out, state)
            else:
                time.sleep(args.poll_seconds)
                continue

        try:
            if not use_mic or mic is None or transcriber is None:
                text = keyboard_listen()
            else:
                text = voice_turn(mic, transcriber, speaker)
                if text is None:
                    # Nothing captured this turn (silence/timeout). Keep listening.
                    continue
        except KeyboardInterrupt:
            print()
            break
        except Exception as exc:
            state.log("listen_error", str(exc))
            text = keyboard_listen()

        if not text:
            # Heard noise but no words; prompt gently and loop.
            state.log("empty_transcript", "No words recognized")
            speak("Sorry, I did not catch that. Please say it again.")
            continue
        state.last_transcript = text
        state.log("user_said", text)
        vision_summary = read_vision_summary()
        reply = decide(text, state, graph, brain=brain, vision_summary=vision_summary)
        state.last_answer = reply
        state.remember(text, reply)
        state.log("assistant_reply", reply)
        speak(reply)
        write_state(args.state_out, state)

        if intent_from_text(text) == "stop":
            break


if __name__ == "__main__":
    main()
