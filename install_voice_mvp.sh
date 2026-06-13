#!/usr/bin/env bash
# GARVIS Voice MVP Installer
# Run: cd ~/GARVIS && bash install_voice_mvp.sh
set -e

cd ~/GARVIS
mkdir -p runtime/voice scripts

echo "[GARVIS] Writing runtime/voice/stt_local.py"
cat > runtime/voice/stt_local.py <<'_EOF_'
"""Local STT — single-shot speech-to-text with faster-whisper."""
from __future__ import annotations

import asyncio
import io
import logging
import wave
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger("garvis.stt")

SAMPLE_RATE = 16000
RECORD_SECONDS = 5
CHANNELS = 1
MODEL_SIZE = "base"  # tiny, base, small
DEVICE = "auto"
COMPUTE_TYPE = "int8"


def record_audio(duration_sec: int = RECORD_SECONDS, sample_rate: int = SAMPLE_RATE) -> bytes:
    """Record audio from microphone, return WAV bytes."""
    import sounddevice as sd

    print(f"🎤 Recording for {duration_sec} seconds...", flush=True)

    samples = sd.rec(
        int(duration_sec * sample_rate),
        samplerate=sample_rate,
        channels=CHANNELS,
        dtype=np.float32,
    )
    sd.wait()

    samples_int16 = (samples.flatten() * 32767).astype(np.int16)

    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples_int16.tobytes())

    print("🎤 Recording done.", flush=True)
    return wav_io.getvalue()


def transcribe_wav(wav_bytes: bytes) -> str:
    """Transcribe WAV bytes to text using faster-whisper."""
    from faster_whisper import WhisperModel

    print("🧠 Transcribing...", flush=True)

    if not hasattr(transcribe_wav, "_model"):
        transcribe_wav._model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
        print(f"   Loaded faster-whisper: {MODEL_SIZE}", flush=True)

    model: Any = transcribe_wav._model

    with io.BytesIO(wav_bytes) as wav_io:
        with wave.open(wav_io, "rb") as wf:
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)
            audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

    segments, info = model.transcribe(audio, language="en", vad_filter=True, condition_on_previous_text=True)
    text = " ".join(seg.text.strip() for seg in segments).strip()

    print(f'📝 Transcription: "{text}"', flush=True)
    return text


async def transcribe_microphone(duration_sec: int = RECORD_SECONDS) -> str:
    """Record from microphone and transcribe. Async wrapper."""
    loop = asyncio.get_event_loop()
    wav_bytes = await loop.run_in_executor(None, record_audio, duration_sec)
    text = await loop.run_in_executor(None, transcribe_wav, wav_bytes)
    return text
_EOF_

echo "[GARVIS] Writing runtime/voice/tts_local.py"
cat > runtime/voice/tts_local.py <<'_EOF_'
"""Local TTS — single-shot text-to-speech with Piper."""
from __future__ import annotations

import io
import wave
from pathlib import Path
from typing import Any

import numpy as np

VOICE_MODEL = "en_US-lessac-medium"
MODEL_DIR = Path("models/piper")
LENGTH_SCALE = 1.0


def _find_model_files() -> tuple[Path, Path]:
    model_path = MODEL_DIR / f"{VOICE_MODEL}.onnx"
    config_path = MODEL_DIR / f"{VOICE_MODEL}.onnx.json"
    if not model_path.exists():
        for c in [Path(f"{VOICE_MODEL}.onnx"), Path.home() / ".local/share/piper" / f"{VOICE_MODEL}.onnx"]:
            if c.exists():
                return c, c.with_suffix("").with_suffix(".onnx.json")
    return model_path, config_path


def synthesize(text: str) -> bytes:
    """Synthesize text into WAV bytes using Piper."""
    from piper import PiperVoice

    model_path, config_path = _find_model_files()

    if not model_path.exists():
        raise FileNotFoundError(
            f"Piper model not found: {model_path}\n"
            f"Run: bash scripts/download_piper_model.sh"
        )

    if not hasattr(synthesize, "_voice"):
        synthesize._voice = PiperVoice.load(
            model_path=str(model_path),
            config_path=str(config_path) if config_path.exists() else None,
            use_cuda=False,
        )
        print(f"   Loaded Piper voice: {VOICE_MODEL}", flush=True)

    voice: Any = synthesize._voice

    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(22050)
        for chunk in voice.synthesize(text, length_scale=LENGTH_SCALE):
            wf.writeframes(chunk)
    return wav_io.getvalue()


def play_wav(wav_bytes: bytes) -> None:
    """Play WAV bytes through default audio output."""
    import sounddevice as sd

    with io.BytesIO(wav_bytes) as wav_io:
        with wave.open(wav_io, "rb") as wf:
            n_frames = wf.getnframes()
            sr = wf.getframerate()
            raw = wf.readframes(n_frames)
            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

    print("🔊 Playing...", flush=True)
    sd.play(samples, sr)
    sd.wait()
    print("🔊 Done.", flush=True)


def speak(text: str) -> None:
    """Synthesize and play text in one call."""
    if not text or not text.strip():
        return
    print(f'🔊 Synthesizing: "{text[:80]}{"..." if len(text) > 80 else ""}"', flush=True)
    wav = synthesize(text)
    if wav:
        play_wav(wav)
_EOF_

echo "[GARVIS] Writing runtime/voice/voice_runtime_loop.py"
cat > runtime/voice/voice_runtime_loop.py <<'_EOF_'
"""GARVIS Voice MVP Loop — one-shot voice conversation.

Mic → STT → Runtime → TTS → Speaker

Usage:
    cd ~/GARVIS && python runtime/voice/voice_runtime_loop.py
"""
from __future__ import annotations

import asyncio
import sys

import httpx

from runtime.voice.stt_local import transcribe_microphone
from runtime.voice.tts_local import speak

API_BASE = "http://localhost:8000"
SESSION_ID = "voice-mvp"
RECORD_DURATION = 5


async def main() -> None:
    print("=" * 50)
    print("  GARVIS Voice MVP")
    print("  Mic → STT → Runtime → TTS → Speaker")
    print("=" * 50)

    # Record + Transcribe
    print("\n[1/3] 🎤 Listening... (speak now)")
    try:
        user_text = await transcribe_microphone(duration_sec=RECORD_DURATION)
    except RuntimeError as exc:
        print(f"\n❌ STT Error: {exc}")
        sys.exit(1)

    if not user_text.strip():
        print("\n❌ No speech detected.")
        sys.exit(0)

    # Send to GARVIS runtime
    print(f'\n[2/3] 📤 Sending: "{user_text}"')
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{API_BASE}/api/v1/runtime/command",
                json={"text": user_text, "source": "voice", "session_id": SESSION_ID},
            )
            result = response.json()
    except Exception as exc:
        print(f"\n❌ Runtime Error: {exc}")
        sys.exit(1)

    response_text = result.get("response_text", "")
    print(f'   Status: {result.get("status")}')
    print(f'   Governance: {result.get("governance_decision", {}).get("decision")}')

    # Speak response
    if response_text:
        print(f'\n[3/3] 📥 Response: "{response_text[:120]}{"..." if len(response_text) > 120 else ""}"')
        print("\n🔊 Speaking...")
        try:
            speak(response_text)
        except RuntimeError as exc:
            print(f"\n❌ TTS Error: {exc}")
            sys.exit(1)

    print("\n✅ Done.")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
_EOF_

echo "[GARVIS] Writing runtime/voice/microphone_test.py"
cat > runtime/voice/microphone_test.py <<'_EOF_'
"""Microphone test — record and playback."""
from __future__ import annotations

import io
import wave

import numpy as np


def test_microphone(duration_sec: int = 3) -> None:
    import sounddevice as sd

    print(f"🎤 Recording {duration_sec} seconds...")
    sample_rate = 16000
    samples = sd.rec(int(duration_sec * sample_rate), samplerate=sample_rate, channels=1, dtype=np.float32)
    sd.wait()

    print("🔊 Playing back...")
    sd.play(samples, sample_rate)
    sd.wait()

    samples_int16 = (samples.flatten() * 32767).astype(np.int16)
    with wave.open("/tmp/mic_test.wav", "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples_int16.tobytes())

    print("✅ Saved to /tmp/mic_test.wav")


if __name__ == "__main__":
    test_microphone()
_EOF_

echo "[GARVIS] Writing scripts/test_voice_loop.py"
cat > scripts/test_voice_loop.py <<'_EOF_'
"""Validate voice MVP components (structural only)."""
from __future__ import annotations

import sys

_all_passed = True


def _pass(msg: str) -> None:
    print(f"  [PASS] {msg}")


def _fail(msg: str) -> None:
    global _all_passed
    _all_passed = False
    print(f"  [FAIL] {msg}")


def main() -> None:
    print("=" * 50)
    print("  GARVIS Voice MVP Validation")
    print("=" * 50)

    try:
        from runtime.voice.stt_local import transcribe_microphone
        _pass("stt_local imports OK")
    except ImportError as e:
        _fail(f"stt_local: {e}")

    try:
        from runtime.voice.tts_local import speak
        _pass("tts_local imports OK")
    except ImportError as e:
        _fail(f"tts_local: {e}")

    try:
        from runtime.voice.voice_runtime_loop import API_BASE, SESSION_ID
        assert API_BASE == "http://localhost:8000"
        assert SESSION_ID == "voice-mvp"
        _pass("voice_runtime_loop OK")
    except Exception as e:
        _fail(f"voice_runtime_loop: {e}")

    try:
        import httpx
        r = httpx.get("http://localhost:8000/api/v1/status/health", timeout=5.0)
        _pass(f"API healthy ({r.json().get('status')})" if r.status_code == 200 else "API unhealthy")
    except Exception as e:
        _fail(f"API: {e}")

    from pathlib import Path
    if (Path("models/piper") / "en_US-lessac-medium.onnx").exists():
        _pass("Piper model found")
    else:
        _fail("Piper model missing — run: bash scripts/download_piper_model.sh")

    print("\n" + "=" * 50)
    print("  ALL PASSED" if _all_passed else "  SOME FAILED")
    print("=" * 50)
    sys.exit(0 if _all_passed else 1)


if __name__ == "__main__":
    main()
_EOF_

echo "[GARVIS] Writing scripts/download_piper_model.sh"
cat > scripts/download_piper_model.sh <<'_EOF_'
#!/usr/bin/env bash
set -e
echo "[GARVIS] Downloading Piper voice model..."
mkdir -p models/piper
cd models/piper
MODEL="en_US-lessac-medium"
BASE="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium"
if [[ -f "${MODEL}.onnx" && -f "${MODEL}.onnx.json" ]]; then
    echo "  Model already exists."; exit 0
fi
wget -q --show-progress "${BASE}/${MODEL}.onnx" -O "${MODEL}.onnx" || curl -L -o "${MODEL}.onnx" "${BASE}/${MODEL}.onnx"
wget -q --show-progress "${BASE}/${MODEL}.onnx.json" -O "${MODEL}.onnx.json" || curl -L -o "${MODEL}.onnx.json" "${BASE}/${MODEL}.onnx.json"
echo "  Done: $(ls -lh ${MODEL}.onnx ${MODEL}.onnx.json)"
_EOF_

chmod +x scripts/download_piper_model.sh

echo ''
echo '========================================'
echo '  Voice MVP installed — 6 files'
echo '========================================'
echo ''
echo 'Install deps:'
echo '  sudo apt install -y portaudio19-dev libsndfile1 ffmpeg espeak-ng'
echo '  pip install faster-whisper piper-tts sounddevice numpy httpx'
echo ''
echo 'Download voice:'
echo '  bash scripts/download_piper_model.sh'
echo ''
echo 'Test mic:'
echo '  python runtime/voice/microphone_test.py'
echo ''
echo 'Run voice loop:'
echo '  python runtime/voice/voice_runtime_loop.py'
echo ''
echo 'Validate:'
echo '  python scripts/test_voice_loop.py'
