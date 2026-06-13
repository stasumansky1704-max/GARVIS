import "./living-core.css";
import Scene from "./scene/Scene";
import Hud from "./hud/Hud";

/**
 * JARVIS Living AI Core Chamber — the Home visual.
 * Live WebGL scene + diegetic HUD. Self-contained; scoped under
 * `.living-core-root` so its Tailwind/CSS never leaks into the dashboard.
 * The HUD command bar is wired to the real GARVIS backend.
 */
export default function LivingCore() {
  return (
    <div className="living-core-root relative h-full w-full overflow-hidden bg-[#030813]">
      {/* midnight-navy void */}
      <div
        className="absolute inset-0 z-0"
        style={{
          background:
            "radial-gradient(95% 80% at 50% 44%, #0e2a4e 0%, #0a1d39 32%, #061026 60%, #03070f 100%)",
        }}
      />
      <div className="absolute inset-0 z-0">
        <Scene />
      </div>
      <Hud />
    </div>
  );
}
