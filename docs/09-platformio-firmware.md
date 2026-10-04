# 09 — PlatformIO Firmware

## Firmware purpose

Provide a dumb camera edge device for the local laptop server.

## Planned components

- PlatformIO project dedicated to the actual XIAO ESP32-S3 hardware.
- Wi-Fi setup.
- Camera initialization.
- JPEG/frame capture.
- HTTP or WebSocket upload to the local FastAPI server.
- Basic heartbeat/status endpoint or message.
- Simple error handling and reconnect logic.

## Not allowed in firmware

- AI libraries.
- LLMs.
- Knowledge graph logic.
- Task planning.
- Natural language generation.
- Haptic feedback for this MVP.
- Unnecessary embedded dependencies.

## Board configuration gate

Before writing the final `platformio.ini`, verify the exact physical board and camera pin mapping. The likely PlatformIO board ID is:

```ini
board = seeed_xiao_esp32s3
```

But final firmware configuration must be based on the verified board variant.
