import { useEffect, useState } from "react";
import LivingCore from "./living-core/LivingCore";
import StatusBadge from "./components/StatusBadge";
import IntelHub from "./components/IntelHub";
import Factories3D from "./components/Factories3D";
import { FACTORIES, factoriesSummary } from "./data/missionControl";

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

  // Intelligence Hub is a full-bleed command center with its own chrome (sidebar). The
  // other screens (incl. Home / Living Core) keep the original top-nav frame, untouched.
  if (page === "intelligence") {
    return (
      <div className="jarvis-app">
        <IntelHub audioIntensity={audioIntensity} page={page} onNavigate={setPage} />
      </div>
    );
  }

  return (
    <div className="jarvis-app">
      <nav className="jarvis-nav">
        <div className="jarvis-logo">
          <div className="jarvis-logo-mark">J</div>
          <div>
            <div className="jarvis-logo-text">J.A.R.V.I.S.</div>
            <div className="jarvis-logo-sub">JUST A REALLY VERY INTELLIGENT SYSTEM</div>
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

const FLAGSHIP = ["youtube", "faceless", "education", "novagame", "alphaflow"];

function WorkflowsPage() {
  const flagships = FLAGSHIP
    .map((id) => FACTORIES.find((f) => f.id === id))
    .filter((f): f is (typeof FACTORIES)[number] => Boolean(f));
  return (
    <section className="page-screen">
      <PageHeader title="FACTORIES" subtitle={factoriesSummary()} />

      {/* Premium 3D factory cards — the 5 flagship factories as Intel-Hub-style hex monitors. */}
      <div className="factories3d-wrap">
        <Factories3D factories={flagships} />
      </div>

      {/* compact HTML list (always available; primary on small screens) */}
      <div className="factory-grid">
        {flagships.map((f) => (
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
