# J.A.R.V.I.S. HOME — Living AI Core Chamber

A cinematic, living sci-fi command center — **not** a dashboard. One screen: you "enter J.A.R.V.I.S."

Built with **React 19 + React Three Fiber (Three.js) + @react-three/postprocessing + Tailwind v4**.

## Run

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # production bundle
npm run preview  # serve the build
```

## What's on screen

A live WebGL scene framed by a diegetic HUD overlay:

**The command chamber (environment, built around the frozen core):**
- **Chamber** (`scene/Chamber.tsx`) — two ribbed metallic side walls angled inward toward a far vanishing point, with bright cyan emissive seams + a horizontal accent rail per wall, a back wall with a lit half-arch behind the core, base floor strip-lights, and a dark ceiling.
- **Energy platform** (`scene/EnergyPlatform.tsx`) — hex metallic pedestal beneath the core with concentric rings, a rotating accent ring, and an expanding energy pulse.
- **Distant screens** (`scene/DistantScreens.tsx`) — 6 holographic wall panels deep in the corridor, faintly flickering (ambient, not readable UI).
- **Atmosphere** (`scene/Atmosphere.tsx`) — ~1,400 drifting dust motes + two soft god-ray cones for volumetric depth.
- **Reflective floor** — `MeshReflectorMaterial`, raised and more mirror-like to catch the core, platform, and walls.

**The core (frozen — behavior unchanged this phase):**
- **Living AI Core** — distorting emissive heart, white-hot center, halo shell, camera-facing energy rings; breathes and pulses.
- **Orbit rings**, **~3,500 core particles**, **contained light beam**.

**Scene-wide:** denser exponential fog + darker premium clear color; cyan key light on the core plus four wall-rim lights hugging the corridor; Bloom + Vignette + film Noise; ACES tonemapping; slow drifting/parallax camera.

HUD (`src/hud/Hud.tsx`):
top status bar (wordmark · live clock · SYSTEM/COMPUTE/LINK), left presence panel ("J.A.R.V.I.S. is active / I'm listening"),
right telemetry, center "J.A.R.V.I.S. CORE / ONLINE" caption, command input with listening cue, quick-action bar
(Tell Me · Show Me · Open · Run · Analyze · Summarize · Create · Check), and footer (STAS / Execution Layer · Ready Node).

## Structure

```
src/
  App.tsx              # composition: chamber gradient + <Scene/> + <Hud/>
  index.css            # Tailwind v4 + HUD primitives (brackets, glow, scanlines, vignette)
  scene/
    Scene.tsx          # Canvas, lights, fog, camera rig, EffectComposer
    Chamber.tsx        # ribbed metallic walls, back arch, ceiling (the room)
    EnergyPlatform.tsx # hex pedestal + rings + pulse under the core
    DistantScreens.tsx # holographic wall panels deep in the corridor
    Atmosphere.tsx     # drifting dust motes + god-ray cones
    AICore.tsx         # the living holographic core (frozen)
    OrbitRings.tsx     # rotating orbit rings (frozen)
    CoreParticles.tsx  # drifting particle field (frozen)
    LightBeam.tsx      # contained volumetric beam (frozen)
    Floor.tsx          # reflective chamber floor
  hud/
    Hud.tsx            # full diegetic command-center overlay
```

## Design system

This project is governed by a Claude Code **skill stack** in `../.claude/skills/` that forces cinematic,
living, sci-fi execution and rejects generic dashboards:
`cinematic-art-director`, `reference-to-living-scene`, `threejs-webgl-director`, `motion-designer`,
`anti-dashboard-gatekeeper`, `command-center-layout`, `visual-testing`.

The master visual target is `../concept art/garvis core.png`. It is reference only — the scene is
recreated live in WebGL, never used as a background image.
