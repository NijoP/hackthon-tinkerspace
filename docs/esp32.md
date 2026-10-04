# ESP32 Camera Node

## Hardware

Target hardware is one Seeed XIAO ESP32-S3 / XIAO ESP32-S3 Sense camera-capable board.

The exact physical board and camera variant still need to be confirmed before flashing.

## Firmware project

Current PlatformIO skeleton:

```text
firmware/
```

Important files:

- `firmware/platformio.ini`
- `firmware/src/main.cpp`
- `firmware/include/secrets.h.example`
- local ignored `firmware/include/secrets.h`

## Firmware scope

The firmware only:

- connects to Wi-Fi,
- initializes camera,
- captures JPEG frames,
- uploads frames to the local server,
- retries Wi-Fi/server connection.

It does not run AI, speech, graph logic, task planning, haptics, or natural language generation.

## Before flashing

1. Start the laptop server.
2. Open `GET /status` and record the LAN IP.
3. Put the laptop LAN IP into local `firmware/include/secrets.h` as `SERVER_HOST`.
4. Verify the board/camera variant and camera pin mapping.
5. Build/upload with PlatformIO.
