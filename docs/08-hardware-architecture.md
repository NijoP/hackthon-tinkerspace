# 08 — Hardware Architecture

## MVP hardware

- One Windows laptop acting as local server and audio output device.
- One Seeed Studio XIAO ESP32-S3 camera-capable board / Sense variant.
- One camera.
- Wi-Fi connection between ESP32 and laptop local server.

## Data flow

```text
XIAO ESP32-S3 camera
    -> JPEG/frame capture
    -> HTTP or WebSocket upload over Wi-Fi
    -> FastAPI local server
    -> live detection + graph query + task state
    -> laptop speaker guidance
```

## ESP32 boundary

The ESP32 must remain simple:

- initialize camera,
- connect to Wi-Fi,
- capture visual frames/JPEGs,
- send frames to local server,
- report basic device status,
- perform minimal transport/control logic.

It must not run AI models, graph logic, semantic reasoning, task planning, LLMs, or haptics.

## Board verification requirement

Before final PlatformIO configuration, physically verify the exact XIAO ESP32-S3 board variant. The documented PlatformIO board identifier for XIAO ESP32-S3 is commonly:

```text
seeed_xiao_esp32s3
```

Do not assume this without final hardware confirmation.
