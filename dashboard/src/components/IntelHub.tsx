import { useEffect, useMemo, useState } from "react";
import HolographicEarth3D from "./HolographicEarth3D";

// Full Intelligence Hub command-center (page-scoped). Faithful live recreation of the
// reference: left sidebar, orbiting hex cards + connectors, central living globe + radar
// base, right rail (overview / feed / commands), top bar, bottom stats bar.
// NOTE: numbers, feeds and "connected" states are SAMPLE/PLACEHOLDER (not wired to a real
// backend) - shown for layout fidelity and clearly labelled in the UI. Home / Living Core
// are NOT touched by this component.

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

// Six orbiting hex cards. Status is honest about wiring (none connected yet); the metric
// strings are clearly sample placeholders.
const CARDS = [
  { id: "world", title: "WORLD INTELLIGENCE", glyph: "🌐", metric: "— signals",
    state: "NOT CONNECTED", accent: "#b07bff", pos: { top: "8%", left: "31%" } },
  { id: "market", title: "MARKET NEXUS", glyph: "📈", metric: "— feeds",
    state: "NOT CONNECTED", accent: "#34e0a1", pos: { top: "8%", left: "69%" } },
  { id: "social", title: "SOCIAL RADAR", glyph: "☻", metric: "— posts",
    state: "NOT CONNECTED", accent: "#2fb6ff", pos: { top: "40%", left: "15%" } },
  { id: "revenue", title: "REVENUE COMMAND", glyph: "$", metric: "— streams",
    state: "NOT CONNECTED", accent: "#ffb33e", pos: { top: "40%", left: "85%" } },
  { id: "tech", title: "TECHNOLOGY WATCH", glyph: "⌬", metric: "— updates",
    state: "NOT CONNECTED", accent: "#2fb6ff", pos: { top: "73%", left: "31%" } },
  { id: "ops", title: "OPERATIONS CENTER", glyph: "⚙", metric: "— systems",
    state: "NOT CONNECTED", accent: "#34e0a1", pos: { top: "73%", left: "69%" } },
];

const FEED = [
  { t: "14:59", cat: "WORLD", text: "Connect a news/event API to populate world events." },
  { t: "14:57", cat: "MARKETS", text: "Connect market feeds for indices / crypto." },
  { t: "14:54", cat: "TECH", text: "Connect a research source for model & tooling news." },
  { t: "14:51", cat: "SCIENCE", text: "No live science feed connected yet." },
];

const STATS = [
  { label: "CPU USAGE", value: "—" },
  { label: "MEMORY", value: "—" },
  { label: "GPU", value: "—" },
  { label: "NETWORK", value: "—" },
  { label: "DATABASE", value: "—" },
  { label: "UPTIME", value: "—" },
];

function Spark() {
  const pts = useMemo(
    () =>
      Array.from({ length: 16 })
        .map((_, i) => `${i * 6},${14 - Math.round(Math.random() * 12)}`)
        .join(" "),
    []
  );
  return (
    <svg className="ihub-spark" viewBox="0 0 90 16" preserveAspectRatio="none">
      <polyline points={pts} fill="none" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

export default function IntelHub({ audioIntensity = 0, page, onNavigate }: Props) {
  const [clock, setClock] = useState("");
  useEffect(() => {
    const tick = () =>
      setClock(new Date().toLocaleTimeString([], { hour12: false }));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

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
                onClick={() => ["home", "workflows", "intelligence", "settings"].includes(n.key as string) && onNavigate(n.key as Page)}
              >
                <span className="ihub-nav-glyph">{n.glyph}</span>
                <span>{n.label}</span>
              </button>
            ))}
          </nav>

          <div className="ihub-side-foot">
            <div className="ihub-status-card">
              <div className="ihub-status-row">
                <span>SYSTEM STATUS</span>
                <Spark />
              </div>
              <div className="ihub-status-online">ONLINE</div>
              <div className="ihub-status-sub">ALL CORE SYSTEMS NOMINAL</div>
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
              <p>REAL-TIME WORLD INTELLIGENCE OVERVIEW</p>
            </div>
            <div className="ihub-top-right">
              <span className="ihub-sync"><i /> AI CORE SYNC</span>
              <span className="ihub-clock">{clock}<small>LOCAL TIME</small></span>
            </div>
          </header>

          <div className="ihub-stage">
            <div className="ihub-globe">
              <HolographicEarth3D audioIntensity={audioIntensity} />
            </div>

            {/* connector lines from each card to the globe */}
            <svg className="ihub-links" viewBox="0 0 100 100" preserveAspectRatio="none">
              {CARDS.map((c) => (
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

            {CARDS.map((c) => (
              <article
                key={c.id}
                className="ihub-hex"
                style={{ top: c.pos.top, left: c.pos.left, ["--accent" as string]: c.accent }}
              >
                <div className="ihub-hex-inner">
                  <span className="ihub-hex-glyph">{c.glyph}</span>
                  <h3>{c.title}</h3>
                  <div className="ihub-hex-metric">{c.metric}</div>
                  <div className="ihub-hex-state"><i /> {c.state}</div>
                </div>
              </article>
            ))}
          </div>

          <div className="ihub-command">
            <span className="ihub-command-wave">⌁</span>
            <div>
              <strong>SPEAK TO GARVIS</strong>
              <small>OR TYPE A COMMAND</small>
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
          </div>

          <div className="ihub-panel ihub-panel-grow">
            <div className="ihub-panel-head">INTELLIGENCE FEED <span className="ihub-demo">SAMPLE</span></div>
            <ul className="ihub-feed">
              {FEED.map((f, i) => (
                <li key={i}>
                  <span className="ihub-feed-time">{f.t}</span>
                  <span className="ihub-feed-cat">{f.cat}</span>
                  <p>{f.text}</p>
                </li>
              ))}
            </ul>
            <button className="ihub-link-btn">VIEW ALL FEEDS ›</button>
          </div>

          <div className="ihub-panel">
            <div className="ihub-panel-head">ACTIVE COMMANDS</div>
            <ul className="ihub-cmds">
              <li>Monitor global markets</li>
              <li>Track AI news</li>
              <li>Analyze social sentiment</li>
              <li>Watch security advisories</li>
            </ul>
            <button className="ihub-link-btn ihub-add">＋ ADD COMMAND</button>
          </div>
        </aside>
      </div>

      {/* ---------- Bottom stats bar ---------- */}
      <footer className="ihub-stats">
        {STATS.map((s) => (
          <div className="ihub-stat" key={s.label}>
            <div className="ihub-stat-label">{s.label}</div>
            <div className="ihub-stat-value">{s.value}</div>
            <Spark />
          </div>
        ))}
        <div className="ihub-stat ihub-stat-note">SAMPLE / PLACEHOLDER DATA — not wired to live sources</div>
      </footer>
    </div>
  );
}
