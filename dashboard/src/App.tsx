import { useEffect, useState } from "react";
import JarvisCore3D from "./components/JarvisCore3D";
import HolographicEarth3D from "./components/HolographicEarth3D";

type Page = "home" | "workflows" | "intelligence" | "settings";

const pageTitles: Record<Page, string> = {
  home: "HOME",
  workflows: "WORKFLOWS",
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

function HomePage({ audioIntensity }: { audioIntensity: number }) {
  return (
    <section className="home-screen">
      <div className="home-bg-grid" />

      <div className="reactor-stage">
        <JarvisCore3D audioIntensity={audioIntensity} />
      </div>

      <div className="home-hud home-hud-left">
        <div className="hud-card">
          <div className="hud-label">SYSTEM</div>
          <div className="hud-value green">ONLINE</div>
          <div className="hud-small">Runtime local</div>
        </div>

        <div className="hud-card">
          <div className="hud-label">VOICE</div>
          <div className="hud-value cyan">STANDBY</div>
          <div className="hud-small">Awaiting command</div>
        </div>

        <div className="hud-card">
          <div className="hud-label">OPERATOR</div>
          <div className="hud-value">STAS</div>
          <div className="hud-small">Commander profile active</div>
        </div>
      </div>

      <div className="home-hud home-hud-right">
        <div className="hud-card">
          <div className="hud-label">MODE</div>
          <div className="hud-value cyan">OPERATOR</div>
          <div className="hud-small">Truth-first behavior</div>
        </div>

        <div className="hud-card">
          <div className="hud-label">AUDIO SIGNAL</div>
          <div className="audio-meter">
            <div className="audio-meter-fill" style={{ width: `${audioIntensity * 100}%` }} />
          </div>
          <div className="hud-small">{Math.round(audioIntensity * 100)}%</div>
        </div>

        <div className="hud-card">
          <div className="hud-label">CORE</div>
          <div className="hud-value green">READY</div>
          <div className="hud-small">Arc reactor shell active</div>
        </div>
      </div>

      <div className="home-title-block">
        <h1>JARVIS</h1>
        <p>Adaptive AI Operating Environment</p>
      </div>

      <div className="command-box">
        <span className="prompt-symbol">›</span>
        <input placeholder="Type your command..." />
        <button>VOICE</button>
        <button>SEND</button>
      </div>

      <div className="shortcut-row">
        <span>1 HOME</span>
        <span>2 WORKFLOWS</span>
        <span>3 INTELLIGENCE</span>
        <span>4 SETTINGS</span>
      </div>
    </section>
  );
}

function WorkflowsPage() {
  return (
    <section className="page-screen">
      <PageHeader title="WORKFLOWS" subtitle="Projects, missions, automations and operational workflows" />

      <div className="empty-panel">
        <div className="empty-icon">⚡</div>
        <h2>No active workflows yet</h2>
        <p>
          Workflows will appear here only when real workflows are created or connected.
          No fake production data.
        </p>
        <button className="primary-button">CREATE WORKFLOW</button>
      </div>
    </section>
  );
}

function IntelligencePage({ audioIntensity }: { audioIntensity: number }) {
  return (
    <section className="intel-screen">
      <div className="earth-stage">
        <HolographicEarth3D audioIntensity={audioIntensity} />
      </div>

      <div className="intel-overlay">
        <PageHeader
          title="INTELLIGENCE HUB"
          subtitle="World events, markets, sports, wrestling and live global awareness"
        />

        <div className="intel-layout">
          <div className="intel-panel">
            <h3>WORLD EVENTS</h3>
            <p>Feed not connected.</p>
            <span>Connect news source / event API</span>
          </div>

          <div className="intel-panel">
            <h3>STOCK MARKET</h3>
            <p>Market feed not connected.</p>
            <span>Connect index, stock and crypto feeds</span>
          </div>

          <div className="intel-panel">
            <h3>SPORTS / WRESTLING</h3>
            <p>Sports feed not connected.</p>
            <span>WWE, AEW, UFC, NBA, football and major events</span>
          </div>

          <div className="intel-panel">
            <h3>REVENUE</h3>
            <p>Revenue source not connected.</p>
            <span>Stripe / PayPal / custom endpoint later</span>
          </div>
        </div>
      </div>
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
