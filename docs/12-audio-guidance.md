# 12 — Audio Guidance

## Output channel

Primary feedback channel for the MVP is the laptop speaker.

Do not depend on Bluetooth audio through the ESP32.

## Initial TTS choice

Use pyttsx3 / Windows SAPI-compatible speech first because it is local and practical for a Windows hackathon demo.

A neural local TTS such as Piper may be evaluated later only if time allows and the basic system already works.

## Repetition control

Implement cooldown logic so the same sentence is not spoken constantly. Guidance should be understandable, timely, and not overwhelming.

## Example messages

- `Welcome to the kitchen.`
- `The kettle is on your right.`
- `Move forward slowly.`
- `The cup is beside the kettle.`
- `I am not certain. Please stop.`
- `Task complete.`

## Test expectation

A local test must prove that text can be converted to audible speech through the laptop speaker.
