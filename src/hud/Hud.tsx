import { useEffect, useState } from "react";
import { startSpeaking, stopSpeaking } from "../scene/voiceLevel";
import { LeftIntelRail, RightIntelRail } from "../intel/IntelHub";
import { MeshyAssetStrip } from "../intel/MeshyIntelAssets";

const QUICK_ACTIONS = [
  "Tell Me",
  "Show Me",
  "Open",
  "Run",
  "Analyze",
  "Summarize",
  "Create",
  "Check",
];

/* ---------- small inline icons (no emoji) ---------- */
function HexIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className}>
      <path d="M12 2.5l8 4.6v9.8l-8 4.6-8-4.6V7.1l8-4.6z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
    </svg>
  );
}
function ShieldIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className}>
      <path d="M12 3l7 3v5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
    </svg>
  );
}
function ChipIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className}>
      <rect x="6" y="6" width="12" height="12" rx="1.5" stroke="currentColor" strokeWidth="1.4" />
      <path d="M9 9h6v6H9z" stroke="currentColor" strokeWidth="1" opacity="0.6" />
      <path d="M9 3v2M15 3v2M9 19v2M15 19v2M3 9h2M3 15h2M19 9h2M19 15h2" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}
function VoiceIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className}>
      <path d="M4 12h2M8 8v8M12 5v14M16 8v8M20 12h0" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}
function UserIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className}>
      <circle cx="12" cy="8" r="3.2" stroke="currentColor" strokeWidth="1.4" />
      <path d="M5 20c0-3.6 3.1-6 7-6s7 2.4 7 6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

/** Animated voice waveform — a row of bars that pulse like an audio meter. */
function Waveform({ bars = 18, className = "", color = "#7dd3fc" }: { bars?: number; className?: string; color?: string }) {
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((x) => x + 1), 120);
    return () => clearInterval(id);
  }, []);
  const t = Date.now() / 200;
  return (
    <div className={`flex items-center gap-[2px] ${className}`}>
      {Array.from({ length: bars }).map((_, i) => {
        const h = 2 + Math.abs(Math.sin(t + i * 0.6)) * 12;
        return (
          <span
            key={i}
            className="inline-block w-[2px] rounded-full"
            style={{ height: `${h}px`, background: color, boxShadow: `0 0 6px ${color}` }}
          />
        );
      })}
    </div>
  );
}

function useClock() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return now;
}

function StatusItem({ Icon, label, value, color }: { Icon: (p: { className?: string }) => JSX.Element; label: string; value: string; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <Icon className="h-4 w-4" />
      <div className="leading-none">
        <div className="hud-label text-[8px] text-sky-300/50">{label}</div>
        <div className="hud-label hud-glow text-[10px]" style={{ color }}>{value}</div>
      </div>
    </div>
  );
}

function TopHud() {
  const now = useClock();
  const time = now.toLocaleTimeString("en-GB", { hour12: false });
  const weekday = now.toLocaleDateString("en-GB", { weekday: "long" }).toUpperCase();
  const date = now
    .toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })
    .toUpperCase();

  return (
    <header className="pointer-events-none absolute inset-x-0 top-0 z-20 px-6 pt-4">
      <div className="flex items-start justify-between">
        {/* left: wordmark in an angled frame */}
        <div className="hud-frame flex items-center gap-3 px-4 py-2">
          <div className="relative flex h-9 w-9 items-center justify-center text-sky-200">
            <HexIcon className="absolute inset-0 h-9 w-9 text-sky-400/60" />
            <span className="hud-glow text-sm font-bold text-sky-100">J</span>
          </div>
          <div className="leading-tight">
            <div className="hud-label hud-glow text-base text-sky-50" style={{ letterSpacing: "0.45em" }}>JARVIS</div>
            <div className="hud-label text-[8px] text-sky-300/50">AI Operating Environment</div>
          </div>
        </div>

        {/* center: weekday / date / clock */}
        <div className="hidden flex-col items-center md:flex">
          <div className="flex items-center gap-4">
            <span className="hud-label text-[9px] text-sky-300/50">{weekday}</span>
            <span className="hud-label text-[9px] text-sky-300/50">{date}</span>
          </div>
          <div className="hud-mono hud-glow text-3xl font-light tracking-[0.18em] text-sky-50">{time}</div>
          <div className="hud-label text-[8px] text-sky-300/40">System Time</div>
        </div>

        {/* right: status row with icons + voice waveform */}
        <div className="hud-frame flex items-center gap-5 px-4 py-2">
          <StatusItem Icon={ShieldIcon} label="System" value="Operational" color="#34d399" />
          <StatusItem Icon={ChipIcon} label="Cognition" value="Active" color="#38bdf8" />
          <StatusItem Icon={VoiceIcon} label="Voice" value="Online" color="#34d399" />
          <Waveform bars={16} className="h-5" />
        </div>
      </div>
    </header>
  );
}

function CommandBar() {
  const [focused, setFocused] = useState(false);
  const [value, setValue] = useState("");

  // Make the core "speak": pulse it for a duration scaled to the reply length.
  // (When the real backend is wired, drive this from the TTS audio analyser instead.)
  const speak = (durationMs: number) => {
    startSpeaking();
    window.setTimeout(() => stopSpeaking(), durationMs);
  };

  const submit = () => {
    const text = value.trim();
    if (!text) return;
    speak(1600 + Math.min(4000, text.length * 60)); // core pulses as if answering
    setValue("");
  };

  return (
    <div className="px-6">
      {/* listening cue */}
      <div className="mb-3 flex justify-center">
        <span
          className={`hud-label text-[10px] tracking-[0.5em] text-sky-300/60 ${
            focused ? "listening text-sky-200" : ""
          }`}
        >
          {focused ? "Listening…" : "JARVIS standing by"}
        </span>
      </div>

      {/* input */}
      <div className="mx-auto max-w-3xl">
        <div
          className={`hud-panel bracket relative flex items-center gap-3 overflow-hidden px-4 py-3 transition-all duration-500 ${
            focused ? "border-sky-300/60 shadow-[0_0_40px_-8px_rgba(56,189,248,0.6)]" : ""
          }`}
        >
          {focused && (
            <span className="sweep pointer-events-none absolute inset-y-0 left-0 w-1/3 bg-gradient-to-r from-transparent via-sky-400/10 to-transparent" />
          )}
          <span className="pulse-dot h-2 w-2 rounded-full bg-sky-400 text-sky-400" />
          <input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
            placeholder="TYPE YOUR COMMAND…"
            className="hud-label flex-1 bg-transparent text-xs tracking-[0.25em] text-sky-50 outline-none placeholder:text-sky-300/30"
          />
          <button onClick={submit} className="group flex h-8 w-8 items-center justify-center rounded-sm border border-sky-400/40 transition-all hover:border-sky-200 hover:bg-sky-400/10">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="text-sky-200">
              <path d="M4 12h14M12 5l7 7-7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>

        {/* quick actions */}
        <div className="mt-3 flex flex-wrap items-center justify-center gap-2">
          {QUICK_ACTIONS.map((a) => (
            <button
              key={a}
              onClick={() => speak(1400)}
              className="hud-label rounded-sm border border-sky-400/15 bg-sky-400/[0.03] px-3 py-1.5 text-[9px] text-sky-200/70 transition-all hover:border-sky-300/60 hover:bg-sky-400/10 hover:text-sky-50 hover:shadow-[0_0_20px_-6px_rgba(56,189,248,0.8)]"
            >
              {a}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function Footer() {
  return (
    <div className="pointer-events-none flex items-end justify-between px-8 pt-4">
      {/* left: owner */}
      <div className="flex items-center gap-3">
        <div className="relative flex h-9 w-9 items-center justify-center text-sky-200">
          <HexIcon className="absolute inset-0 h-9 w-9 text-sky-400/50" />
          <UserIcon className="h-4 w-4" />
        </div>
        <div className="leading-tight">
          <div className="hud-label text-[8px] text-sky-300/45">Owner</div>
          <div className="hud-label hud-glow text-sm text-sky-50">STAS</div>
          <div className="hud-label text-[8px] text-sky-300/45">Commander</div>
        </div>
      </div>
      {/* right: execution layer + waveform */}
      <div className="flex items-center gap-3">
        <div className="text-right leading-tight">
          <div className="hud-label text-[8px] text-sky-300/45">Execution Layer</div>
          <div className="hud-label hud-glow text-sm text-emerald-300">Silent Mode</div>
        </div>
        <Waveform bars={14} className="h-5" color="#34d399" />
      </div>
    </div>
  );
}

export default function Hud() {
  return (
    <div className="pointer-events-none absolute inset-0 z-10">
      {/* atmosphere */}
      <div className="vignette pointer-events-none absolute inset-0 z-0" />
      <div className="scanlines pointer-events-none absolute inset-0 z-0" />

      <TopHud />
      {/* Intel Hub readout rails — diegetic HUD framing the living core (display only) */}
      <LeftIntelRail />
      <RightIntelRail />

      {/* bottom stack: command bar + corner footer, never overlapping */}
      <div className="absolute inset-x-0 bottom-0 z-20 pb-5">
        <MeshyAssetStrip />
        <div className="pointer-events-auto">
          <CommandBar />
        </div>
        <Footer />
      </div>
    </div>
  );
}
