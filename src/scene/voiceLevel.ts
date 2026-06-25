// Shared "is GARVIS speaking" intensity (0..1), read by the core every frame.
// Drive it from anywhere: setVoiceLevel(x) on each audio frame, or
// startSpeaking()/stopSpeaking() for a simulated pulse when no real audio is wired yet.

let target = 0;     // where we want the level to go
let current = 0;    // smoothed value the renderer reads
let speaking = false;
let simPhase = 0;

/** Set instantaneous voice amplitude 0..1 (e.g. from an AnalyserNode RMS). */
export function setVoiceLevel(v: number) {
  target = Math.max(0, Math.min(1, v));
}

/** Begin a simulated speech pulse (use until real mic/TTS analyser is connected). */
export function startSpeaking() { speaking = true; }
export function stopSpeaking() { speaking = false; target = 0; }
export function isSpeaking() { return speaking; }

/** Called once per frame by the core; returns the smoothed 0..1 level. */
export function readVoiceLevel(dt: number, elapsed: number): number {
  if (speaking) {
    // organic speech-like envelope: layered sines + jitter
    simPhase += dt;
    const env =
      0.45 +
      Math.sin(elapsed * 11) * 0.25 +
      Math.sin(elapsed * 23 + 1.3) * 0.15 +
      Math.sin(elapsed * 37 + 0.7) * 0.1;
    target = Math.max(0.05, Math.min(1, env));
  }
  // smooth toward target (attack faster than release)
  const k = target > current ? 0.35 : 0.12;
  current += (target - current) * k;
  return current;
}

// Optional: connect a real audio stream (mic or TTS playback) as the source.
export function attachAnalyser(stream: MediaStream): () => void {
  const ctx = new AudioContext();
  const src = ctx.createMediaStreamSource(stream);
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 512;
  src.connect(analyser);
  const buf = new Uint8Array(analyser.frequencyBinCount);
  let raf = 0;
  const tick = () => {
    analyser.getByteTimeDomainData(buf);
    let sum = 0;
    for (let i = 0; i < buf.length; i++) { const x = (buf[i] - 128) / 128; sum += x * x; }
    setVoiceLevel(Math.min(1, Math.sqrt(sum / buf.length) * 3));
    raf = requestAnimationFrame(tick);
  };
  tick();
  return () => { cancelAnimationFrame(raf); ctx.close(); };
}
