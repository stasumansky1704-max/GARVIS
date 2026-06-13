import sounddevice as sd
import numpy as np

SAMPLE_RATE = 16000
SECONDS = 3

print("Recording...")
audio = sd.rec(
    int(SECONDS * SAMPLE_RATE),
    samplerate=SAMPLE_RATE,
    channels=1,
    dtype=np.float32,
)
sd.wait()

print("Playing...")
sd.play(audio, SAMPLE_RATE)
sd.wait()

print("Done.")