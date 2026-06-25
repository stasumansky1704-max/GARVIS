# GARVIS — Claude Code Operating Charter (`garvis-living-ui`)

This file governs how Claude Code works inside **`GARVIS CORE/garvis-living-ui`**.
It is binding. When a request conflicts with these rules, the rules win — surface the
conflict and ask, do not silently override.

---

## GARVIS mission

GARVIS is a **living AI command center**, not a dashboard. The product is a single
cinematic screen: the operator "enters GARVIS" and stands inside an AI Core Chamber —
a holographic, breathing, sci-fi command bridge (Iron Man lab / JARVIS / Star Citizen
bridge feel). The mission of this repo is to build and refine that **living WebGL scene**
and its diegetic HUD to a AAA real-time-cinematic bar.

Hard product line: **never** drift toward a generic SaaS dashboard, admin panel, analytics
cards, or flat business UI. If the work starts feeling generic, stop and redesign.

---

## Current repo state (Phase 0 — as of this charter)

- **Stack:** Vite + React 19 + TypeScript, React Three Fiber (Three.js) + drei +
  `@react-three/postprocessing`, Tailwind v4. Package name `jarvis-living-ui`.
- **Scripts:** `dev` (vite), `build` (vite build), `lint` (eslint .), `preview`.
- **Source layout:** `src/App.tsx` composes `scene/Scene.tsx` (Canvas, lights, fog,
  camera rig, EffectComposer) + `hud/Hud.tsx`. Scene parts: `Chamber`, `EnergyPlatform`,
  `DistantScreens`, `Atmosphere`, `AICore`, `OrbitRings`, `CoreParticles`, `LightBeam`,
  `Floor`. The **AI Core is FROZEN** (behavior locked this phase) — do not change its
  motion/shaders without explicit approval.
- **Reference target:** `../concept art/garvis core.png` — reference ONLY; the scene is
  recreated live in WebGL, never used as a background image.
- **Design skill stack:** `../.claude/skills/` (`cinematic-art-director`,
  `reference-to-living-scene`, `threejs-webgl-director`, `motion-designer`,
  `anti-dashboard-gatekeeper`, `command-center-layout`, `visual-testing`).
- **Version control:** initialized in Phase 0. No remote configured. Nothing is committed
  by automation.
- **Out of scope (do NOT touch):** sibling folders under `GARVIS CORE/`
  (`00_governance` … `10_docs`, `concept art`), `garvis_voice`,
  `WORKFLOWS/08_GARVIS_COMMAND_SYSTEM`, and any `API KEYS` / `PASSWORDS` folders anywhere.
  Work stays inside `garvis-living-ui/`.

---

## Strict approval gates

Get explicit user approval **before**:

- Modifying source code (anything under `src/`, configs, `package.json`, lockfiles).
- Changing the FROZEN AI Core (`AICore`, `OrbitRings`, `CoreParticles`, `LightBeam`).
- Installing, removing, or upgrading any dependency.
- Installing or enabling any MCP server.
- Running CodeGraph init / indexing.
- `git commit`, `git push`, creating tags/branches on a remote, or any deployment.
- Deleting or overwriting any file you did not create in the current task.
- Touching anything outside `garvis-living-ui/`.

Default posture is **propose → wait for "yes" → act**. Foundation/scaffolding explicitly
requested (docs, ignore files, this charter) may proceed; code and infra changes may not.

---

## CodeGraph — on-demand policy

CodeGraph is **opt-in repository intelligence**. There is no `.codegraph/` index yet, and
**Phase 0 does not create one.** Do not run CodeGraph init or auto-inject repository
context.

When (and only when) an index exists and the task genuinely needs structural
intelligence — symbol lookup, call-graph / reference / impact analysis, cross-file
relationships, blast-radius before an edit — prefer `codegraph_explore` over a grep/read
loop, and keep queries to the **smallest scope** (single symbol → file → subsystem). Do
**not** use CodeGraph for UI/UX/motion/visual critique, docs, planning, or simple edits.
Stop querying once the question is answered. Never index the repo without approval.

---

## No autonomous destructive actions

Never, without an explicit instruction naming the action:

- Delete files/folders, empty trash, `git clean`, `git reset --hard`, force-checkout.
- Mass rename/move, rewrite history, or bulk-edit across the tree.
- Overwrite files you didn't author this session.

Reversible, additive, narrowly-scoped changes are preferred. If a step is hard to undo,
stop and confirm first.

---

## No secrets handling

- Never read, write, print, paste, move, or commit credentials — API keys, tokens,
  passwords, `.env` files, private keys. `.env*` and key files are git-ignored; keep it
  that way.
- Never enter secrets into forms, fields, or external services.
- If a task needs a secret, instruct the user to provide/configure it themselves; do not
  handle the value.
- Do not touch any `API KEYS` / `PASSWORDS` folders.

---

## No deployment / push without explicit approval

- No `git push`, no remote creation, no Vercel/Netlify/CI deploy, no publishing of any
  build artifact unless the user explicitly approves that specific action in chat.
- `git init` and local working-tree changes are fine for Phase 0; **commits are not made
  by automation** — leave the tree for the user to review unless asked to commit.

---

## Validation conventions

- Install deps only if `node_modules` is missing (`npm install`).
- Verify with `npm run build` and `npm run lint` when available.
- Only fix build/lint failures that **your own changes** introduced. Pre-existing failures
  are reported, not "fixed," unless the user asks.
