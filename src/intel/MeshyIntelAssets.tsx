import { lazy, Suspense, useState } from "react";
import {
  MESHY_ASSETS, MESHY_RAW_TOTAL_MB, MESHY_OPT_TOTAL_MB, mb, reductionPct, previewableAssets,
} from "./meshyAssetManifest";
import type { MeshyAsset } from "./meshyAssetManifest";

/**
 * GARVIS Intel Hub — Meshy asset integration (display-only, performance-safe).
 *
 * Shows the asset catalog honestly: each chip reports its web-safe OPTIMIZED size (green) or, if
 * not optimized, its raw size (slate "raw N MB"). The page NEVER auto-loads a GLB and NEVER
 * references raw heavy URLs. An optimized-ready chip is clickable (desktop only) to open an opt-in
 * holographic preview of the OPTIMIZED model; the 3D loader is a lazy chunk that degrades to a
 * wireframe orb on any failure. The code-based NetworkGlobe stays the hero/fallback.
 */

// Lazy so the 3D loader code is a separate chunk, off the critical path.
const ProjectorHologram = lazy(() => import("./ProjectorHologram"));

function AssetChip({ a, active, onToggle }: { a: MeshyAsset; active: boolean; onToggle: () => void }) {
  const ready = a.status === "optimized-ready";
  const detail = ready && a.optimizedSize !== undefined ? `opt ${mb(a.optimizedSize)} MB` : `raw ${mb(a.rawSize)} MB`;
  const dot = (
    <span
      className="pulse-dot inline-block h-2 w-2 shrink-0 rounded-full"
      style={{ background: a.color, color: a.color, boxShadow: `0 0 8px ${a.color}` }}
    />
  );
  const body = (
    <>
      {dot}
      <span className="hud-label whitespace-nowrap text-[8px] text-sky-200/70">{a.label}</span>
      <span className="hud-label whitespace-nowrap text-[7px]" style={{ color: ready ? "#34d399" : "#64748b" }}>
        · {detail}
      </span>
    </>
  );
  // Optimized assets are clickable preview toggles (desktop only); others are static.
  if (!ready) {
    return <div className="flex items-center gap-1.5" title={`${a.label} · ${a.reason}`}>{body}</div>;
  }
  return (
    <button
      onClick={onToggle}
      title={`${a.label} · ${a.reason}`}
      className={`pointer-events-auto hidden items-center gap-1.5 rounded-sm border px-1.5 py-0.5 transition-all lg:flex ${
        active ? "border-emerald-300/70 bg-emerald-400/10" : "border-transparent hover:border-sky-300/40 hover:bg-sky-400/[0.06]"
      }`}
    >
      {body}
    </button>
  );
}

/**
 * The Intel Hub asset strip. Desktop/tablet only (hidden on mobile so heavy 3D is never offered
 * on small screens). pointer-events-none except the optimized-asset preview toggles (lg only).
 */
export function MeshyAssetStrip() {
  const previewable = previewableAssets();
  const [activeId, setActiveId] = useState<string | null>(null);
  const active = previewable.find((a) => a.id === activeId) ?? null;

  return (
    <>
      <div className="pointer-events-none mx-auto mb-3 hidden max-w-5xl md:block">
        <div className="hud-panel bracket flex flex-wrap items-center justify-center gap-x-3 gap-y-1.5 px-4 py-2">
          <span className="hud-label hud-glow text-[9px] text-sky-100">Intel Hub · Assets</span>
          <span className="hidden h-3 w-px bg-sky-400/25 lg:block" />
          {MESHY_ASSETS.map((a) => (
            <AssetChip key={a.id} a={a} active={activeId === a.id} onToggle={() => setActiveId((id) => (id === a.id ? null : a.id))} />
          ))}
          <span className="hidden h-3 w-px bg-sky-400/25 lg:block" />
          <span className="hud-label text-[8px] text-sky-300/40">
            {MESHY_ASSETS.length} GLB · raw {MESHY_RAW_TOTAL_MB} MB → opt {MESHY_OPT_TOTAL_MB} MB · none auto-loaded
          </span>
          <span className="hud-label hidden text-[7px] text-sky-300/30 lg:inline">click an asset to preview</span>
        </div>
      </div>

      {/* opt-in, desktop-only holographic preview — optimized assets only, fully fallback-guarded */}
      {active && active.optimizedUrl && (
        <div className="pointer-events-none fixed bottom-28 right-6 z-30 hidden lg:block">
          <div className="hud-panel bracket relative h-[220px] w-[220px] overflow-hidden">
            <span className="hud-label hud-glow absolute left-2 top-1.5 z-10 text-[8px] text-sky-100">{active.label}</span>
            <span className="hud-label absolute bottom-1.5 left-2 z-10 text-[7px] text-emerald-300/50">
              Optimized · {mb(active.optimizedSize ?? 0)} MB
              {reductionPct(active) !== undefined ? ` · −${reductionPct(active)}%` : ""}
            </span>
            <Suspense fallback={<div className="sweep absolute inset-0 bg-gradient-to-r from-transparent via-sky-400/10 to-transparent" />}>
              <ProjectorHologram url={active.optimizedUrl} />
            </Suspense>
          </div>
        </div>
      )}
    </>
  );
}
