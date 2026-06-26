// GARVIS Intel Hub — Meshy asset manifest (catalog metadata only; display-only).
//
// The 9 raw Meshy GLBs (/public/assets/intel-hub/meshy/, ~559 MB total) are valid glTF 2.0 but
// far too heavy for the web, so the UI NEVER references the raw URLs and NEVER auto-loads a GLB.
// Optimized, web-safe copies live under /assets/intel-hub/meshy-optimized/ and are produced with
// gltf-transform (simplify + KHR_mesh_quantization + webp/1k textures — no Draco/meshopt, so they
// load with vanilla three.js, no external decoder, no network). Only `optimized-ready` assets are
// ever offered for an opt-in, desktop-only preview. The code-based NetworkGlobe remains the hero.

const RAW = "/assets/intel-hub/meshy";
const OPT = "/assets/intel-hub/meshy-optimized";

export type MeshyKind = "earth" | "node" | "floor" | "projector";

// optimized-ready : optimized copy exists, validated, light enough for opt-in preview.
// catalog-only    : shown in the catalog; no web-safe model offered (still being / not optimized).
// too-heavy       : even optimized it is too large for web preview.
// failed          : optimization failed.
export type MeshyStatus = "optimized-ready" | "catalog-only" | "too-heavy" | "failed";

// never-auto-load        : never fetched automatically (catalog metadata only).
// opt-in-preview-only    : may be fetched ONLY on explicit user action.
// ready-for-light-preview: optimized + small enough to offer as an opt-in light preview.
export type LoadPolicy = "never-auto-load" | "opt-in-preview-only" | "ready-for-light-preview";

export interface MeshyAsset {
  readonly id: string;
  readonly label: string;
  readonly kind: MeshyKind;
  readonly color: string;
  readonly rawSize: number;            // bytes (local input, never committed/served)
  readonly optimizedSize?: number;     // bytes (web-safe output)
  readonly optimizedUrl?: string;      // served URL — ONLY set for optimized assets
  readonly thumbnailUrl?: string;      // poster image, if generated
  readonly status: MeshyStatus;
  readonly loadPolicy: LoadPolicy;
  readonly reason: string;
}

// All 9 optimized via gltf-transform (simplify err=0.003 + KHR_mesh_quantization + webp/1k
// textures, no Draco/meshopt). Raw 586 MB → ~10.9 MB total. Optimized sizes are measured bytes.
export const MESHY_ASSETS: readonly MeshyAsset[] = [
  {
    id: "projector", label: "Projector", kind: "projector", color: "#7dd3fc",
    rawSize: 12_914_952, optimizedSize: 646_060, optimizedUrl: `${OPT}/projector.glb`,
    status: "optimized-ready", loadPolicy: "ready-for-light-preview",
    reason: "12.9 MB → 0.6 MB (−95%); web-safe opt-in preview",
  },
  {
    id: "earth", label: "Earth · Intel Hub", kind: "earth", color: "#22d3ee",
    rawSize: 47_726_116, optimizedSize: 450_820, optimizedUrl: `${OPT}/earth_intelhub.glb`,
    status: "optimized-ready", loadPolicy: "ready-for-light-preview",
    reason: "47.7 MB → 0.5 MB (−99%); web-safe opt-in preview",
  },
  {
    id: "market", label: "Market node", kind: "node", color: "#34d399",
    rawSize: 69_755_836, optimizedSize: 1_549_276, optimizedUrl: `${OPT}/node_market_green.glb`,
    status: "optimized-ready", loadPolicy: "ready-for-light-preview",
    reason: "69.8 MB → 1.5 MB (−98%); web-safe opt-in preview",
  },
  {
    id: "ops", label: "Ops node", kind: "node", color: "#fb923c",
    rawSize: 72_016_624, optimizedSize: 942_572, optimizedUrl: `${OPT}/node_ops_orange.glb`,
    status: "optimized-ready", loadPolicy: "ready-for-light-preview",
    reason: "72.0 MB → 0.9 MB (−99%); web-safe opt-in preview",
  },
  {
    id: "revenue", label: "Revenue node", kind: "node", color: "#f87171",
    rawSize: 72_270_364, optimizedSize: 1_630_572, optimizedUrl: `${OPT}/node_revenue_red.glb`,
    status: "optimized-ready", loadPolicy: "ready-for-light-preview",
    reason: "72.3 MB → 1.6 MB (−98%); web-safe opt-in preview",
  },
  {
    id: "social", label: "Social node", kind: "node", color: "#38bdf8",
    rawSize: 71_390_328, optimizedSize: 1_623_596, optimizedUrl: `${OPT}/node_social_blue.glb`,
    status: "optimized-ready", loadPolicy: "ready-for-light-preview",
    reason: "71.4 MB → 1.6 MB (−98%); web-safe opt-in preview",
  },
  {
    id: "tech", label: "Tech node", kind: "node", color: "#fbbf24",
    rawSize: 73_264_996, optimizedSize: 1_730_508, optimizedUrl: `${OPT}/node_tech_yellow.glb`,
    status: "optimized-ready", loadPolicy: "ready-for-light-preview",
    reason: "73.3 MB → 1.7 MB (−98%); web-safe opt-in preview",
  },
  {
    id: "world", label: "World node", kind: "node", color: "#e2e8f0",
    rawSize: 75_577_296, optimizedSize: 1_079_548, optimizedUrl: `${OPT}/node_world_white.glb`,
    status: "optimized-ready", loadPolicy: "ready-for-light-preview",
    reason: "75.6 MB → 1.1 MB (−99%); web-safe opt-in preview",
  },
  {
    id: "floor", label: "Floor · Master", kind: "floor", color: "#64748b",
    rawSize: 90_893_896, optimizedSize: 1_233_840, optimizedUrl: `${OPT}/garvis_floor_master.glb`,
    status: "optimized-ready", loadPolicy: "ready-for-light-preview",
    reason: "90.9 MB → 1.2 MB (−99%); web-safe opt-in preview",
  },
];

export const RAW_BASE = RAW;

export function mb(bytes: number): number {
  return Math.round((bytes / 1_000_000) * 10) / 10;
}
export function reductionPct(a: MeshyAsset): number | undefined {
  if (a.optimizedSize === undefined) return undefined;
  return Math.round((1 - a.optimizedSize / a.rawSize) * 100);
}
export function meshyAsset(id: string): MeshyAsset | undefined {
  return MESHY_ASSETS.find((a) => a.id === id);
}
/** Assets safe to offer for an opt-in preview (optimized + validated). */
export function previewableAssets(): readonly MeshyAsset[] {
  return MESHY_ASSETS.filter((a) => a.status === "optimized-ready" && !!a.optimizedUrl);
}

export const MESHY_RAW_TOTAL_MB = Math.round(MESHY_ASSETS.reduce((s, a) => s + a.rawSize, 0) / 1_000_000);
export const MESHY_OPT_TOTAL_MB =
  Math.round((MESHY_ASSETS.reduce((s, a) => s + (a.optimizedSize ?? 0), 0) / 1_000_000) * 10) / 10;
