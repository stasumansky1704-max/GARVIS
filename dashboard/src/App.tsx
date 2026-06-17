import { useEffect, useState } from "react";
import HolographicEarth3D from "./components/HolographicEarth3D";
import LivingCore from "./living-core/LivingCore";
import StatusBadge from "./components/StatusBadge";
import {
  FACTORIES,
  INTEL_LAYERS,
  factoriesSummary,
  intelSummary,
} from "./data/missionControl";

type Page = "home" | "workflows" | "intelligence" | "settings";

const pageTitles: Record<Page, string> = {
  home: "HOME",
  workflows: "FACTORIES",
  intelligence: "INTELLIGENCE HUB",
  settings: "SETTINGS",
};

export default function App() {
  const [page, setPage] = useState<Page>("home");
  const [audioIntensity, setAudioIntensity] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setAudioIntensity((prev) => prev + (Math.random() * 0.28 - prev) * 0.08);
    }, 50);

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "1") setPage("home");
      if (event.key === "2") setPage("workflows");
      if (event.key === "3") setPage("intelligence");
      if (event.key === "4") setPage("settings");
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <div className="jarvis-app">
      <nav className="jarvis-nav">
        <div className="jarvis-logo">
          <div className="jarvis-logo-mark">J</div>
          <div>
            <div className="jarvis-logo-text">JARVIS</div>
            <div className="jarvis-logo-sub">AI OPERATING ENVIRONMENT</div>
          </div>
        </div>

        <div className="jarvis-nav-links">
          {(["home", "workflows", "intelligence", "settings"] as Page[]).map((item) => (
            <button
              key={item}
              className={`jarvis-nav-link ${page === item ? "active" : ""}`}
              onClick={() => setPage(item)}
            >
              <span>{pageTitles[item]}</span>
            </button>
          ))}
        </div>

        <div className="jarvis-top-status">
          <span className="status-dot" />
          <span>SYSTEM LIVE</span>
        </div>
      </nav>

      <main className="jarvis-main">
        {page === "home" && <HomePage audioIntensity={audioIntensity} />}
        {page === "workflows" && <WorkflowsPage />}
        {page === "intelligence" && <IntelligencePage audioIntensity={audioIntensity} />}
        {page === "settings" && <SettingsPage />}
      </main>
    </div>
  );
}

function HomePage({ audioIntensity: _audioIntensity }: { audioIntensity: number }) {
  // The Living AI Core Chamber IS the home screen (not a dashboard).
  // Full-bleed WebGL core + HUD, wired to the real GARVIS backend.
  return <LivingCore />;
}

function WorkflowsPage() {
  return (
    <section className="page-screen">
      <PageHeader title="FACTORIES" subtitle={factoriesSummary()} />

      <div className="factory-grid">
        {FACTORIES.map((f) => (
          <article className="factory-card" key={f.id}>
            <div className="factory-card-top">
              <span className="factory-glyph" aria-hidden>{f.glyph}</span>
              <StatusBadge status={f.status} />
            </div>
            <h3>{f.name}</h3>
            <p>{f.summary}</p>
          </article>
        ))}
      </div>

      <p className="surface-note">
        Business factories only. Internal engine capabilities (research, loop, run-due,
        review, schedule) are not user workflows and are intentionally hidden. No factory
        shows “Active” until it is wired to a real capability.
      </p>
    </section>
  );
}

function IntelligencePage({ audioIntensity }: { audioIntensity: number }) {
  // The holographic Earth is the hero. Layer cards sit in side rails so they never
  // block the globe (cybernetic command-center framing, not a dashboard grid).
  const left = INTEL_LAYERS.slice(0, 3);
  const right = INTEL_LAYERS.slice(3);

  return (
    <section className="intel-screen">
      <div className="earth-stage">
        <HolographicEarth3D audioIntensity={audioIntensity} />
      </div>

      <div className="intel-overlay">
        <header className="intel-header">
          <h1>INTELLIGENCE HUB</h1>
          <p>{intelSummary()}</p>
        </header>

        <div className="intel-rails">
          <div className="intel-rail intel-rail--left">
            {left.map((l) => <IntelCard key={l.id} layer={l} />)}
          </div>
          <div className="intel-rail intel-rail--right">
            {right.map((l) => <IntelCard key={l.id} layer={l} />)}
          </div>
        </div>
      </div>
    </section>
  );
}

function IntelCard({ layer }: { layer: (typeof INTEL_LAYERS)[number] }) {
  return (
    <article className="intel-card">
      <div className="intel-card-top">
        <span className="intel-glyph" aria-hidden>{layer.glyph}</span>
        <span className="intel-card-title">{layer.name}</span>
        <StatusBadge status={layer.connection} />
      </div>
      <p>{layer.summary}</p>
      <div className="intel-card-foot">
        <StatusBadge status={layer.maturity} />
      </div>
    </article>
  );
}

function SettingsPage() {
  return (
    <section className="page-screen">
      <PageHeader title="SETTINGS" subtitle="Voice, runtime, memory, cognition and behavior controls" />

      <div className="settings-grid">
        <SettingsCard
          title="VOICE"
          rows={[
            ["Input", "Whisper local"],
            ["Output", "Windows TTS / future ElevenLabs"],
            ["Language", "Later phase"],
          ]}
        />

        <SettingsCard
          title="RUNTIME"
          rows={[
            ["Backend", "localhost"],
            ["Docker", "Running"],
            ["API", "Connected later"],
          ]}
        />

        <SettingsCard
          title="BEHAVIOR CORE"
          rows={[
            ["Iron Rule", "JARVIS adapts to Stas"],
            ["Anti-flattery", "Enabled"],
            ["Critical Guardian", "Enabled"],
          ]}
        />

        <SettingsCard
          title="MEMORY"
          rows={[
            ["Long term", "Future"],
            ["Context", "Future"],
            ["Training", "Simulation phase later"],
          ]}
        />
      </div>
    </section>
  );
}

function PageHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <header className="page-header">
      <h1>{title}</h1>
      <p>{subtitle}</p>
    </header>
  );
}

function SettingsCard({ title, rows }: { title: string; rows: string[][] }) {
  return (
    <div className="settings-card">
      <h3>{title}</h3>
      {rows.map(([label, value]) => (
        <div className="settings-row" key={label}>
          <span>{label}</span>
          <strong>{value}</strong>
        </div>
      ))}
    </div>
  );
}
