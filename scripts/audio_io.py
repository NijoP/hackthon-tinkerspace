"""Laptop audio I/O layer for the Kitchen Memory Assistant.

This module owns the OUTPUT (laptop speaker, TTS + earcons) and the INPUT
(laptop microphone, voice-activity recording + local speech-to-text) so that a
visually impaired user can have a smooth, hands-free spoken conversation with
the device.

Design goals for a blind user:
  * The assistant always *announces itself* with speech, never silent UI.
  * Before it listens, it plays a short rising "listening" beep so the user
    knows exactly when to start talking.
  * Recording uses energy-based Voice Activity Detection (VAD): the user just
    talks naturally and stops; the mic auto-stops after a short trailing
    silence. No fixed countdown, no screen required.
  * After capture it plays a short falling "got it" beep, then transcribes.
  * Heavy resources (TTS engine, Whisper model) are created ONCE and reused.

Everything here is local-only (Windows SAPI via pyttsx3 + faster-whisper).

Environment overrides (all optional):
  MIC_DEVICE        index or name substring of the input device
  SPEAKER_DEVICE    index or name substring of the output device
  TTS_VOICE         voice id/name substring (e.g. "Zira", "David")
  TTS_RATE          speech rate words-per-minute (int, default 165)
  TTS_VOLUME        0.0 - 1.0 (default 1.0)
  WHISPER_MODEL     faster-whisper model name (default "base")
  WHISPER_DEVICE    "cuda" or "cpu" (default auto -> cpu fallback)
"""

from __future__ import annotations

import os
import queue
import tempfile
import threading
import time
import wave
from collections import deque
from pathlib import Path
from typing import Optional

import numpy as np

SAMPLE_RATE = 16000


# --------------------------------------------------------------------------- #
# Device resolution helpers
# --------------------------------------------------------------------------- #
def _resolve_device(spec: Optional[str], want_input: bool) -> Optional[int]:
    """Resolve a device spec (index or name substring) to a device index.

    Returns None to let sounddevice use the system default.
    """
    if spec is None or str(spec).strip() == "":
        return None
    try:
        import sounddevice as sd
    except Exception:
        return None

    spec = str(spec).strip()
    # Direct numeric index.
    if spec.isdigit():
        return int(spec)

    # Name substring match against devices with the right channel direction.
    needle = spec.lower()
    try:
        devices = sd.query_devices()
    except Exception:
        return None
    for idx, dev in enumerate(devices):
        chans = dev.get("max_input_channels" if want_input else "max_output_channels", 0)
        if chans > 0 and needle in dev.get("name", "").lower():
            return idx
    return None


def list_devices() -> str:
    """Return a human-readable listing of audio devices for diagnostics."""
    try:
        import sounddevice as sd
    except Exception as exc:  # pragma: no cover - import guard
        return f"sounddevice unavailable: {exc}"
    lines = ["Audio devices (index: name [in/out]):"]
    for idx, dev in enumerate(sd.query_devices()):
        lines.append(
            f"  {idx:>2}: {dev['name']} "
            f"[{dev['max_input_channels']} in / {dev['max_output_channels']} out]"
        )
    try:
        din, dout = sd.default.device
        lines.append(f"Default input={din}  Default output={dout}")
    except Exception:
        pass
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Speaker: TTS + earcons
# --------------------------------------------------------------------------- #
class Speaker:
    """Laptop speaker output. Reuses one TTS engine for the whole session."""

    def __init__(
        self,
        enabled: bool = True,
        device: Optional[str] = None,
        voice: Optional[str] = None,
        rate: Optional[int] = None,
        volume: Optional[float] = None,
        earcons: bool = True,
    ) -> None:
        self.enabled = enabled
        self.earcons = earcons
        self.device = _resolve_device(device or os.getenv("SPEAKER_DEVICE"), want_input=False)
        self._voice_spec = voice or os.getenv("TTS_VOICE")
        self._rate = int(rate if rate is not None else os.getenv("TTS_RATE", "165"))
        self._volume = float(volume if volume is not None else os.getenv("TTS_VOLUME", "1.0"))
        self._engine = None
        if self.enabled:
            self._init_engine()

    def _init_engine(self) -> None:
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", self._rate)
            engine.setProperty("volume", self._volume)
            if self._voice_spec:
                needle = self._voice_spec.lower()
                for v in engine.getProperty("voices"):
                    if needle in (v.id or "").lower() or needle in (v.name or "").lower():
                        engine.setProperty("voice", v.id)
                        break
            self._engine = engine
        except Exception as exc:
            print(f"[TTS unavailable: {exc}]")
            self._engine = None

    def speak(self, text: str) -> None:
        """Speak text through the laptop speaker and echo it to the console."""
        print(f"ASSISTANT: {text}")
        if not self.enabled:
            return
        if self._engine is None:
            self._init_engine()
        if self._engine is None:
            return
        try:
            self._engine.say(text)
            self._engine.runAndWait()
        except RuntimeError:
            # Engine loop can get wedged; rebuild once and retry.
            self._init_engine()
            if self._engine is not None:
                try:
                    self._engine.say(text)
                    self._engine.runAndWait()
                except Exception as exc:
                    print(f"[TTS error: {exc}]")
        except Exception as exc:
            print(f"[TTS error: {exc}]")

    # --- earcons -------------------------------------------------------- #
    def _tone(self, freqs, duration: float = 0.18, volume: float = 0.3) -> None:
        if not (self.enabled and self.earcons):
            return
        try:
            import sounddevice as sd
        except Exception:
            return
        try:
            seg_len = int(SAMPLE_RATE * duration / len(freqs))
            t = np.arange(seg_len) / SAMPLE_RATE
            parts = [np.sin(2 * np.pi * f * t) for f in freqs]
            wave_arr = np.concatenate(parts).astype(np.float32)
            # Short fade in/out to avoid clicks.
            fade = min(400, len(wave_arr) // 10)
            if fade > 0:
                env = np.ones_like(wave_arr)
                env[:fade] = np.linspace(0, 1, fade)
                env[-fade:] = np.linspace(1, 0, fade)
                wave_arr *= env
            wave_arr *= volume
            sd.play(wave_arr, SAMPLE_RATE, device=self.device)
            sd.wait()
        except Exception:
            pass

    def beep_listening(self) -> None:
        """Rising two-tone cue: 'I am listening now, please talk.'"""
        self._tone([660, 990])

    def beep_done(self) -> None:
        """Falling two-tone cue: 'Got it, processing.'"""
        self._tone([880, 440])

    def beep_error(self) -> None:
        """Low buzz cue: 'I did not catch that.'"""
        self._tone([300, 300], duration=0.25)


# --------------------------------------------------------------------------- #
# Microphone: voice-activity recording
# --------------------------------------------------------------------------- #
class Microphone:
    """Laptop microphone with an ALWAYS-ON input stream + ring buffer.

    Root cause this design fixes: on this laptop the AMD mic-array driver
    (with AMD noise suppression) delivers ~1.0s of pure zeros plus ~200ms
    open latency every time a NEW input stream is opened. Opening a stream
    per utterance therefore silently discarded the first ~1.2s of speech
    ("I have a quick ques-"), and Whisper guessed at the fragment
    ("Kristian for you", "Thank you."). Keeping one warm stream open and
    slicing audio out of a ring buffer means nothing is ever lost.
    """

    BLOCK_SEC = 0.1

    def __init__(
        self,
        device: Optional[str] = None,
        sample_rate: int = SAMPLE_RATE,
        silence_threshold: float = 0.0,
        start_timeout: float = 8.0,
        silence_duration: float = 1.2,
        max_duration: float = 15.0,
        calibrate: bool = True,  # kept for API compatibility
        min_speech_seconds: float = 0.3,
        buffer_seconds: float = 30.0,
    ) -> None:
        self.device = _resolve_device(device or os.getenv("MIC_DEVICE"), want_input=True)
        self.sample_rate = sample_rate
        self.fixed_threshold = silence_threshold  # 0 => adaptive
        self.silence_threshold = 300.0
        self.start_timeout = start_timeout
        self.silence_duration = silence_duration
        self.max_duration = max_duration
        self.min_speech_seconds = min_speech_seconds
        self._calibrated = True  # calibration is continuous now
        self._lock = threading.Lock()
        self._blocks: "deque[tuple[int, np.ndarray]]" = deque(maxlen=int(buffer_seconds / self.BLOCK_SEC))
        self._counter = 0
        self._stream = None
        self._stream_device = "unset"
        self.last_stats: dict = {}

    @staticmethod
    def available() -> bool:
        try:
            import sounddevice  # noqa: F401
            return True
        except Exception:
            return False

    @staticmethod
    def _rms(block: np.ndarray) -> float:
        if block.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(block.astype(np.float32) ** 2)))

    # ---- persistent stream ------------------------------------------------ #
    def _callback(self, indata, frames, time_info, status):  # noqa: ANN001
        with self._lock:
            self._counter += 1
            self._blocks.append((self._counter, indata.copy()))

    def ensure_stream(self) -> None:
        """Open the always-on input stream (once) and wait until it is warm."""
        import sounddevice as sd
        if self._stream is not None and self._stream_device == self.device and self._stream.active:
            return
        self.close()
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="int16",
            blocksize=int(self.sample_rate * self.BLOCK_SEC),
            device=self.device,
            callback=self._callback,
        )
        self._stream.start()
        self._stream_device = self.device
        # Wait for the driver warm-up (pure zeros) to pass, max 3s.
        deadline = time.time() + 3.0
        while time.time() < deadline:
            with self._lock:
                recent = [b for _, b in list(self._blocks)[-3:]]
            if recent and any(self._rms(b) > 0.5 for b in recent):
                break
            time.sleep(0.05)

    def close(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
        self._stream = None
        self._stream_device = "unset"
        with self._lock:
            self._blocks.clear()

    def noise_floor(self, seconds: float = 3.0) -> float:
        """Robust ambient level: 20th percentile of recent non-zero block RMS."""
        n = max(1, int(seconds / self.BLOCK_SEC))
        with self._lock:
            recent = [self._rms(b) for _, b in list(self._blocks)[-n:]]
        recent = [r for r in recent if r > 0.5] or [0.0]
        return float(np.percentile(recent, 20))

    def calibrate(self, seconds: float = 0.6) -> None:  # compatibility
        self.ensure_stream()
        self._update_threshold()

    def _update_threshold(self) -> float:
        if self.fixed_threshold > 0:
            self.silence_threshold = self.fixed_threshold
        else:
            floor = self.noise_floor()
            self.silence_threshold = max(floor * 3.0, floor + 80.0, 100.0)
        return self.silence_threshold

    def mark(self) -> int:
        """Return the current stream position; capture can start from here."""
        self.ensure_stream()
        with self._lock:
            return self._counter

    def listen(self, start_mark: Optional[int] = None) -> Optional[Path]:
        """Capture one utterance from the warm stream, starting at start_mark.

        Endpointing: wait for speech (energy above adaptive threshold), then
        stop after ``silence_duration`` of trailing silence. ALL audio from
        start_mark onward is kept, so the onset can never be clipped; Whisper's
        Silero VAD trims leading/trailing silence afterwards.
        """
        try:
            self.ensure_stream()
        except Exception as exc:
            print(f"[Mic unavailable: {exc}]")
            return None
        threshold = self._update_threshold()
        if start_mark is None:
            start_mark = self.mark()

        speech_started = False
        voiced = 0
        silence = 0
        seen = start_mark
        needed_silence = int(self.silence_duration / self.BLOCK_SEC)
        t_start = time.time()
        while True:
            time.sleep(0.05)
            with self._lock:
                new = [(i, b) for i, b in self._blocks if i > seen]
            for i, b in new:
                seen = i
                if self._rms(b) >= threshold:
                    speech_started = True
                    voiced += 1
                    silence = 0
                elif speech_started:
                    silence += 1
            elapsed = time.time() - t_start
            if not speech_started and elapsed > self.start_timeout:
                break
            if speech_started and silence >= needed_silence:
                break
            if elapsed > self.max_duration:
                break
            if self._stream is None or not self._stream.active:
                break

        with self._lock:
            chunks = [b for i, b in self._blocks if start_mark < i <= seen]
        audio = np.concatenate(chunks, axis=0) if chunks else np.zeros((0, 1), dtype=np.int16)
        self.last_stats = {
            "captured_seconds": round(len(audio) / self.sample_rate, 2),
            "voiced_seconds": round(voiced * self.BLOCK_SEC, 2),
            "threshold": round(threshold, 1),
            "noise_floor": round(self.noise_floor(), 1),
            "peak": int(np.abs(audio).max()) if audio.size else 0,
        }
        if not speech_started or voiced * self.BLOCK_SEC < self.min_speech_seconds:
            return None
        return self._write_wav(audio)

    def record_fixed(self, seconds: float) -> Optional[Path]:
        """Fixed-length capture from the warm stream (no VAD)."""
        try:
            m = self.mark()
        except Exception as exc:
            print(f"[Mic unavailable: {exc}]")
            return None
        time.sleep(seconds)
        with self._lock:
            chunks = [b for i, b in self._blocks if i > m]
        if not chunks:
            return None
        return self._write_wav(np.concatenate(chunks, axis=0))

    def _write_wav(self, audio: np.ndarray) -> Path:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        tmp.close()
        with wave.open(tmp.name, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio.tobytes())
        return Path(tmp.name)


# --------------------------------------------------------------------------- #
# Transcription post-processing
# --------------------------------------------------------------------------- #
_PHANTOMS = {
    "thank you", "thank you very much", "thanks for watching",
    "thank you for watching", "you", "please subscribe",
    "subtitles by the amara org community",
}


def _normalize_phrase(text: str) -> str:
    import re as _re
    return _re.sub(r"[^a-z ]", "", (text or "").lower()).strip()


def _collapse_repeats(text: str) -> str:
    """Remove immediate duplicated sentences/phrases and stutters.

    Whisper sometimes emits the same sentence twice (e.g. "Hey... Hey...").
    This is a cheap safety net on top of the decoder-level repetition guards:
    it collapses consecutive identical sentences and consecutive identical
    word runs without touching legitimately repeated short words.
    """
    if not text:
        return text

    import re as _re

    # 1) Collapse repeated sentences.
    parts = _re.split(r"(?<=[.!?])\s+", text)
    deduped: list[str] = []
    for p in parts:
        norm = _re.sub(r"[^a-z0-9 ]", "", p.lower()).strip()
        if deduped and norm and norm == _re.sub(r"[^a-z0-9 ]", "", deduped[-1].lower()).strip():
            continue
        deduped.append(p)
    out = " ".join(deduped).strip()

    # 2) Collapse an immediately repeated whole phrase (no sentence punctuation).
    words = out.split()
    n = len(words)
    if n >= 4:
        for size in range(n // 2, 1, -1):
            if words[:size] == words[size:2 * size]:
                # Phrase A A ... -> keep one A plus any remainder.
                out = " ".join(words[size:]) if n == 2 * size else " ".join(words[:size] + words[2 * size:])
                break

    # 3) Collapse stuttered single words ("the the the" -> "the").
    out = _re.sub(r"\b(\w+)(\s+\1\b)+", r"\1", out, flags=_re.IGNORECASE)
    return out.strip()


# --------------------------------------------------------------------------- #
# Transcriber: load Whisper once, reuse
# --------------------------------------------------------------------------- #
class Transcriber:
    """Local speech-to-text with faster-whisper. Model is loaded once."""

    def __init__(self, model_name: Optional[str] = None, device: Optional[str] = None) -> None:
        # `small.en` is far more accurate than `base` for conversational English
        # while still fast on a modern GPU. Override with WHISPER_MODEL.
        self.model_name = model_name or os.getenv("WHISPER_MODEL", "small.en")
        self.device = device or os.getenv("WHISPER_DEVICE") or self._auto_device()
        # English-only by default (set WHISPER_LANGUAGE=auto for detection).
        lang = os.getenv("WHISPER_LANGUAGE", "en")
        self.language = None if lang.lower() in ("", "auto", "none") else lang
        # Optional domain vocabulary bias (kitchen terms, the wake name, etc.).
        self.initial_prompt = os.getenv("WHISPER_PROMPT") or None
        self._model = None

    @staticmethod
    def _auto_device() -> str:
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
        except Exception:
            pass
        return "cpu"

    def _load(self) -> None:
        if self._model is not None:
            return
        from faster_whisper import WhisperModel
        compute_type = "float16" if self.device == "cuda" else "int8"

        def _build(device: str, ctype: str):
            # Try the local HF cache first (fast: ~0.5s). Only if the model is
            # not cached do we hit the network to download it. This avoids the
            # ~170s hub revalidation delay on every warm start.
            prev = os.environ.get("HF_HUB_OFFLINE")
            os.environ["HF_HUB_OFFLINE"] = "1"
            try:
                return WhisperModel(self.model_name, device=device, compute_type=ctype)
            except Exception:
                # Not cached (or offline load failed): allow a one-time download.
                if prev is None:
                    os.environ.pop("HF_HUB_OFFLINE", None)
                else:
                    os.environ["HF_HUB_OFFLINE"] = prev
                return WhisperModel(self.model_name, device=device, compute_type=ctype)
            finally:
                if prev is None:
                    os.environ.pop("HF_HUB_OFFLINE", None)
                else:
                    os.environ["HF_HUB_OFFLINE"] = prev

        try:
            self._model = _build(self.device, compute_type)
        except Exception as exc:
            # Fall back to CPU if CUDA init fails.
            print(f"[Whisper {self.device} init failed ({exc}); falling back to cpu]")
            self.device = "cpu"
            self._model = _build("cpu", "int8")

    def transcribe(self, wav_path: Path) -> str:
        self._load()
        assert self._model is not None
        # Decoding settings chosen to fight the two classic Whisper failures:
        #  * REPETITION / duplicated phrases ("Hey... Hey..."): disable
        #    condition_on_previous_text, add repetition_penalty + no_repeat_ngram.
        #  * HALLUCINATION on silence/noise: VAD filter + no_speech/log_prob/
        #    compression-ratio thresholds, with temperature fallback.
        # beam search (beam_size=5) replaces the old greedy beam_size=1 for
        # much better word accuracy.
        segments, _info = self._model.transcribe(
            str(wav_path),
            language=self.language,
            task="transcribe",
            beam_size=5,
            best_of=5,
            temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
            condition_on_previous_text=False,
            repetition_penalty=1.15,
            no_repeat_ngram_size=3,
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
            no_speech_threshold=0.6,
            initial_prompt=self.initial_prompt,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500, "speech_pad_ms": 200},
        )
        kept = []
        for seg in segments:
            # Drop segments Whisper itself flags as likely non-speech.
            if getattr(seg, "no_speech_prob", 0.0) > 0.6 and getattr(seg, "avg_logprob", 0.0) < -0.8:
                continue
            kept.append(seg.text.strip())
        text = _collapse_repeats(" ".join(kept).strip())
        # Classic Whisper phantom phrases produced from silence/noise.
        if _normalize_phrase(text) in _PHANTOMS:
            return ""
        return text


# --------------------------------------------------------------------------- #
# Convenience: a complete "ask one question" turn
# --------------------------------------------------------------------------- #
def voice_turn(
    mic: Microphone,
    transcriber: Transcriber,
    speaker: Optional[Speaker] = None,
) -> Optional[str]:
    """One full listen->transcribe turn with audible cues for a blind user.

    Returns the recognized text, "" if nothing understood, or None if the mic
    is unavailable.
    """
    # The mic stream is always open and warm; mark the capture start at the
    # beep so even words spoken during/right after the beep are kept.
    try:
        mic.ensure_stream()
    except Exception as exc:
        print(f"[Mic unavailable: {exc}]")
        return None
    start = mic.mark()
    if speaker is not None:
        speaker.beep_listening()
    wav = mic.listen(start_mark=start)
    if speaker is not None:
        speaker.beep_done()
    if wav is None:
        if speaker is not None:
            speaker.beep_error()
        return None
    try:
        text = transcriber.transcribe(wav)
    finally:
        try:
            wav.unlink(missing_ok=True)
        except Exception:
            pass
    if not text and speaker is not None:
        speaker.beep_error()
    return text


if __name__ == "__main__":
    # Quick manual diagnostic.
    print(list_devices())
