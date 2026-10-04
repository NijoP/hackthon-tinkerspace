"""Reliable laptop text-to-speech for the server process.

Why this exists: pyttsx3 2.99 drives Windows SAPI through COM. The server calls
speech from a thread pool, so the engine was created on one thread and used from
others. SAPI then silently produces no audio. Here a single dedicated thread
initialises COM, owns one SAPI SpVoice for the whole process, and speaks every
request in order. Callers block until their sentence has finished playing.

Local only: Windows SAPI voices installed on this laptop.
"""

from __future__ import annotations

import os
import queue
import threading
from typing import Optional

_SVSF_DEFAULT = 0          # synchronous speak
_SVSF_PURGE = 2            # purge queued speech (used by stop)


class _Job:
    __slots__ = ("text", "device_name", "done", "error")

    def __init__(self, text: str, device_name: Optional[str]) -> None:
        self.text = text
        self.device_name = device_name
        self.done = threading.Event()
        self.error: Optional[str] = None


class SapiSpeaker:
    def __init__(self) -> None:
        self._jobs: "queue.Queue[_Job]" = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="sapi-tts", daemon=True)
        self._ready = threading.Event()
        self._init_error: Optional[str] = None
        self._voice = None
        self.speaking = False
        self._thread.start()
        self._ready.wait(timeout=10)

    # ---------------------------------------------------------------- thread
    def _run(self) -> None:
        try:
            import pythoncom
            import win32com.client

            pythoncom.CoInitialize()
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            wpm = int(os.getenv("TTS_RATE", "165"))
            voice.Rate = max(-10, min(10, round((wpm - 180) / 18)))
            voice.Volume = int(max(0.0, min(1.0, float(os.getenv("TTS_VOLUME", "1.0")))) * 100)
            wanted = (os.getenv("TTS_VOICE") or "").lower()
            if wanted:
                for token in voice.GetVoices():
                    if wanted in token.GetDescription().lower():
                        voice.Voice = token
                        break
            self._voice = voice
        except Exception as exc:  # pragma: no cover - depends on host
            self._init_error = f"{type(exc).__name__}: {exc}"
        finally:
            self._ready.set()

        while True:
            job = self._jobs.get()
            if self._voice is None:
                job.error = self._init_error or "SAPI unavailable"
                job.done.set()
                continue
            try:
                self._select_output(job.device_name)
                self.speaking = True
                self._voice.Speak(job.text, _SVSF_DEFAULT)
            except Exception as exc:
                job.error = f"{type(exc).__name__}: {exc}"
            finally:
                self.speaking = False
                job.done.set()

    def _select_output(self, device_name: Optional[str]) -> None:
        """Best-effort match of a sounddevice output name to a SAPI audio output."""
        try:
            outputs = self._voice.GetAudioOutputs()
            if not device_name:
                return
            needle = device_name.lower()[:28]
            for i in range(outputs.Count):
                token = outputs.Item(i)
                desc = token.GetDescription().lower()
                if needle in desc or desc in needle:
                    self._voice.AudioOutput = token
                    return
        except Exception:
            pass

    # ---------------------------------------------------------------- public
    @property
    def available(self) -> bool:
        return self._voice is not None

    @property
    def error(self) -> Optional[str]:
        return self._init_error

    def speak(self, text: str, device_name: Optional[str] = None, timeout: float = 120.0) -> Optional[str]:
        """Speak and wait until finished. Returns an error string or None."""
        text = (text or "").strip()
        if not text:
            return None
        job = _Job(text, device_name)
        self._jobs.put(job)
        if not job.done.wait(timeout):
            return "Speech timed out."
        return job.error


_instance: Optional[SapiSpeaker] = None
_instance_lock = threading.Lock()


def get_speaker() -> SapiSpeaker:
    global _instance
    with _instance_lock:
        if _instance is None:
            _instance = SapiSpeaker()
        return _instance
