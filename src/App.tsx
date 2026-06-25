import Scene from "./scene/Scene";
import Hud from "./hud/Hud";

/**
 * JARVIS HOME — Living AI Core Chamber.
 * A live WebGL scene (the core, particles, rings, beam, reflective floor)
 * framed by a diegetic command-center HUD. Not a dashboard — an environment.
 */
export default function App() {
  return (
    <main className="relative h-screen w-screen overflow-hidden bg-[#030813]">
      {/* midnight-navy void: subtle blue glow around the core, near-black edges */}
      <div
        className="absolute inset-0 z-0"
        style={{
          background:
            "radial-gradient(95% 80% at 50% 44%, #0e2a4e 0%, #0a1d39 32%, #061026 60%, #03070f 100%)",
        }}
      />
      {/* live WebGL scene */}
      <div className="absolute inset-0 z-0">
        <Scene />
      </div>
      {/* diegetic HUD overlay */}
      <Hud />
    </main>
  );
}
