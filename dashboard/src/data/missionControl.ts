// Honest surface map for Mission Control.
// Factories and intelligence layers are USER-FACING business concepts. None are wired to a
// real backend capability yet, so every status here is Concept / Blueprint / Not Connected.
// Do NOT promote anything to Ready / Active / Connected until it is actually wired.

import type { Status } from "../components/StatusBadge";

export type Factory = {
  id: string;
  name: string;
  glyph: string;
  summary: string;
  status: Status; // honest maturity: Concept | Blueprint | Prototype (no Active until wired)
};

export type IntelLayer = {
  id: string;
  name: string;
  glyph: string;
  summary: string;
  connection: Status; // Connected | Not Connected
  maturity: Status; // Concept | Blueprint | Prototype
};

// Business factories — the visual body's "what GARVIS will produce" surface.
// Internal engine capabilities (research / loop / run-due / review / schedule) are
// intentionally NOT listed here; they are not user workflows.
export const FACTORIES: Factory[] = [
  { id: "youtube", name: "YouTube Factory", glyph: "▶", status: "Blueprint",
    summary: "Long-form video pipeline: idea → script → assets → publish." },
  { id: "faceless", name: "Faceless Channel Factory", glyph: "◐", status: "Concept",
    summary: "Automated faceless channels across niches and formats." },
  { id: "education", name: "Education Factory", glyph: "✎", status: "Blueprint",
    summary: "Courses, lessons and learning content generation." },
  { id: "novagame", name: "NovaGame Factory", glyph: "◆", status: "Concept",
    summary: "Game concepts, mechanics and content prototyping." },
  { id: "alphaflow", name: "AlphaFlow Factory", glyph: "▲", status: "Prototype",
    summary: "Trading intelligence + terminal (separate app, not yet brain-wired)." },
  { id: "marketing", name: "Marketing Factory", glyph: "✦", status: "Concept",
    summary: "Campaigns, copy and creative across channels." },
  { id: "leadgen", name: "Lead Generation Factory", glyph: "⊹", status: "Concept",
    summary: "Prospect sourcing, qualification and outreach." },
  { id: "products", name: "Digital Products Factory", glyph: "❖", status: "Concept",
    summary: "Templates, tools and downloadable product creation." },
  { id: "newsletter", name: "Newsletter Factory", glyph: "✉", status: "Blueprint",
    summary: "Research → curated issues → audience growth." },
  { id: "social", name: "Social Repurposing Factory", glyph: "↻", status: "Concept",
    summary: "Turn one source into many platform-native posts." },
];

// Intelligence layers around the globe. None are connected to a live feed yet.
export const INTEL_LAYERS: IntelLayer[] = [
  { id: "world", name: "World Events", glyph: "✦", connection: "Not Connected", maturity: "Blueprint",
    summary: "Global news & event awareness — needs a news/event API." },
  { id: "markets", name: "Markets", glyph: "$", connection: "Not Connected", maturity: "Blueprint",
    summary: "Indices, stocks & crypto — needs market data feeds." },
  { id: "sports", name: "Sports", glyph: "◎", connection: "Not Connected", maturity: "Concept",
    summary: "Major leagues & events — needs a sports data API." },
  { id: "revenue", name: "Revenue", glyph: "▮", connection: "Not Connected", maturity: "Blueprint",
    summary: "Earnings across ventures — needs Stripe/PayPal/custom." },
  { id: "social", name: "Social", glyph: "◍", connection: "Not Connected", maturity: "Concept",
    summary: "Reach & engagement signals — needs platform APIs." },
  { id: "tech", name: "Tech / AI", glyph: "⌬", connection: "Not Connected", maturity: "Blueprint",
    summary: "Model & tooling intelligence — needs research/source feeds." },
];

// Honest rollup for headers (no inflation).
export function factoriesSummary(): string {
  const ready = FACTORIES.filter((f) => f.status === "Ready" || f.status === "Active").length;
  return `${FACTORIES.length} factories mapped · ${ready} wired · rest in concept/blueprint`;
}

export function intelSummary(): string {
  const connected = INTEL_LAYERS.filter((l) => l.connection === "Connected").length;
  return `${INTEL_LAYERS.length} layers · ${connected} live feeds connected`;
}
