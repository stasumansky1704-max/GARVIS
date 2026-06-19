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

interface Card {
  id: string;
  title: string;
  glyph: string;
  need: string;
  state: string;
  maturity: string;
  accent: string;
  pos: { top: string; left: string };
  // Honest, forward-looking blueprint of what this layer COULD contain once wired.
  // These are NOT live and NOT internal engine workflows — they are placeholder intents.
  systems: string[];
}

// Six orbiting hex cards, pushed toward the edges so the Earth stays the hero. No live
// metrics; honest connection + maturity states only. Each has a distinct accent identity.
const CARDS: Card[] = [
  {
    id: "world", title: "WORLD INTELLIGENCE", glyph: "🌐", need: "news / event API",
    state: "Not Connected", maturity: "Blueprint", accent: "#8a7bff", pos: { top: "12%", left: "26%" },
    systems: ["Global event stream", "Geopolitical risk watch", "Region briefings"],
  },
  {
    id: "market", title: "MARKET NEXUS", glyph: "📈", need: "market data feeds",
    state: "Not Connected", maturity: "Blueprint", accent: "#2ee6b0", pos: { top: "12%", left: "74%" },
    systems: ["Index & crypto tape", "Sector heatmap", "Volatility radar"],
  },
  {
    id: "social", title: "SOCIAL RADAR", glyph: "☻", need: "platform APIs",
    state: "Not Connected", maturity: "Concept", accent: "#2f9bff", pos: { top: "46%", left: "9%" },
    systems: ["Sentiment pulse", "Trend detection", "Narrative tracking"],
  },
  {
    id: "revenue", title: "REVENUE COMMAND", glyph: "$", need: "Stripe / PayPal / custom",
    state: "Not Connected", maturity: "Blueprint", accent: "#ffb33e", pos: { top: "46%", left: "91%" },
    systems: ["Revenue stream", "MRR / churn view", "Payout monitor"],
  },
  {
    id: "tech", title: "TECHNOLOGY WATCH", glyph: "⌬", need: "research / source feed",
    state: "Not Connected", maturity: "Blueprint", accent: "#29d4ff", pos: { top: "80%", left: "26%" },
    systems: ["Research digest", "Release radar", "Security advisories"],
  },
  {
    id: "ops", title: "OPERATIONS CENTER", glyph: "⚙", need: "ops telemetry",
    state: "Not Connected", maturity: "Prototype", accent: "#19d39a", pos: { top: "80%", left: "74%" },
    systems: ["Service health", "Job queue view", "Incident timeline"],
  },
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

// Holographic detail drawer for a selected card. HONEST only: states the layer is not
// connected, lists the future data source + a blueprint of potential systems, and a
// voice-command hint. No live data, no internal engine workflows.
function CardDrawer({ card, onClose }: { card: Card; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <>
      <div className="ihub-drawer-scrim" onClick={onClose} aria-hidden />
      <aside
        className="ihub-drawer open"
        role="dialog"
        aria-label={`${card.title} details`}
        style={{ ["--accent" as string]: card.accent }}
      >
        <header className="ihub-drawer-head">
          <span className="ihub-drawer-glyph">{card.glyph}</span>
          <div>
            <h2>{card.title}</h2>
            <div className="ihub-drawer-sub">{card.maturity} · intelligence layer</div>
          </div>
          <button className="ihub-drawer-x" onClick={onClose} aria-label="Close details">✕</button>
        </header>

        <div className="ihub-drawer-state"><i /> {card.state}</div>

        <section className="ihub-drawer-sec">
          <h3>Future data source required</h3>
          <p className="ihub-drawer-need">{card.need}</p>
          <Placeholder text="Placeholder — no source connected yet" />
        </section>

        <section className="ihub-drawer-sec">
          <h3>Potential systems <span className="ihub-demo">BLUEPRINT</span></h3>
          <ul className="ihub-drawer-list">
            {card.systems.map((s) => (
              <li key={s}><span className="ihub-drawer-dot" /> {s} <em>not built</em></li>
            ))}
          </ul>
        </section>

        <footer className="ihub-drawer-foot">
          <span className="ihub-drawer-wave">⌁</span>
          Ask GARVIS to show this layer
        </footer>
      </aside>
    </>
  );
}

export default function IntelHub({ audioIntensity = 0, page, onNavigate }: Props) {
  // Screenshot-friendly mode (?capture=1): pauses animation + WebGL post-processing and
  // drops backdrop blur so the scene renders fast for capture. Normal mode is unaffected.
  const capture = useMemo(
    () => typeof window !== "undefined" &&
      new URLSearchParams(window.location.search).get("capture") === "1",
    []
  );

  const [clock, setClock] = useState("");
  const [activeCard, setActiveCard] = useState<Card | null>(null);
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);

  useEffect(() => {
    if (capture) { setClock("00:00:00"); return; }
    const tick = () => setClock(new Date().toLocaleTimeString([], { hour12: false }));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [capture]);

  const cards = useMemo(() => CARDS, []);
  const bodyClass = `ihub-body${leftOpen ? "" : " left-collapsed"}${rightOpen ? "" : " right-collapsed"}`;

  return (
    <div className={`ihub${capture ? " ihub-capture" : ""}`}>
      <div className={bodyClass}>
        {/* ---------- Left sidebar ---------- */}
        <aside className={`ihub-side${leftOpen ? "" : " collapsed"}`}>
          <div className="ihub-logo">
            <div className="ihub-logo-mark">J</div>
            <div className="ihub-logo-when-open">
              <div className="ihub-logo-text">J.A.R.V.I.S.</div>
              <div className="ihub-logo-sub">JUST A REALLY VERY INTELLIGENT SYSTEM</div>
            </div>
          </div>

          <button
            className="ihub-rail-toggle ihub-rail-toggle-left"
            onClick={() => setLeftOpen((v) => !v)}
            aria-label={leftOpen ? "Collapse navigation" : "Expand navigation"}
            aria-expanded={leftOpen}
          >
            {leftOpen ? "‹" : "›"}
          </button>

          <nav className="ihub-nav">
            {NAV.map((n) => (
              <button
                key={n.key}
                className={`ihub-nav-item ${page === n.key ? "active" : ""}`}
                title={n.label}
                onClick={() =>
                  ["home", "workflows", "intelligence", "settings"].includes(n.key as string) &&
                  onNavigate(n.key as Page)
                }
              >
                <span className="ihub-nav-glyph">{n.glyph}</span>
                <span className="ihub-nav-label">{n.label}</span>
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
              <HolographicEarth3D audioIntensity={capture ? 0 : audioIntensity} capture={capture} />
            </div>

            <div className="ihub-nodes">
              <svg className="ihub-links" viewBox="0 0 100 100" preserveAspectRatio="none">
                {cards.map((c) => (
                  <line
                    key={c.id}
                    x1={parseFloat(c.pos.left)}
                    y1={parseFloat(c.pos.top) + 5}
                    x2="50"
                    y2="48"
                    stroke={c.accent}
                    strokeWidth="0.12"
                    strokeOpacity="0.45"
                    strokeDasharray="0.6 0.9"
                  />
                ))}
              </svg>

              {cards.map((c) => (
                <article
                  key={c.id}
                  className={`ihub-hex${activeCard?.id === c.id ? " selected" : ""}`}
                  style={{ top: c.pos.top, left: c.pos.left, ["--accent" as string]: c.accent }}
                  role="button"
                  tabIndex={0}
                  aria-label={`${c.title} — ${c.state}. Open details`}
                  onClick={() => setActiveCard(c)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setActiveCard(c); }
                  }}
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
        <aside className={`ihub-right${rightOpen ? "" : " collapsed"}`}>
          <button
            className="ihub-rail-toggle ihub-rail-toggle-right"
            onClick={() => setRightOpen((v) => !v)}
            aria-label={rightOpen ? "Collapse panels" : "Expand panels"}
            aria-expanded={rightOpen}
          >
            {rightOpen ? "›" : "‹"}
          </button>

          <div className="ihub-right-inner">
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

      {activeCard && <CardDrawer card={activeCard} onClose={() => setActiveCard(null)} />}
    </div>
  );
}
