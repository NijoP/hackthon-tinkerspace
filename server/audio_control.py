"""Server-side bridge to the laptop audio layer (mic + speaker).

The FastAPI server runs on the same laptop that has the physical microphone and
speaker, so dashboard "test" actions execute here. This module exposes thin,
blocking helpers (meant to be called from a threadpool) plus lazily-created
singletons so the Whisper model and TTS engine are built only once.

All imports of the heavy audio stack are deferred and guarded so the web server
still starts on a machine without working audio.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from typing import Any, Optional

# Make scripts/audio_io.py importable.
_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

_lock = threading.Lock()
# Serializes actual audio device access. PortAudio is NOT thread-safe: two
# overlapping streams (e.g. a stale/abandoned request plus a new one) can crash
# the whole process. Every device operation must hold this lock.
_op_lock = threading.Lock()
_BUSY = {
    "ok": False,
    "busy": True,
    "error": "Audio device is busy with another test. Please wait a moment and try again.",
}
LAST_WAV = Path(__file__).resolve().parents[1] / "artifacts" / "live" / "last_mic.wav"
_speaker = None
_mic = None
_transcriber = None
_last_mic_text: str = ""
_last_mic_at: Optional[float] = None


def _import_audio() -> Any:
    """Import the audio_io module, or raise with a clear message."""
    import audio_io  # type: ignore
    return audio_io


def audio_available() -> bool:
    """True if sounddevice can be imported (i.e. audio I/O is possible)."""
    try:
        import sounddevice  # noqa: F401
        return True
    except Exception:
        return False


def list_devices() -> dict:
    """Return structured input/output device info for the dashboard."""
    try:
        import sounddevice as sd
    except Exception as exc:
        return {"available": False, "error": str(exc), "inputs": [], "outputs": []}

    inputs, outputs = [], []
    try:
        devices = sd.query_devices()
        for idx, dev in enumerate(devices):
            entry = {"index": idx, "name": dev.get("name", f"device {idx}")}
            if dev.get("max_input_channels", 0) > 0:
                inputs.append(entry)
            if dev.get("max_output_channels", 0) > 0:
                outputs.append(entry)
        default_in, default_out = sd.default.device
    except Exception as exc:
        return {"available": False, "error": str(exc), "inputs": inputs, "outputs": outputs}

    def _name(i: int) -> Optional[str]:
        try:
            return sd.query_devices(i)["name"]
        except Exception:
            return None

    return {
        "available": True,
        "inputs": inputs,
        "outputs": outputs,
        "default_input": {"index": default_in, "name": _name(default_in)},
        "default_output": {"index": default_out, "name": _name(default_out)},
    }


def _get_speaker():
    global _speaker
    with _lock:
        if _speaker is None:
            audio_io = _import_audio()
            _speaker = audio_io.Speaker()
        return _speaker


def _get_mic():
    global _mic
    with _lock:
        if _mic is None:
            audio_io = _import_audio()
            _mic = audio_io.Microphone()
        return _mic


def _get_transcriber():
    global _transcriber
    with _lock:
        if _transcriber is None:
            audio_io = _import_audio()
            _transcriber = audio_io.Transcriber()
        return _transcriber


def speaker_status() -> str:
    if not audio_available():
        return "OFFLINE"
    return "READY" if _speaker is not None else "AVAILABLE"


def microphone_status() -> str:
    if not audio_available():
        return "OFFLINE"
    return "READY" if _mic is not None else "AVAILABLE"


def last_mic_result() -> dict:
    return {"text": _last_mic_text, "at": _last_mic_at}


def _coerce_device(value) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except Exception:
        return None


# --- blocking actions (call via asyncio.to_thread) ------------------------- #
def _output_device_name(dev: Optional[int]) -> Optional[str]:
    if dev is None:
        return None
    try:
        import sounddevice as sd
        return sd.query_devices(dev)["name"]
    except Exception:
        return None


def test_speaker(text: Optional[str] = None, device=None, earcon: bool = True) -> dict:
    """Speak a phrase through the laptop speaker. Returns a result dict.

    Speech goes through the dedicated SAPI thread (server/tts_worker.py); pyttsx3
    is silent when its engine is shared across thread-pool threads.
    """
    if not audio_available():
        return {"ok": False, "error": "Audio output unavailable on this host."}
    phrase = (text or "").strip() or (
        "Speaker test successful. The laptop speaker is working."
    )
    if not _op_lock.acquire(blocking=False):
        return dict(_BUSY)
    try:
        dev = _coerce_device(device)
        t0 = time.time()
        if earcon:
            sp = _get_speaker()
            if dev is not None:
                sp.device = dev
            sp.beep_done()
        try:
            from server import tts_worker
        except Exception:  # pragma: no cover - loose-script mode
            import tts_worker  # type: ignore
        tts = tts_worker.get_speaker()
        if not tts.available:
            # Last resort: the original pyttsx3 path.
            _get_speaker().speak(phrase)
        else:
            err = tts.speak(phrase, _output_device_name(dev))
            if err:
                return {"ok": False, "error": err}
        return {"ok": True, "spoke": phrase, "elapsed_ms": int((time.time() - t0) * 1000)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        _op_lock.release()


def test_microphone(device=None) -> dict:
    """Beep, listen for one utterance via VAD, transcribe, and return text."""
    global _last_mic_text, _last_mic_at
    if not audio_available():
        return {"ok": False, "error": "Microphone unavailable on this host."}
    if not _op_lock.acquire(blocking=False):
        return dict(_BUSY)
    try:
        sp = _get_speaker()
        mic = _get_mic()
        tr = _get_transcriber()
        dev = _coerce_device(device)
        if dev is not None and dev != mic.device:
            mic.device = dev  # ensure_stream() reopens on the new device
        # Mic stream is persistent and already warm (no ~1.2s driver dead
        # time); mark capture start at the beep so no words are lost.
        mic.ensure_stream()
        start = mic.mark()
        sp.beep_listening()
        t0 = time.time()
        wav = mic.listen(start_mark=start)
        sp.beep_done()
        stats = dict(mic.last_stats)
        if wav is None:
            return {
                "ok": True,
                "captured": False,
                "text": "",
                "stats": stats,
                "message": "No speech detected. Speak right after the beep.",
            }
        try:
            import shutil
            LAST_WAV.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(wav, LAST_WAV)  # for dashboard playback/debug
        except Exception:
            pass
        try:
            text = tr.transcribe(wav)
        finally:
            try:
                wav.unlink(missing_ok=True)
            except Exception:
                pass
        _last_mic_text = text
        _last_mic_at = time.time()
        return {
            "ok": True,
            "captured": True,
            "text": text,
            "elapsed_ms": int((time.time() - t0) * 1000),
            "model": tr.model_name,
            "device": tr.device,
            "stats": stats,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        _op_lock.release()


def warm_up() -> dict:
    """Pre-build the TTS engine and load the Whisper model (one-time cost)."""
    if not audio_available():
        return {"ok": False, "error": "Audio unavailable on this host."}
    if not _op_lock.acquire(blocking=False):
        return dict(_BUSY)
    try:
        _get_speaker()
        mic = _get_mic()
        tr = _get_transcriber()
        # Open the persistent mic stream now so the driver warm-up (pure
        # zeros for ~1s on the AMD mic array) is over before the first test.
        try:
            mic.ensure_stream()
        except Exception:
            pass
        t0 = time.time()
        tr._load()  # noqa: SLF001 - intentional warmup
        return {
            "ok": True,
            "model": tr.model_name,
            "device": tr.device,
            "load_ms": int((time.time() - t0) * 1000),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        _op_lock.release()
