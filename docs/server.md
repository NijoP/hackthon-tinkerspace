# Server

## Framework

FastAPI local server bound to `0.0.0.0` so the ESP32 can reach it over the phone hotspot LAN.

## Implemented skeleton

Current server skeleton lives in:

```text
server/app.py
```

Implemented endpoints:

- `GET /`
- `GET /health`
- `GET /status`
- `POST /api/frame`
- `GET /api/stream`
- placeholder graph/query/voice/task endpoints

## Latest-frame design

The server stores only the newest JPEG frame. It intentionally does not build an unbounded video queue. The dashboard reads the latest frame through an MJPEG stream.

## Run command

After Python is verified:

```powershell
cd C:\Users\HP\Downloads\hackathon
.\scripts\run_server.ps1
```

The script creates `.venv`, installs minimal server dependencies, and starts Uvicorn.
