"""Self-test for the laptop audio layer (mic + transcription + speaker).

Usage:
  python scripts/test_audio.py --devices        # list audio devices
  python scripts/test_audio.py --tts            # speaker-only test
  python scripts/test_audio.py --mic            # record one VAD utterance
  python scripts/test_audio.py --loop           # full conversation loop test

By default (no flags) it runs a non-interactive smoke test: lists devices,
speaks one line, and confirms the mic can capture audio. This is safe to run
in a demo environment to prove the audio channel works end to end.
"""

from __future__ import annotations

import argparse

from audio_io import Microphone, Speaker, Transcriber, voice_turn, list_devices


def smoke() -> None:
    print(list_devices())
    print("\n-- Speaker test --")
    sp = Speaker()
    sp.beep_listening()
    sp.speak("Audio layer online. The laptop speaker is working.")
    print("\n-- Microphone capture test (2s, no words needed) --")
    mic = Microphone(calibrate=False)
    wav = mic.record_fixed(2.0)
    if wav is None:
        print("MIC: unavailable")
    else:
        size = wav.stat().st_size
        print(f"MIC: captured {size} bytes -> {wav}")
        wav.unlink(missing_ok=True)
        print("MIC OK" if size > 1000 else "MIC SILENT")


def tts_test() -> None:
    sp = Speaker()
    for voice in ("David", "Zira"):
        sp2 = Speaker(voice=voice)
        sp2.speak(f"This is the {voice} voice speaking through the laptop speaker.")


def mic_test() -> None:
    sp = Speaker()
    mic = Microphone()
    tr = Transcriber()
    sp.speak("Please say something after the beep.")
    text = voice_turn(mic, tr, sp)
    if text is None:
        sp.speak("I did not hear anything.")
    else:
        sp.speak(f"You said: {text}")
    print(f"Transcript: {text!r}")


def loop_test() -> None:
    sp = Speaker()
    mic = Microphone()
    tr = Transcriber()
    sp.speak("Conversation test. Talk to me after each beep. Say stop to end.")
    while True:
        text = voice_turn(mic, tr, sp)
        if text is None:
            continue
        print(f"Transcript: {text!r}")
        if "stop" in text.lower():
            sp.speak("Stopping the test. Goodbye.")
            break
        sp.speak(f"I heard: {text}")


def main() -> None:
    p = argparse.ArgumentParser(description="Audio layer self-test")
    p.add_argument("--devices", action="store_true")
    p.add_argument("--tts", action="store_true")
    p.add_argument("--mic", action="store_true")
    p.add_argument("--loop", action="store_true")
    args = p.parse_args()

    if args.devices:
        print(list_devices())
    elif args.tts:
        tts_test()
    elif args.mic:
        mic_test()
    elif args.loop:
        loop_test()
    else:
        smoke()


if __name__ == "__main__":
    main()
