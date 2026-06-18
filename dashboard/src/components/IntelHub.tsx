import { useEffect, useMemo, useState } from "react";
import HolographicEarth3D from "./HolographicEarth3D";

// Full Intelligence Hub command center (page-scoped). Faithful live recreation of the
// reference layout, but with HONEST data only: no fake live numbers, no fake feeds, no
// fake "connected" states. Every data section is a clearly-labelled placeholder until a
// real source is wired. Home / Living Core are NOT touched by this component.

type Page = "home" | "workflows" | "intelligence" | "settings";

interface Props {
  audioIntensity?: number;
  page: Page;
  onNavigate: (p: Page) => void;
}

const NAV: { key: Page | string; label: string; glyph: string }[] = [
  { key: "home", label: "Mission Control", glyph: "▣" },
  { key: "intelligence", label: "Intelligence Hub", glyph: "◎" },
  { key: "workflows", label: "Factories", glyph: "⚙" },
  { key: "agents", label: "Agents", glyph: "☷" },
  { key: "memory", label: "Memory Graph", glyph: "❖" },
  { key: "health", label: "System Health", glyph: "♥" },
  { key: "settings", label: "Settings", glyph: "✦" },
];

// Six orbiting hex cards. No live metrics; honest connection + maturity states only.
const CARDS = [
  { id: "world", title: "WORLD INTELLIGENCE", glyph: "🌐", need: "news / event API",
    state: "Not Connected", maturity: "Blueprint", accent: "#b07bff", pos: { top: "8%", left: "31%" } },
  { id: "market", title: "MARKET NEXUS", glyph: "📈", need: "market data feeds",
    state: "Not Connected", maturity: "Blueprint", accent: "#34e0a1", pos: { top: "8%", left: "69%" } },
  { id: "social", title: "SOCIAL RADAR", glyph: "☻", need: "platform APIs",
    state: "Not Connected", maturity: "Concept", accent: "#2fb6ff", pos: { top: "40%", left: "15%" } },
  { id: "revenue", title: "REVENUE COMMAND", glyph: "$", need: "Stripe / PayPal / custom",
    state: "Not Connected", maturity: "Blueprint", accent: "#ffb33e", pos: { top: "40%", left: "85%" } },
  { id: "tech", title: "TECHNOLOGY WATCH", glyph: "⌬", need: "research / source feed",
    state: "Not Connected", maturity: "Blueprint", accent: "#2fb6ff", pos: { top: "73%", left: "31%" } },
  { id: "ops", title: "OPERATIONS CENTER", glyph: "⚙", need: "ops telemetry",
    state: "Not Connected", maturity: "Prototype", accent: "#34e0a1", pos: { top: "73%", left: "69%" } },
];

// Honest "what needs wiring" rows (NOT a live feed).
const SOURCES = [
  { cat: "WORLD", text: "Connect a news / event API" },
  { cat: "MARKETS", text: "Connect index / crypto feeds" },
  { cat: "TECH", text: "Connect a research source" },
  { cat: "SCIENCE", text: "No live source connected" },
];

const STAT_LABELS = ["CPU USAGE", "MEMORY", "GPU", "NETWORK", "DATABASE", "UPTIME"];
const CMD_EXAMPLES = ["Monitor global markets", "Track AI news", "Analyze social sentiment", "Watch security advisories"];

function Placeholder({ text = "Placeholder — not connected yet" }: { text?: string }) {
  return <div className="ihub-ph">◌ {text}</div>;
}

function Spark() {
  // Flat baseline (no fake data trend) — purely decorative axis.
  return (
    <svg className="ihub-spark" viewBox="0 0 90 16" preserveAspectRatio="none" aria-hidden>
      <line x1="0" y1="13" x2="90" y2="13" stroke="currentColor" strokeWidth="1" strokeOpacity="0.4" />
    </svg>
  );
}

export default function IntelHub({ audioIntensity = 0, page, onNavigate }: Props) {
  const [clock, setClock] = useState("");
  useEffect(() => {
    const tick = () => setClock(new Date().toLocaleTimeString([], { hour12: false }));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  const cards = useMemo(() => CARDS, []);

  return (
    <div className="ihub">
      <div className="ihub-body">
        {/* ---------- Left sidebar ---------- */}
        <aside className="ihub-side">
          <div className="ihub-logo">
            <div className="ihub-logo-mark">J</div>
            <div>
              <div className="ihub-logo-text">J.A.R.V.I.S.</div>
              <div className="ihub-logo-sub">JUST A REALLY VERY INTELLIGENT SYSTEM</div>
            </div>
          </div>

          <nav className="ihub-nav">
            {NAV.map((n) => (
              <button
                key={n.key}
                className={`ihub-nav-item ${page === n.key ? "active" : ""}`}
                onClick={() =>
                  ["home", "workflows", "intelligence", "settings"].includes(n.key as string) &&
                  onNavigate(n.key as Page)
                }
              >
                <span className="ihub-nav-glyph">{n.glyph}</span>
                <span>{n.label}</span>
              </button>
            ))}
          </nav>

          <div className="ihub-side-foot">
            <div className="ihub-status-card">
              <div className="ihub-status-row"><span>SYSTEM STATUS</span></div>
              <div className="ihub-status-state">PLACEHOLDER</div>
              <div className="ihub-status-sub">Not connected yet</div>
            </div>
            <blockquote className="ihub-quote">
              “The goal is not to be perfect, it is to be useful.”
              <cite>— J.A.R.V.I.S.</cite>
            </blockquote>
          </div>
        </aside>

        {/* ---------- Center stage ---------- */}
        <section className="ihub-center">
          <header className="ihub-top">
            <div>
              <h1>INTELLIGENCE HUB</h1>
              <p>REAL-TIME WORLD INTELLIGENCE OVERVIEW · PLACEHOLDER</p>
            </div>
            <div className="ihub-top-right">
              <span className="ihub-sync"><i /> PREVIEW MODE</span>
              <span className="ihub-clock">{clock}<small>LOCAL TIME</small></span>
            </div>
          </header>

          <div className="ihub-stage">
            <div className="ihub-globe">
              <HolographicEarth3D audioIntensity={audioIntensity} />
            </div>

            <svg className="ihub-links" viewBox="0 0 100 100" preserveAspectRatio="none">
              {cards.map((c) => (
                <line
                  key={c.id}
                  x1={parseFloat(c.pos.left)}
                  y1={parseFloat(c.pos.top) + 6}
                  x2="50"
                  y2="50"
                  stroke={c.accent}
                  strokeWidth="0.15"
                  strokeOpacity="0.5"
                  strokeDasharray="0.6 0.8"
                />
              ))}
            </svg>

            {cards.map((c) => (
              <article
                key={c.id}
                className="ihub-hex"
                style={{ top: c.pos.top, left: c.pos.left, ["--accent" as string]: c.accent }}
              >
                <div className="ihub-hex-inner">
                  <span className="ihub-hex-glyph">{c.glyph}</span>
                  <h3>{c.title}</h3>
                  <div className="ihub-hex-metric">needs {c.need}</div>
                  <div className="ihub-hex-state"><i /> {c.state}</div>
                  <div className="ihub-hex-mat">{c.maturity}</div>
                </div>
              </article>
            ))}
          </div>

          <div className="ihub-command">
            <span className="ihub-command-wave">⌁</span>
            <div>
              <strong>SPEAK TO GARVIS</strong>
              <small>command input — placeholder, not wired yet</small>
            </div>
          </div>
        </section>

        {/* ---------- Right rail ---------- */}
        <aside className="ihub-right">
          <div className="ihub-panel">
            <div className="ihub-panel-head">GLOBAL OVERVIEW</div>
            <div className="ihub-map" aria-hidden />
            <div className="ihub-overview">
              <div><b>—</b><span>COUNTRIES</span></div>
              <div><b>—</b><span>CITIES</span></div>
              <div><b>—</b><span>COVERAGE</span></div>
            </div>
            <Placeholder />
          </div>

          <div className="ihub-panel ihub-panel-grow">
            <div className="ihub-panel-head">INTELLIGENCE FEED <span className="ihub-demo">PLACEHOLDER</span></div>
            <ul className="ihub-feed">
              {SOURCES.map((f, i) => (
                <li key={i}>
                  <span className="ihub-feed-time">--:--</span>
                  <span className="ihub-feed-cat">{f.cat}</span>
                  <p>{f.text}</p>
                </li>
              ))}
            </ul>
            <Placeholder text="Placeholder — no live feed connected yet" />
          </div>

          <div className="ihub-panel">
            <div className="ihub-panel-head">ACTIVE COMMANDS <span className="ihub-demo">EXAMPLES</span></div>
            <ul className="ihub-cmds">
              {CMD_EXAMPLES.map((c) => <li key={c}>{c}</li>)}
            </ul>
            <Placeholder text="Placeholder — example commands, not active yet" />
          </div>
        </aside>
      </div>

      {/* ---------- Bottom stats bar ---------- */}
      <footer className="ihub-stats">
        {STAT_LABELS.map((label) => (
          <div className="ihub-stat" key={label}>
            <div className="ihub-stat-label">{label}</div>
            <div className="ihub-stat-value">—</div>
            <Spark />
          </div>
        ))}
        <div className="ihub-stat ihub-stat-note">Placeholder — not connected yet (no live metrics wired)</div>
      </footer>
    </div>
  );
}
