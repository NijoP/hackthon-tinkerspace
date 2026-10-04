# Voice Interface

## MVP flow

```text
Laptop microphone
  -> local speech-to-text
  -> question text
  -> target-object extraction
  -> Kitchen Knowledge Graph query
  -> answer text
  -> local TTS
  -> laptop speaker
```

## Speech-to-text

Uses faster-whisper. The default model is **`small.en`** (English-only), which is
much more accurate for conversational speech than `base` while staying fast on a
GPU. Push-to-talk or the dashboard record button is acceptable.

### Accuracy / anti-hallucination settings

Early tests with `base` + greedy decoding produced wrong words and duplicated
phrases (e.g. "I have a quick question for you" -> "Hey, I have a Q-Costain for
you. Hey, I have a Q-Costain for you."). These are the two classic Whisper
failure modes. The fixes applied in `scripts/audio_io.py` (`Transcriber`) follow
the common guidance from the faster-whisper / WhisperX / openai-whisper issue
trackers:

- Bigger English model: `small.en` instead of `base` (set `WHISPER_MODEL`).
- `language="en"` fixed (no language-detection errors) \- `WHISPER_LANGUAGE`.
- `beam_size=5` + `best_of=5` instead of greedy `beam_size=1`.
- `condition_on_previous_text=False` \- the main cause of repeated phrases.
- `repetition_penalty=1.15` and `no_repeat_ngram_size=3` \- block loops.
- `temperature` fallback `[0.0 .. 1.0]` with `compression_ratio`,
  `log_prob`, and `no_speech` thresholds \- drop hallucinated output.
- `vad_filter=True` with padded VAD params \- trim silence that triggers
  hallucination.
- A `_collapse_repeats()` post-processor as a final safety net that removes any
  residual duplicated sentence / phrase / stutter.

### Choosing a model (speed vs accuracy)

Set `WHISPER_MODEL` before starting the server or assistant:

| Model | Notes |
|-------|-------|
| `base` / `base.en` | fastest, least accurate (old default) |
| `small.en` | **current default**, good accuracy, fast on GPU |
| `distil-medium.en` | better accuracy, still fast |
| `medium.en` | high accuracy, heavier |
| `distil-large-v3` | near-large accuracy, ~2x faster than large |

The RTX 3050 6GB in this laptop comfortably runs up to `medium.en` /
`distil-large-v3`. First use downloads the model; later loads are instant
(offline-first cache).

## Text-to-speech

Use pyttsx3 / Windows SAPI first. Piper is optional later only if the basic demo already works.

## Example questions

- Where is the glass?
- Where is the tea?
- Where is the kettle?
- Where is the sugar?
- Where is the spoon?

## Safety response

If the system is uncertain, answer:

```text
I am not certain. Please stop.
```

## Implementation (laptop mic + speaker)

The audio layer lives in `scripts/audio_io.py` and is shared by the live
assistant. It is built for a blind user to converse hands-free:

- `Speaker` — one persistent pyttsx3 / Windows SAPI engine for the whole
  session (not re-created per sentence), plus audible earcons:
  - rising beep = "I am listening, talk now"
  - falling beep = "got it, processing"
  - low buzz = "I did not catch that"
- `Microphone` — energy-based Voice Activity Detection. The user just talks
  after the beep and stops; recording auto-ends after ~1s of silence. Ambient
  noise is auto-calibrated so it adapts to the room. No countdown, no screen.
- `Transcriber` — faster-whisper loaded **once** and reused (the old code
  reloaded the model on every utterance).

### Running the live assistant

```powershell
# From the repo root, using the project venv.
.venv\Scripts\python.exe scripts\live_kitchen_assistant.py --force-welcome
```

Useful flags:

- `--list-devices` list all mic/speaker devices and exit.
- `--mic-device "Microphone Array"` pick an input by index or name substring.
- `--speaker-device "Realtek"` pick an output by index or name substring.
- `--voice Zira` choose a SAPI voice (e.g. `Zira`, `David`).
- `--rate 165` speech rate in words per minute.
- `--whisper-model base` / `--device cuda|cpu` STT model and backend.
- `--no-earcons` disable the beeps.
- `--keyboard` type instead of speaking (fallback if no mic).

### Environment overrides

All of the above can be set via env vars so the hardware config is fixed once:
`MIC_DEVICE`, `SPEAKER_DEVICE`, `TTS_VOICE`, `TTS_RATE`, `TTS_VOLUME`,
`WHISPER_MODEL`, `WHISPER_DEVICE`.

### Testing from the control dashboard

The dashboard (`/dashboard/`) has an **AUDIO TEST \- LAPTOP MIC + SPEAKER**
panel. Because the FastAPI server runs on the laptop that owns the hardware,
these buttons exercise the real laptop mic/speaker:

- **Test Speaker** \- speaks the phrase in the text box through the laptop
  speaker (`POST /api/audio/speaker/test`).
- **Test Microphone** \- plays a beep, records one utterance with VAD, and
  shows the transcript (`POST /api/audio/mic/test`). Speak right after the beep.
- **Warm up speech model** \- pre-loads Whisper so the first real test is fast
  (`POST /api/audio/warmup`).
- **Refresh devices** \- shows the default mic/speaker
  (`GET /api/audio/devices`).

The System Status panel now reflects real mic/speaker availability
(`OFFLINE` / `AVAILABLE` / `READY`) instead of a hardcoded value.

Model loading note: faster-whisper is loaded **offline-first** from the local
Hugging Face cache (~0.6s). Only the very first download touches the network.
This avoids a ~170s hub revalidation delay that otherwise hit every warm start.

### Testing from the command line

```powershell
.venv\Scripts\python.exe scripts\test_audio.py            # smoke test
.venv\Scripts\python.exe scripts\test_audio.py --mic      # record one phrase
.venv\Scripts\python.exe scripts\test_audio.py --loop     # full conversation
.venv\Scripts\python.exe scripts\test_audio.py --devices  # list devices
```

Verified on this laptop: default mic = `Microphone Array (AMD Audio Device)`,
default speaker = `Speaker (Realtek(R) Audio)`. Synthesized speech
"where is the kettle" was captured and transcribed correctly by the base
Whisper model.

## Root cause of clipped / hallucinated transcripts (fixed)

Symptom: "I have a quick question for you" became "Hey, I have a Q-Costain for you",
"Thank you.", or "Kristian for you" - always only the END of the sentence.

Measured cause: the AMD "Microphone Array" driver (with AMD noise suppression +
echo cancellation) needs ~215 ms to open a stream and then delivers ~1.0 s of
pure zeros. The old code opened a NEW stream for every utterance (and another
one for noise calibration), so the first ~1.2 s of speech after the beep was
silently discarded. Whisper then guessed at the fragment.

Fix (`scripts/audio_io.py` `Microphone`):
- One persistent, always-open input stream feeding a 30 s ring buffer.
- Capture starts at a mark taken at the beep, so no words are lost; all audio
  from the mark is kept and Whisper's Silero VAD trims silence.
- Adaptive threshold from the live noise floor (20th percentile of recent
  blocks) instead of a fresh-stream calibration that only measured zeros.
- Phantom guard: segments flagged as non-speech and classic silence phrases
  ("Thank you.", "Thanks for watching") are discarded.
- Dashboard shows capture stats and a player for `GET /api/audio/mic/last.wav`
  so you can hear exactly what the mic captured.

Note: because of AMD echo cancellation, audio played by the laptop speaker is
removed from the mic signal. Speaker->mic loopback tests do not work on this
laptop; test with a real voice.
