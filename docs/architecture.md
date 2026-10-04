# Architecture

## MVP architecture

```text
XIAO ESP32-S3 camera
  -> JPEG over Wi-Fi
  -> FastAPI local laptop server
  -> latest-frame buffer
  -> browser dashboard
  -> optional low-rate AI inference

Laptop microphone
  -> local speech-to-text
  -> question text
  -> graph query
  -> concise answer
  -> laptop speaker

Recorded kitchen video
  -> keyframes + audio
  -> visual understanding + transcription
  -> Kitchen Knowledge Graph JSON
```

## Priority order

1. ESP32 camera -> Wi-Fi -> laptop -> live dashboard.
2. Laptop microphone -> speech-to-text.
3. Question -> Kitchen Knowledge Graph -> answer.
4. Answer -> laptop speaker.
5. Video -> environment memory.
6. Live AI visual context.
7. Tea task integration.

## Hard boundaries

- ESP32 transports frames only.
- Laptop runs all intelligence.
- No GitHub dependency.
- No haptics in the MVP.
- No cloud inference.
- No Neo4j.
