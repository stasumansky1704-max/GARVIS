# Sprint: Voice Loop v2 — Current Decision

## Current Working Voice Pipeline

GARVIS currently works with:

```text
Windows microphone
→ sounddevice recording
→ faster-whisper base
→ GARVIS runtime API
→ Ollama response
→ pyttsx3 voice output