# 10 — Local Server API

## Framework

Use FastAPI for the local laptop server.

## Proposed endpoints

### Health

`GET /health`

Returns service status and version.

### Mapping video processing

`POST /mapping/process`

Starts or runs local processing for a configured video path.

### Graph

`GET /graph`

Returns the current Kitchen Knowledge Graph JSON.

`POST /graph/query`

Queries objects or relationships.

### Frame ingestion

`POST /frames`

Receives one camera frame/JPEG from the ESP32 or local test client.

### Task

`GET /task`

Returns current tea task state.

`POST /task/start`

Starts the deterministic tea task.

`POST /task/reset`

Resets the tea task state machine.

### Guidance

`GET /guidance`

Returns the current guidance text and optionally triggers TTS depending on implementation.

### Device status

`POST /device/status`

Receives heartbeat/status from the ESP32.

## API principle

Keep request/response bodies simple and inspectable. Prefer explicit JSON over hidden side effects.
