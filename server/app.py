from __future__ import annotations

import asyncio
import json
import os
import re
import socket
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

try:
    from server import audio_control
except Exception:  # pragma: no cover - allow running as a loose script
    import audio_control  # type: ignore


@dataclass
class LatestFrameStore:
    lock: threading.Lock = field(default_factory=threading.Lock)
    frame: Optional[bytes] = None
    frame_id: int = 0
    received_at: Optional[float] = None
    source: str = "none"
    metadata: dict = field(default_factory=dict)

    def update(self, frame: bytes, source: str = "esp32", metadata: Optional[dict] = None) -> dict:
        now = time.time()
        with self.lock:
            self.frame = frame
            self.frame_id += 1
            self.received_at = now
            self.source = source
            self.metadata = metadata or {}
            return {
                "ok": True,
                "frame_id": self.frame_id,
                "received_at": self.received_at,
                "size_bytes": len(frame),
            }

    def snapshot(self) -> tuple[Optional[bytes], int, Optional[float], str, dict]:
        with self.lock:
            return self.frame, self.frame_id, self.received_at, self.source, dict(self.metadata)


app = FastAPI(title="AI Kitchen Assistant", version="0.2.0")
frames = LatestFrameStore()
mobile_frames = LatestFrameStore()
mobile_websocket_clients: dict[WebSocket, asyncio.Queue[bytes]] = {}
started_at = time.time()
PROJECT_ROOT = Path(__file__).resolve().parents[1]
GRAPH_PATH = PROJECT_ROOT / "data" / "graphs" / "kitchen_graph.json"
ASSISTANT_STATE_PATH = PROJECT_ROOT / "artifacts" / "live" / "assistant_state.json"
VLM_STATE_PATH = PROJECT_ROOT / "artifacts" / "live" / "vlm_reasoning.json"
MOBILE_FRAME_DIR = PROJECT_ROOT / "artifacts" / "mobile_frames"
MOBILE_FRAME_DIR.mkdir(parents=True, exist_ok=True)
SAFE_UNCERTAIN = "I am not certain. Please stop."

DASHBOARD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dashboard"))
if os.path.isdir(DASHBOARD_DIR):
    app.mount("/dashboard", StaticFiles(directory=DASHBOARD_DIR, html=True), name="dashboard")

# Walkthrough keyframes: visual evidence behind kitchen-memory facts (read-only).
EVIDENCE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "artifacts", "keyframes_quality"))
if os.path.isdir(EVIDENCE_DIR):
    app.mount("/evidence", StaticFiles(directory=EVIDENCE_DIR), name="evidence")

# Per-object evidence frames chosen during the Claude vision review of the walkthrough.
KITCHEN_EVIDENCE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "artifacts", "kitchen_evidence"))
os.makedirs(KITCHEN_EVIDENCE_DIR, exist_ok=True)
app.mount("/kitchen-evidence", StaticFiles(directory=KITCHEN_EVIDENCE_DIR), name="kitchen-evidence")

MOBILE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mobile"))
if os.path.isdir(MOBILE_DIR):
    app.mount("/mobile", StaticFiles(directory=MOBILE_DIR, html=True), name="mobile")


def lan_ip() -> str:
    """Best-effort local LAN IP discovery without contacting the internet."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


def camera_connected(timeout_seconds: float = 3.0) -> bool:
    _, _, received_at, _, _ = frames.snapshot()
    return received_at is not None and (time.time() - received_at) <= timeout_seconds


MOBILE_LATEST_PATH = MOBILE_FRAME_DIR / "mobile_latest.jpg"


def latest_mobile_file() -> Optional[Path]:
    if MOBILE_LATEST_PATH.exists():
        return MOBILE_LATEST_PATH
    files = sorted(MOBILE_FRAME_DIR.glob("mobile_*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def mobile_disk_snapshot() -> tuple[Optional[Path], Optional[float], int]:
    path = latest_mobile_file()
    if path is None:
        return None, None, 0
    try:
        stat = path.stat()
        return path, stat.st_mtime, stat.st_size
    except OSError:
        return None, None, 0


def mobile_connected(timeout_seconds: float = 3.0) -> bool:
    _, _, received_at, _, _ = mobile_frames.snapshot()
    disk_path, disk_received_at, _ = mobile_disk_snapshot()
    latest = received_at if received_at is not None else disk_received_at
    return latest is not None and (time.time() - latest) <= timeout_seconds


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", str(text).lower()).strip()


def wanted_object(question: str) -> str | None:
    q = normalize(question)
    for item in ["glass", "tea", "kettle", "sugar", "spoon", "cup", "mug", "bottle", "coffee", "water", "tissues"]:
        if re.search(rf"\b{re.escape(item)}\b", q):
            return item
    m = re.search(r"where is the ([a-z0-9 ]+)", q)
    return m.group(1).strip() if m else None


def object_matches(obj: dict, target: str) -> bool:
    target = normalize(target)
    fields = [normalize(obj.get("object_type", "")), normalize(obj.get("semantic_label", "")), normalize(obj.get("object_id", ""))]
    return any(re.search(rf"\b{re.escape(target)}\b", field) for field in fields)


def load_graph() -> dict:
    if not GRAPH_PATH.exists():
        return {"objects": [], "relationships": [], "error": f"Graph not found: {GRAPH_PATH}"}
    try:
        return json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"objects": [], "relationships": [], "error": str(exc)}


def answer_from_graph(graph: dict, question: str) -> str:
    target = wanted_object(question)
    if not target:
        return SAFE_UNCERTAIN
    candidates = []
    for obj in graph.get("objects", []):
        if not isinstance(obj, dict) or not object_matches(obj, target):
            continue
        loc = str(obj.get("location", "unknown")).strip()
        status = str(obj.get("uncertainty_status", "uncertain")).lower()
        try:
            conf = float(obj.get("confidence", 0.0) or 0.0)
        except Exception:
            conf = 0.0
        if loc and loc.lower() != "unknown" and status != "unknown" and conf >= 0.5:
            candidates.append((conf, obj))
    if not candidates:
        return SAFE_UNCERTAIN
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    obj = candidates[0][1]
    label = str(obj.get("semantic_label") or target)
    loc = str(obj.get("location"))
    status = str(obj.get("uncertainty_status", "uncertain")).lower()
    prefix = "I am not fully certain, but " if status == "uncertain" else ""
    verb = "are" if label.lower().endswith("s") and not label.lower().endswith("ss") else "is"
    prep = "" if loc.lower().startswith(("at ", "near ", "in ", "on ", "inside ")) else "at "
    sentence = f"{prefix}the {label} {verb} {prep}{loc.rstrip('.')}."
    return sentence[0].upper() + sentence[1:]


# --------------------------------------------------------------------------- #
# Agent 3: reasoning brain (NVIDIA Nemotron) for dashboard "ask anything" chat.
# --------------------------------------------------------------------------- #
import sys as _sys

_SCRIPTS_DIR = str(PROJECT_ROOT / "scripts")
if _SCRIPTS_DIR not in _sys.path:
    _sys.path.insert(0, _SCRIPTS_DIR)

_BRAIN = None


def get_brain():
    """Lazily build the brain. Retries while no key is set so the dashboard works
    as soon as NVIDIA_API_KEY is added to .env (no server restart needed)."""
    global _BRAIN
    if _BRAIN is not None:
        return _BRAIN
    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env", override=True)
    except Exception:
        pass
    try:
        from brain import NemotronBrain
        _BRAIN = NemotronBrain()
    except Exception:
        _BRAIN = None
    return _BRAIN


def brain_vision_summary() -> Optional[str]:
    try:
        state = json.loads(VLM_STATE_PATH.read_text(encoding="utf-8"))
        summary = (state.get("last_observation") or {}).get("summary")
        return summary.strip() if isinstance(summary, str) and summary.strip() else None
    except Exception:
        return None


def brain_graph_facts(graph: dict) -> Optional[str]:
    parts = []
    for obj in (graph.get("objects") or []):
        label = obj.get("semantic_label") or obj.get("object_type")
        loc = obj.get("location")
        if label and loc and obj.get("uncertainty_status") != "unknown":
            parts.append(f"{label}: {loc}")
    order = graph.get("counter_order_left_to_right")
    if order:
        parts.insert(0, "Counter items from left to right: " + ", ".join(order))
    for note in graph.get("notes") or []:
        parts.append(note)
    return "; ".join(parts[:30]) if parts else None


@app.get("/", response_class=HTMLResponse)
def root() -> str:
    return """
    <html><head><title>AI Kitchen Assistant</title></head>
    <body style='font-family:Segoe UI,Arial,sans-serif'>
      <h1>AI Kitchen Assistant</h1>
      <p><a href='/dashboard/'>Open live dashboard</a></p>
      <p><a href='/mobile/'>Open mobile camera uploader</a></p>
      <p><a href='/health'>Health</a> | <a href='/status'>Status</a> | <a href='/api/stream'>ESP32 MJPEG stream</a></p>
    </body></html>
    """


@app.get("/mobile-ca.crt")
def mobile_ca_certificate() -> Response:
    ca_path = PROJECT_ROOT / "certs" / "laptop-ca.crt"
    if not ca_path.exists():
        return Response(status_code=404)
    return Response(content=ca_path.read_bytes(), media_type="application/x-x509-ca-cert", headers={"Content-Disposition": "attachment; filename=laptop-ca.crt"})


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "ai-kitchen-assistant", "version": "0.2.0"}


@app.get("/status")
def status() -> dict:
    frame, frame_id, received_at, source, metadata = frames.snapshot()
    mobile_frame, mobile_frame_id, mobile_received_at, mobile_source, mobile_metadata = mobile_frames.snapshot()
    mobile_disk_path, mobile_disk_received_at, mobile_disk_size = mobile_disk_snapshot()
    now = time.time()
    age_ms = None if received_at is None else int((now - received_at) * 1000)
    mobile_received_at = mobile_received_at or mobile_disk_received_at
    mobile_age_ms = None if mobile_received_at is None else int((now - mobile_received_at) * 1000)
    mobile_is_fresh = mobile_age_ms is not None and mobile_age_ms <= 3000
    if mobile_frame is None and mobile_disk_path is not None:
        mobile_frame_id = int(mobile_disk_path.stat().st_mtime_ns // 1_000_000)
        mobile_source = "mobile-disk"
        mobile_metadata = {"path": str(mobile_disk_path)}
    return {
        "server": "RUNNING",
        "server_host": os.getenv("SERVER_HOST", "0.0.0.0"),
        "server_port": int(os.getenv("SERVER_PORT", "8000")),
        "lan_ip": lan_ip(),
        "dashboard_url": f"http://{lan_ip()}:{int(os.getenv('SERVER_PORT', '8000'))}/dashboard/",
        "camera": "CONNECTED" if camera_connected() else "OFFLINE",
        "mobile_camera": "CONNECTED" if mobile_connected() else "OFFLINE",
        "ai": "READY" if GRAPH_PATH.exists() else "NO_GRAPH",
        "microphone": audio_control.microphone_status(),
        "speaker": audio_control.speaker_status(),
        "latest_frame": {
            "available": frame is not None,
            "frame_id": frame_id,
            "age_ms": age_ms,
            "source": source,
            "size_bytes": 0 if frame is None else len(frame),
            "metadata": metadata,
        },
        "latest_mobile_frame": {
            "available": mobile_is_fresh,
            "frame_id": mobile_frame_id,
            "age_ms": mobile_age_ms,
            "source": mobile_source,
            "size_bytes": (len(mobile_frame) if mobile_frame is not None else mobile_disk_size) if mobile_is_fresh else 0,
            "metadata": mobile_metadata,
        },
        "live_assistant": "RUNNING" if ASSISTANT_STATE_PATH.exists() else "NOT_STARTED",
        "uptime_seconds": int(now - started_at),
    }


@app.post("/api/frame")
async def upload_frame(request: Request, file: UploadFile | None = File(default=None)) -> Response:
    """Receive the newest JPEG frame.

    Supports multipart field `file` or raw `image/jpeg` body. The server stores
    only the latest frame and intentionally drops older frames.
    """
    if file is not None:
        payload = await file.read()
    else:
        payload = await request.body()

    if not payload:
        return JSONResponse({"ok": False, "error": "empty frame"}, status_code=400)

    metadata = {
        "device_id": request.headers.get("X-Device-Id", "esp32-camera"),
        "device_frame_count": request.headers.get("X-Frame-Count"),
        "capture_millis": request.headers.get("X-Capture-Millis"),
        "content_type": request.headers.get("Content-Type"),
        "client_host": request.client.host if request.client else None,
    }
    frames.update(payload, metadata=metadata)
    return Response(status_code=204)


def jpeg_response(store: LatestFrameStore, disk_fallback: bool = False) -> Response:
    frame, frame_id, received_at, _, _ = store.snapshot()
    if frame is None and disk_fallback:
        path = latest_mobile_file()
        if path is not None:
            try:
                frame = path.read_bytes()
                frame_id = int(path.stat().st_mtime_ns // 1_000_000)
                received_at = path.stat().st_mtime
            except OSError:
                frame = None
    if frame is None:
        return Response(status_code=404)
    return Response(
        content=frame,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "X-Frame-Id": str(frame_id),
            "X-Frame-Age-Ms": "0" if received_at is None else str(int((time.time() - received_at) * 1000)),
        },
    )


@app.get("/api/latest.jpg")
def latest_jpeg() -> Response:
    return jpeg_response(frames)


@app.get("/api/mobile/latest.jpg")
def mobile_latest_jpeg() -> Response:
    return jpeg_response(mobile_frames, disk_fallback=True)


async def _relay_latest_frames(websocket: WebSocket, queue: asyncio.Queue[bytes]) -> None:
    try:
        while True:
            payload = await queue.get()
            await websocket.send_bytes(payload)
    except Exception:
        mobile_websocket_clients.pop(websocket, None)


def _write_latest_mobile_file(payload: bytes) -> None:
    """Atomically overwrite the single latest-frame file (read by the :8000 process / VLM)."""
    latest_tmp = MOBILE_FRAME_DIR / "mobile_latest.tmp.jpg"
    try:
        latest_tmp.write_bytes(payload)
        latest_tmp.replace(MOBILE_LATEST_PATH)
    except OSError:
        pass


_disk_write_pending = False


async def _write_latest_mobile_file_async(payload: bytes) -> None:
    """Off-event-loop disk write; skips if a write is already in flight (latest wins)."""
    global _disk_write_pending
    if _disk_write_pending:
        return
    _disk_write_pending = True
    try:
        await asyncio.to_thread(_write_latest_mobile_file, payload)
    finally:
        _disk_write_pending = False


@app.websocket("/ws/mobile")
async def mobile_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=1)
    mobile_websocket_clients[websocket] = queue
    sender = asyncio.create_task(_relay_latest_frames(websocket, queue))
    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            payload = message.get("bytes")
            if not payload:
                continue
            metadata = {
                "device_id": websocket.headers.get("X-Device-Id", "mobile-camera"),
                "content_type": "image/jpeg",
                "client_host": websocket.client.host if websocket.client else None,
            }
            mobile_frames.update(payload, source="mobile-websocket", metadata=metadata)
            # Disk fallback for the HTTP :8000 process, written off the event loop.
            asyncio.create_task(_write_latest_mobile_file_async(payload))
            for client, client_queue in list(mobile_websocket_clients.items()):
                if client is websocket:
                    continue
                if client_queue.full():
                    try:
                        client_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                try:
                    client_queue.put_nowait(payload)
                except asyncio.QueueFull:
                    pass
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        mobile_websocket_clients.pop(websocket, None)
        sender.cancel()


# --------------------------------------------------------------------------- #
# WebRTC signaling: phone (publisher) <-> dashboard (viewers), peer-to-peer on LAN.
# The server only relays SDP/ICE JSON; video never touches Python.
# --------------------------------------------------------------------------- #
rtc_publisher: dict = {"ws": None}
rtc_viewers: dict[str, WebSocket] = {}


async def _rtc_send(ws: Optional[WebSocket], message: dict) -> None:
    if ws is None:
        return
    try:
        await ws.send_text(json.dumps(message))
    except Exception:
        pass


@app.websocket("/ws/signal")
async def rtc_signal(websocket: WebSocket) -> None:
    await websocket.accept()
    role = websocket.query_params.get("role", "viewer")
    peer_id = f"v{int(time.time() * 1000)}_{id(websocket) % 10000}"
    if role == "publisher":
        old = rtc_publisher["ws"]
        rtc_publisher["ws"] = websocket
        if old is not None and old is not websocket:
            try:
                await old.close()
            except Exception:
                pass
        # Tell the phone about every dashboard already waiting.
        for vid in list(rtc_viewers):
            await _rtc_send(websocket, {"type": "viewer-joined", "from": vid})
    else:
        rtc_viewers[peer_id] = websocket
        await _rtc_send(websocket, {"type": "welcome", "id": peer_id, "publisher": rtc_publisher["ws"] is not None})
        await _rtc_send(rtc_publisher["ws"], {"type": "viewer-joined", "from": peer_id})
    try:
        while True:
            text = await websocket.receive_text()
            try:
                msg = json.loads(text)
            except Exception:
                continue
            if role == "publisher":
                target = rtc_viewers.get(str(msg.get("to", "")))
                await _rtc_send(target, msg)
            else:
                msg["from"] = peer_id
                await _rtc_send(rtc_publisher["ws"], msg)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        if role == "publisher":
            if rtc_publisher["ws"] is websocket:
                rtc_publisher["ws"] = None
                for vws in list(rtc_viewers.values()):
                    await _rtc_send(vws, {"type": "publisher-left"})
        else:
            rtc_viewers.pop(peer_id, None)
            await _rtc_send(rtc_publisher["ws"], {"type": "viewer-left", "from": peer_id})


@app.get("/api/rtc/status")
def rtc_status() -> dict:
    return {"publisher": rtc_publisher["ws"] is not None, "viewers": len(rtc_viewers)}


@app.post("/api/mobile/frame")
async def upload_mobile_frame(request: Request) -> Response:
    payload = await request.body()
    if not payload:
        return JSONResponse({"ok": False, "error": "empty frame"}, status_code=400)
    metadata = {
        "device_id": request.headers.get("X-Device-Id", "mobile-camera"),
        "capture_millis": request.headers.get("X-Capture-Millis"),
        "content_type": request.headers.get("Content-Type"),
        "client_host": request.client.host if request.client else None,
    }
    result = mobile_frames.update(payload, source="mobile", metadata=metadata)
    # Fast path: overwrite one latest-frame file atomically, off the event loop.
    await asyncio.to_thread(_write_latest_mobile_file, payload)

    # Archive only when explicitly requested by the mapping workflow.
    saved = str(MOBILE_LATEST_PATH)
    if request.headers.get("X-Save-Mapping", "false").lower() == "true":
        stamp = time.strftime("%Y%m%d_%H%M%S")
        archive = MOBILE_FRAME_DIR / f"mobile_{stamp}_{result['frame_id']:06d}.jpg"
        try:
            archive.write_bytes(payload)
            saved = str(archive)
        except Exception:
            pass
    return JSONResponse({"ok": True, "frame_id": result["frame_id"], "size_bytes": len(payload), "saved": saved})


@app.get("/api/stream")
def stream() -> StreamingResponse:
    def generate():
        last_id = -1
        while True:
            frame, frame_id, _, _, _ = frames.snapshot()
            if frame is not None and frame_id != last_id:
                last_id = frame_id
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    + f"Content-Length: {len(frame)}\r\n".encode()
                    + b"Cache-Control: no-store\r\n\r\n" + frame + b"\r\n"
                )
            time.sleep(0.01)

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")


# --------------------------------------------------------------------------- #
# ESP32 bridge. The ESP32 firmware posts to the HTTP server (:8000). The HTTPS
# server (:8443, used by the phone and dashboard) is a separate process, so it
# mirrors the ESP32 frames by reading :8000's MJPEG stream over localhost.
# --------------------------------------------------------------------------- #
ESP32_HTTP_PORT = int(os.getenv("ESP32_HTTP_PORT", "8000"))


def _own_port() -> Optional[int]:
    argv = _sys.argv
    for i, arg in enumerate(argv):
        if arg == "--port" and i + 1 < len(argv):
            try:
                return int(argv[i + 1])
            except ValueError:
                return None
        if arg.startswith("--port="):
            try:
                return int(arg.split("=", 1)[1])
            except ValueError:
                return None
    return None


def _esp32_bridge_loop() -> None:
    import urllib.request

    url = f"http://127.0.0.1:{ESP32_HTTP_PORT}/api/stream"
    while True:
        try:
            with urllib.request.urlopen(url, timeout=15) as resp:
                while True:
                    line = resp.readline()
                    if not line:
                        break  # stream closed; reconnect
                    if not line.lower().startswith(b"content-length:"):
                        continue
                    length = int(line.split(b":", 1)[1].strip())
                    while resp.readline() not in (b"\r\n", b"\n", b""):
                        pass  # remaining part headers
                    payload = resp.read(length)
                    if len(payload) == length:
                        frames.update(payload, source="esp32", metadata={"device_id": "esp32-kitchen-cam", "via": f"bridge from :{ESP32_HTTP_PORT}"})
        except Exception:
            pass
        time.sleep(1.0)  # ESP32 server idle or restarting; retry


@app.on_event("startup")
def _start_esp32_bridge() -> None:
    port = _own_port()
    if port is not None and port != ESP32_HTTP_PORT:
        threading.Thread(target=_esp32_bridge_loop, name="esp32-bridge", daemon=True).start()
        _start_presence()


# --------------------------------------------------------------------------- #
# Presence: when the camera sees someone enter, start listening on the laptop mic
# so the user can simply say "Hey, I am at the kitchen" and be greeted by name.
# Only the HTTPS process (:8443) runs this, so there is exactly one listener.
# --------------------------------------------------------------------------- #
presence = None
AUTO_LISTEN_ON_ENTRY = os.getenv("PRESENCE_AUTO_LISTEN", "1") != "0"
_auto_listen_busy = threading.Lock()


def _presence_frame() -> tuple[Optional[bytes], str]:
    """Kitchen camera first (ESP32), phone camera as fallback. Only fresh frames."""
    now = time.time()
    for store, name in ((frames, "esp32"), (mobile_frames, "phone")):
        frame, _, received_at, _, _ = store.snapshot()
        if frame is not None and received_at is not None and now - received_at < 3.0:
            return frame, name
    return None, ""


def _auto_listen(entry: dict) -> None:
    """Camera saw someone come in: listen for up to three short turns."""
    if not _auto_listen_busy.acquire(blocking=False):
        return
    try:
        log_auto_event("note", f"Someone entered the kitchen ({entry.get('source') or 'camera'}). Listening now.")
        for _ in range(3):
            while voice_state.get("speaking"):
                time.sleep(0.3)
            heard = audio_control.test_microphone(None)
            if heard.get("busy"):
                time.sleep(1.0)  # dashboard is using the mic; try again shortly
                continue
            text = str(heard.get("text") or "").strip()
            if not heard.get("ok") or not heard.get("captured") or not text:
                continue
            voice_state["last_heard"] = text
            log_auto_event("user", text)
            result = asyncio.run(answer_question(text))
            answer = result.get("answer") or SAFE_UNCERTAIN
            voice_state["last_answer"] = answer
            log_auto_event("assistant", answer, result.get("source"))
            _speak_blocking(answer)
            return
        log_auto_event("note", "No one spoke after entering. Tap to talk when ready.")
    finally:
        _auto_listen_busy.release()


def _on_person_entry(entry: dict) -> None:
    if AUTO_LISTEN_ON_ENTRY:
        threading.Thread(target=_auto_listen, args=(entry,), name="auto-listen", daemon=True).start()


def _start_presence() -> None:
    global presence
    try:
        from server.presence import PresenceMonitor
    except Exception:  # pragma: no cover - loose-script mode
        from presence import PresenceMonitor  # type: ignore
    presence = PresenceMonitor(_presence_frame, _on_person_entry)


@app.get("/api/presence")
def presence_api() -> dict:
    if presence is None:
        return {"status": "off", "enabled": False, "present": False, "people": [], "auto_listen": AUTO_LISTEN_ON_ENTRY}
    snap = presence.snapshot()
    snap["auto_listen"] = AUTO_LISTEN_ON_ENTRY
    snap["listening"] = _auto_listen_busy.locked()
    return snap


@app.post("/api/presence/config")
async def presence_config(request: Request) -> dict:
    global AUTO_LISTEN_ON_ENTRY
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if "auto_listen" in payload:
        AUTO_LISTEN_ON_ENTRY = bool(payload["auto_listen"])
    if presence is not None and "enabled" in payload:
        presence.enabled = bool(payload["enabled"])
    return presence_api()


@app.get("/api/graph")
def graph_api() -> dict:
    graph = load_graph()
    return {"status": "ok" if "error" not in graph else "error", "graph": graph}


@app.post("/api/query")
async def query_api(request: Request) -> dict:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    question = str(payload.get("question", "")).strip()
    graph = load_graph()
    answer = answer_from_graph(graph, question)
    return {"status": "ok", "question": question, "answer": answer, "safe_uncertain": answer == SAFE_UNCERTAIN}


@app.get("/api/vlm/state")
def vlm_state() -> dict:
    if not VLM_STATE_PATH.exists():
        return {"status": "not_started", "reasoner": None}
    try:
        return {"status": "ok", "reasoner": json.loads(VLM_STATE_PATH.read_text(encoding="utf-8"))}
    except Exception as exc:
        return {"status": "error", "error": str(exc), "reasoner": None}


@app.get("/api/assistant/state")
def assistant_state() -> dict:
    if not ASSISTANT_STATE_PATH.exists():
        return {"status": "not_started", "state": None}
    try:
        return {"status": "ok", "state": json.loads(ASSISTANT_STATE_PATH.read_text(encoding="utf-8"))}
    except Exception as exc:
        return {"status": "error", "error": str(exc), "state": None}


@app.post("/api/voice/query")
async def voice_query_placeholder() -> dict:
    return {"status": "use_live_assistant", "message": "Run scripts/live_kitchen_assistant.py for microphone interaction."}


# --------------------------------------------------------------------------- #
# Conversation layer: one answer pipeline shared by typed chat and voice turns.
# Order of authority: safety intents -> kitchen graph -> Nemotron brain.
# --------------------------------------------------------------------------- #
voice_state: dict = {"speaking": False, "text": None, "last_answer": None, "last_heard": None, "updated_at": None}
_STOP_RE = re.compile(r"\b(stop|cancel|halt|be quiet|shut up)\b")
USER_NAME = os.getenv("USER_NAME", "Leela")
# "Hey, I am at the kitchen" / "I'm in the kitchen" / "I have reached the kitchen" ...
_ARRIVAL_RE = re.compile(
    r"\b(i am|i m|im|i have|i ve)\b.{0,25}\bkitchen\b"
    r"|\b(entered|reached|arrived|came|come|walked)\b.{0,25}\bkitchen\b"
)
# Conversation turns the server starts by itself (camera-triggered listening), for the dashboard.
auto_events: list[dict] = []
_auto_event_id = 0
_auto_lock = threading.Lock()


def greeting_text() -> str:
    return f"Hey {USER_NAME}, welcome to the kitchen. How can I help you today?"


def log_auto_event(role: str, text: str, source: Optional[str] = None) -> None:
    global _auto_event_id
    with _auto_lock:
        _auto_event_id += 1
        auto_events.append({"id": _auto_event_id, "role": role, "text": text, "source": source, "at": time.time()})
        del auto_events[:-30]
_REPEAT_RE = re.compile(r"\b(repeat|say (that|it) again|again please|pardon)\b")


async def answer_question(question: str) -> dict:
    q = normalize(question)
    if _ARRIVAL_RE.search(q):
        if presence is not None:
            presence.mark_greeted()
        return {"status": "ok", "question": question, "source": "greeting", "answer": greeting_text()}
    if _STOP_RE.search(q):
        return {"status": "ok", "question": question, "source": "safety",
                "answer": "Stopping. Please stay where you are."}
    if _REPEAT_RE.search(q) and voice_state.get("last_answer"):
        return {"status": "ok", "question": question, "source": "repeat",
                "answer": voice_state["last_answer"]}

    # Kitchen location questions stay on the deterministic graph (authoritative/safe).
    graph = load_graph()
    if wanted_object(question):
        graph_ans = answer_from_graph(graph, question)
        if graph_ans != SAFE_UNCERTAIN:
            return {"status": "ok", "question": question, "answer": graph_ans, "source": "kitchen_graph"}

    brain = get_brain()
    if brain is None:
        return {"status": "error", "source": "brain", "question": question,
                "answer": "The reasoning brain is not configured. Set NVIDIA_API_KEY in .env."}
    try:
        answer = await asyncio.to_thread(
            brain.answer, question, brain_vision_summary(), brain_graph_facts(graph), None
        )
    except Exception as exc:
        return {"status": "error", "source": "brain", "question": question,
                "answer": f"Reasoning service error: {type(exc).__name__}."}
    return {"status": "ok", "question": question, "answer": answer,
            "source": "nemotron", "model": getattr(brain, "model", None)}


def _speak_blocking(text: str, device=None) -> dict:
    """Speak through the laptop speaker, waiting briefly if the audio device is busy."""
    voice_state.update(speaking=True, text=text, updated_at=time.time())
    try:
        for _ in range(40):  # up to ~10 s for a mic capture to release the device
            result = audio_control.test_speaker(text, device, earcon=False)
            if not result.get("busy"):
                return result
            time.sleep(0.25)
        return {"ok": False, "error": "Speaker stayed busy."}
    finally:
        voice_state.update(speaking=False, updated_at=time.time())


def speak_in_background(text: str, device=None) -> None:
    voice_state["last_answer"] = text
    voice_state.update(speaking=True, text=text, updated_at=time.time())
    asyncio.get_running_loop().create_task(asyncio.to_thread(_speak_blocking, text, device))


@app.post("/api/assistant/ask")
async def assistant_ask(request: Request) -> dict:
    """Typed chat: question -> safety / kitchen graph / Nemotron -> answer.
    Speech runs in the background so the text answer returns immediately."""
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    question = str(payload.get("question", "")).strip()
    speak = bool(payload.get("speak", False))
    if not question:
        return {"status": "error", "answer": "No question provided."}
    result = await answer_question(question)
    if speak and result.get("answer"):
        speak_in_background(result["answer"], payload.get("speaker_device"))
    else:
        voice_state["last_answer"] = result.get("answer")
    result["spoke"] = speak
    return result


@app.post("/api/voice/turn")
async def voice_turn(request: Request) -> dict:
    """One spoken conversation turn on the laptop: beep -> listen (VAD) -> transcribe
    -> answer -> speak reply in the background."""
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    t0 = time.time()
    heard = await asyncio.to_thread(audio_control.test_microphone, payload.get("mic_device"))
    listen_ms = int((time.time() - t0) * 1000)
    if heard.get("busy"):
        return {"status": "busy", "message": heard.get("error")}
    if not heard.get("ok"):
        return {"status": "error", "message": heard.get("error", "Microphone error.")}
    text = str(heard.get("text") or "").strip()
    if not heard.get("captured") or not text:
        return {"status": "no_speech", "message": heard.get("message") or "I did not catch that.", "listen_ms": listen_ms}
    voice_state["last_heard"] = text
    t1 = time.time()
    result = await answer_question(text)
    result["think_ms"] = int((time.time() - t1) * 1000)
    result["listen_ms"] = listen_ms
    result["transcript"] = text
    speak = payload.get("speak", True) is not False
    if speak and result.get("answer"):
        speak_in_background(result["answer"], payload.get("speaker_device"))
    result["spoke"] = speak
    return result


@app.post("/api/voice/speak")
async def voice_speak(request: Request) -> dict:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    text = str(payload.get("text", "")).strip()
    if not text:
        return {"ok": False, "error": "No text."}
    speak_in_background(text, payload.get("speaker_device"))
    return {"ok": True}


@app.post("/api/voice/clear")
def voice_clear() -> dict:
    """Forget the conversation so 'repeat' does not replay a cleared answer."""
    voice_state.update(last_answer=None, last_heard=None)
    return {"ok": True}


@app.get("/api/voice/state")
def voice_state_api() -> dict:
    return {"speaking": voice_state["speaking"], "text": voice_state["text"],
            "auto_events": list(auto_events), "user_name": USER_NAME,
            "last_heard": voice_state["last_heard"], "last_answer": voice_state["last_answer"]}


@app.get("/api/audio/devices")
def audio_devices() -> dict:
    return audio_control.list_devices()


@app.post("/api/audio/speaker/test")
async def audio_speaker_test(request: Request) -> dict:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    text = str(payload.get("text", "")).strip() or None
    device = payload.get("device")
    return await asyncio.to_thread(audio_control.test_speaker, text, device)


@app.post("/api/audio/mic/test")
async def audio_mic_test(request: Request) -> dict:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    device = payload.get("device")
    # Blocking VAD capture + transcription runs off the event loop.
    return await asyncio.to_thread(audio_control.test_microphone, device)


@app.get("/api/audio/mic/last.wav")
def audio_last_capture() -> Response:
    path = audio_control.LAST_WAV
    if not path.exists():
        return JSONResponse({"ok": False, "error": "No capture yet"}, status_code=404)
    return Response(path.read_bytes(), media_type="audio/wav", headers={"Cache-Control": "no-store"})


@app.post("/api/audio/warmup")
async def audio_warmup() -> dict:
    return await asyncio.to_thread(audio_control.warm_up)


@app.get("/api/task")
def task_placeholder() -> dict:
    return {"task": "Prepare Tea", "state": "NOT_STARTED", "current_step": None}


@app.post("/api/task/start")
def task_start_placeholder() -> dict:
    return {"task": "Prepare Tea", "state": "START", "current_step": "Kitchen ready check pending"}


@app.post("/api/task/reset")
def task_reset_placeholder() -> dict:
    return {"task": "Prepare Tea", "state": "NOT_STARTED", "current_step": None}
