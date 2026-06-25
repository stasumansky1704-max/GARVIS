# GARVIS — Claude Code Platform & Migration Plan

**Date:** 2026-06-25 · **Author role:** Principal GARVIS Platform Architect · **Mode:** read-only architecture + migration plan.
**Nothing was installed, modified, added, or deleted.** AlphaFlow was the *pilot*; GARVIS is the *target*. This plan deliberately does **not** copy AlphaFlow's setup — GARVIS has different needs.

> **Doc location note:** authored here in the AlphaFlow repo (where the audit series lives) because GARVIS is **not yet a git repo** and sits outside the sanctioned working dirs. **Step 1 of the plan is to git-init GARVIS**, after which this file should be copied to `GARVIS CORE/garvis-living-ui/docs/`.

---

## 1. GARVIS current state

GARVIS is **not one app** — it's a 3-part polyrepo, each at a different maturity:

| Component | Path | Stack | Maturity |
|---|---|---|---|
| **Living UI** (command-center face) | `GARVIS CORE/garvis-living-ui` | **Vite 8 + React 19 + Three.js** (`@react-three/fiber` 9, `drei`, `postprocessing`), Tailwind v4, **Playwright** dep | Runs (`node_modules` present); **no git, no tests, no `.claude`, no CLAUDE.md, no index**; root cluttered with ~40 dev PNGs |
| **Voice stack** | `garvis_voice` | **Python** — Vosk / RealtimeSTT (STT), Piper / ElevenLabs (TTS), mic diagnostics, latency probe, multilingual-TTS plan | POC scripts; **no git, no `requirements.txt`/venv manifest**; logs scattered |
| **Command system** | `WORKFLOWS/08_GARVIS_COMMAND_SYSTEM` | **Markdown spec** — `PROJECT_REGISTRY`, `AGENT_ROLES`, `AUTOMATION_RULES`, `NIGHT_OPERATIONS`, `APPROVAL_QUEUE`, `SYSTEM_PROMPTS`, `DAILY_BRIEFINGS`, `DEPLOYMENT_CONTROL`, `CANDIDATE_SYSTEMS` | Operating-model spec; not code yet |

**Environment facts:**
- **No version control anywhere** in GARVIS (the single biggest blocker).
- **No Claude config** at all — a clean slate (no inherited debt; AlphaFlow's lessons apply cleanly).
- **Global MCP already available to GARVIS sessions:** `codegraph`, Vercel, Canva, Google Drive (connected). GARVIS just isn't indexed yet, so the global `~/.claude/CLAUDE.md` codegraph note self-guards to a no-op there.
- **Polyglot + multi-process** (JS/TS UI + Python voice + markdown ops) → favors process-control, filesystem-spanning, and browser tooling over a single-app setup.

### Audit checklist (requested 1–12)
1. **Repo structure** — 3 components, polyrepo, above. 2. **Claude config** — none. 3. **Agents** — none local (227 global agency-agents available). 4. **Skills** — none local. 5. **MCP** — none GARVIS-specific; global codegraph/Vercel/Canva/Drive reachable. 6. **Memory** — none formal; the command-system's `PROJECT_REGISTRY`/`REPORTS`/`DAILY_BRIEFINGS` are a *latent* state layer. 7. **Workflows** — specced in `08_GARVIS_COMMAND_SYSTEM` (approval-queue, night-ops), not yet executable. 8. **Voice modules** — Python POCs in `garvis_voice` (Vosk/RealtimeSTT + Piper/ElevenLabs). 9. **Frontend/backend/testing** — Vite/R3F front end; **no backend**; **no test runner** (Playwright present as a dep but unused). 10. **Automation scripts** — Python voice/mic probes; no orchestration code. 11. **Documentation** — `README.md` per area + the command-system spec; no architecture docs. 12. **Gaps** — see below.

### Current gaps (ranked)
1. **No git** — prerequisite for everything (rollback, gated workflow, codegraph hook self-guard, GitHub MCP).
2. **No test harness** — Playwright is a dep but there's no suite; the UI is verified by eyeballing PNGs.
3. **No Claude foundation** — no CLAUDE.md/AGENTS.md/memory/permissions; no usage policies.
4. **No code intelligence** — not indexed; cross-component understanding is manual.
5. **No execution/automation layer** — the command-system is a spec, not a runner.
6. **No secrets discipline** — voice POCs reference ElevenLabs/OpenAI; no `.env` policy observed (and a `Desktop/API KEYS and PASSWORDS/` folder exists — **left untouched**, but flags a secrets-hygiene need).

---

## 2. What AlphaFlow taught us (carry-over lessons)

| Lesson from the pilot | How it changes the GARVIS plan |
|---|---|
| **Disable always-on hooks; go on-demand** (CodeGraph hook injected ~4.3k tokens/prompt) | Install CodeGraph for GARVIS **with the prompt-hook off from day one**; reuse the on-demand Usage Policy. |
| **Permissions are the real attack surface** (auto-approved `git credential *` + `curl POST` were the worst findings) | GARVIS's `settings.local.json` must start **least-privilege**: no `git credential *`, no auto-approved authenticated `curl`, no bare `npx *`. Especially critical because GARVIS aims at *computer control*. |
| **`npm audit` matters; never `--force`** (would've downgraded Next 16→9) | Add an `npm audit` gate to the GARVIS UI from the start; pin a "never `--force`" rule. |
| **One memory authority; reject claude-mem** | Build GARVIS memory with the proven curated-file pattern; fold in the command-system's registry/reports. |
| **Subtract, don't add; reject duplicates** | GARVIS needs *more* tools than AlphaFlow — but each must add **execution value**, not clutter. |
| **Identity-locked design; reject taste-skill** | GARVIS already has its cinematic Jarvis identity + a 7-skill UI stack → no generic design skills. |
| **Motion was installed but unused in AlphaFlow** | GARVIS's UI is **r3f/Three (3D)**, not DOM-animation-heavy → Motion is even *lower* value here. |

---

## 3. Tooling map for GARVIS

| Tool | Decision | Why (GARVIS-specific) | Method | Conflict risk |
|---|---|---|---|---|
| **CodeGraph** | **Install (after git)** | Mission = "understand its own codebase"; polyrepo self-understanding. Index the JS/TS UI (codegraph parses ts/tsx/js/yaml; **Python support unverified** → UI first). | `npm i -g` (done globally) → `codegraph init` in the UI repo; **hook off** | Low |
| **Playwright MCP** | **Install (high value)** | Mission = "UI command center / browser-UI control / run tests"; the UI **already depends on Playwright**. Direct browser drive + the missing test layer. | `claude mcp add playwright -- npx @playwright/mcp@latest` | Low |
| **GitHub MCP** | **Install later (after repos on GitHub; manual PAT)** | Mission = "GitHub helper". Structured repo/PR/issue ops beyond shell `gh`. | `claude mcp add github …`; **fine-grained PAT, manual approval** | Cred-handling (gate it) |
| **Context7 MCP** | **Install later** | GARVIS rides bleeding edge (Vite 8, React 19, Three 0.184, r3f 9); current-docs injection reduces guesswork. Read-only, low risk. | `claude mcp add context7 …` | None |
| **anthropics/skills** | **Pilot (selective)** | `document-skills` (pdf/docx/xlsx) feeds GARVIS's `REPORTS`/`DAILY_BRIEFINGS`/night-ops outputs. | `/plugin` (interactive terminal) | Low |
| **Ruflo** | **Pilot only (isolated)** | This is where GARVIS ≠ AlphaFlow: Ruflo's orchestration/agent-roles/memory map onto `08_GARVIS_COMMAND_SYSTEM` (agent-roles, automation-rules, night-ops, approval-queue). **But** heavy + overlaps the 227 agents + built-in Task system. Evaluate vs building GARVIS's own runner on the existing spec. | Pilot env: `claude mcp add ruflo -- npx ruflo@latest mcp start` | **High** (orchestration overlap) |
| **Computer-control** (computer-use / Chrome) | **Pilot only (heavily gated)** | The **endgame** ("real computer-use capability"). Harness already exposes `computer-use` + `Claude_in_Chrome`. Needs the `APPROVAL_QUEUE` as a hard gate first. | Harness-provided; design guardrails, don't "install" | **High** (machine control) |
| **Filesystem MCP** | **Skip for now (lean)** | Built-in Read/Edit/Glob/Grep + additional working dirs already span the polyrepo. Adds little until cross-root automation is real. | — | Overlap w/ built-ins |
| **Motion** | **Skip/later** | UI is r3f/Three (animates via `useFrame`), not DOM. Only if HUD **DOM** overlays need spring physics. | `npm i motion` (UI repo) | None |
| **Sequential Thinking MCP** | **Skip** | The model + `Plan` agent already reason structurally; a scratchpad tool adds clutter, not execution value. | — | — |
| **Superpowers** | **Skip (pilot at most)** | Imposes a dev methodology; GARVIS's operating model is its **own** command-system spec — let that lead, don't overwrite it. | — | Workflow-doctrine clash |
| **wshobson/agents** | **Skip** | 227 `agency-agents` already global; near-total overlap (same verdict as AlphaFlow). | — | Duplicate |
| **taste-skill** | **Skip** | GARVIS has a locked cinematic Jarvis identity + 7-skill UI stack. | — | Identity clash |
| **Additional memory tools (claude-mem etc.)** | **Skip** | Build the curated-file memory pattern; reject competing memory layers. | — | Memory-authority clash |

---

## 4. Install order (foundation → intelligence → execution → automation)

```
PHASE 0 — FOUNDATION (prerequisite; nothing else is safe without it)
  0.1 git init the three GARVIS areas (UI, voice, command-system) + .gitignore the PNG/log clutter
  0.2 Claude foundation in the UI repo:
        CLAUDE.md (+ @AGENTS.md), AGENTS.md (Vite/R3F/Three notes),
        a GARVIS memory dir + MEMORY.md (curated pattern),
        CodeGraph Usage Policy (on-demand, copied from the pilot),
        settings.local.json — LEAST-PRIVILEGE (no `git credential *`, no auto `curl POST`, no bare `npx *`)
  0.3 npm audit gate on the UI; "never --force" rule

PHASE 1 — INTELLIGENCE
  1.1 CodeGraph init on garvis-living-ui (hook OFF, on-demand)
  1.2 Context7 MCP (current-docs for the bleeding-edge stack)

PHASE 2 — EXECUTION
  2.1 Playwright MCP (browser/UI control + the missing test layer)
  2.2 First Playwright smoke suite for the Living UI (replaces PNG eyeballing)
  2.3 GitHub MCP (after repos pushed; fine-grained PAT, MANUAL approval)

PHASE 3 — AUTOMATION (pilot, gated)
  3.1 Decide orchestration: build on 08_GARVIS_COMMAND_SYSTEM vs pilot Ruflo (isolated)
  3.2 document-skills for REPORTS/DAILY_BRIEFINGS
  3.3 Wire the APPROVAL_QUEUE as the hard gate for any side-effecting action

PHASE 4 — COMPUTER-CONTROL (long-horizon, heavily gated)
  4.1 Voice→intent→APPROVAL_QUEUE→action loop, read-only first
  4.2 computer-use / Chrome control behind explicit per-session approval
```

---

## 5. Risk table

| Item | Risk | Severity | Mitigation |
|---|---|---|---|
| No git before changes | No rollback; unsafe edits | **High** | Phase 0.1 first — block all else on it |
| Computer-control tools | Machine takeover / irreversible actions | **High** | Approval-queue gate; read-only first; per-session approval |
| GitHub MCP PAT | Credential exposure (AlphaFlow's worst finding) | **High** | Fine-grained least-privilege PAT; manual approval; never auto-allow `git credential`/`curl POST` |
| Ruflo orchestration | Heavy; competes with built-ins + 227 agents | **Med** | Pilot isolated; compare to native command-system build |
| Secrets in voice POCs / `API KEYS and PASSWORDS/` | Leakage | **Med** | `.env` + gitignore policy in Phase 0; never commit keys; rotate shared ones |
| CodeGraph on Python voice | Index may not cover Python | **Low** | Index the JS/TS UI; treat voice separately |
| Tool sprawl | Clutter without execution value | **Med** | This map rejects 6 tools outright |

---

## 6. Conflict table

| A | B | Conflict | Resolution |
|---|---|---|---|
| Ruflo orchestration | Built-in `Task`/`Agent` + 227 agency-agents | Three overlapping orchestration layers | Pilot Ruflo only; pick **one** runner |
| Superpowers methodology | `08_GARVIS_COMMAND_SYSTEM` operating model | Two competing workflows | Let GARVIS's own spec lead; skip Superpowers |
| claude-mem | Curated GARVIS memory + command-system registry | Two memory authorities | Single curated memory; reject claude-mem |
| taste-skill | GARVIS cinematic identity + 7-skill UI stack | Competing design doctrine | Skip taste-skill |
| Filesystem MCP | Built-in Read/Edit/Glob/Grep | Redundant file access | Skip until cross-root need is real |
| Global codegraph hook (if ever re-enabled) | GARVIS token budget | Auto-inject tax | Keep hook OFF (pilot lesson) |

---

## 7. Needed MCP servers (GARVIS)
- **Now/early:** `codegraph` (already global — just `init` the UI), **Playwright MCP** (control + tests).
- **Later (gated):** **GitHub MCP** (manual PAT), **Context7 MCP** (docs).
- **Pilot only:** **Ruflo MCP** (orchestration), **computer-use / Chrome** (harness-provided).
- **Skip:** Filesystem, Sequential-Thinking.
- **Keep (already connected):** Vercel (deploy — matches "Vercel helper"), Canva/Drive (incidental).
- **Gap vs mission:** no **Docker MCP** found for the "Docker helper" goal → evaluate a Docker MCP in Phase 2/3 (deferred; needs its own audit).

## 8. Needed skills (GARVIS)
- **Build first (own):** a GARVIS CodeGraph Usage Policy, a `run-garvis` launch/screenshot skill (Vite dev + Playwright), a voice-stack run skill.
- **Adopt selectively (later):** `document-skills` (reports/briefings), `consolidate-memory` (memory hygiene), `skill-creator` (author GARVIS skills).
- **Skip:** taste-skill, generic design skills, lingoverse/* (other projects).

## 9. Needed agents (GARVIS)
- **Reuse, don't reinstall:** the 227 global `agency-agents` are already available (engineering-*, testing-*, devops, security). No new agent install.
- **Define GARVIS-specific roles** from `02_AGENT_ROLES` as **project subagents** (e.g. `garvis-voice`, `garvis-ops`, `garvis-deploy`) once git exists — small, scoped, not a bulk import.

## 10. Needed automation layer
- **Source of truth:** `08_GARVIS_COMMAND_SYSTEM` (registry, automation-rules, night-ops, approval-queue) — make it executable rather than importing a foreign harness.
- **Hard gate:** every side-effecting action (deploy, push, computer-control) routes through `06_APPROVAL_QUEUE` — the same "stop at the merge gate" discipline the pilot proved.
- **Runner decision (Phase 3):** native build vs Ruflo pilot — decide with evidence, not by default.

---

## 11. Recommended FIRST installation
**Before any tool: `git init` the GARVIS repos + lay the Claude foundation (CLAUDE.md / AGENTS.md / memory / least-privilege permissions / on-demand CodeGraph policy).** Then the **first actual tool is CodeGraph `init` on `garvis-living-ui`** (self-understanding), immediately followed by **Playwright MCP** (the execution + test capability GARVIS lacks entirely). These three moves convert GARVIS from "unversioned scripts" into a safe, self-aware, testable platform — the minimum base for everything else.

## 12. Roadmap toward GARVIS computer-control capability
1. **Foundation** — git + Claude config + least-privilege permissions.
2. **Self-awareness** — CodeGraph (on-demand) + Context7.
3. **Hands** — Playwright MCP (browser/UI) + a real test suite.
4. **Repo/deploy reach** — GitHub MCP (gated PAT) + the existing Vercel MCP.
5. **Orchestration** — make `08_GARVIS_COMMAND_SYSTEM` executable; pilot Ruflo only to compare.
6. **Voice loop** — wire `garvis_voice` → intent → **APPROVAL_QUEUE** → action (read-only first).
7. **Computer-use** — enable `computer-use`/Chrome control **only** behind the approval queue, per-session approval, reversible-first.

---

## Final answer

- **Install FIRST in GARVIS:** **git init + Claude foundation (CLAUDE.md/AGENTS.md/memory/least-privilege permissions/on-demand CodeGraph policy)**, then **CodeGraph `init` on the UI**, then **Playwright MCP**.
- **Do NOT install yet:** GitHub MCP (until repos are on GitHub + a fine-grained PAT exists), Ruflo (pilot-only/isolated), computer-control tools (gated behind the approval queue), Context7/document-skills (Phase 1–3), Docker MCP (needs its own audit).
- **Requires MANUAL approval:** GitHub MCP PAT, any computer-use/Chrome control, any deploy/push action (route through `APPROVAL_QUEUE`).
- **Postpone / reconsider:** Motion (UI is 3D, low value), Filesystem MCP (overlaps built-ins), Superpowers (workflow clash).
- **Reject outright:** wshobson/agents (duplicate), taste-skill (identity clash), claude-mem (memory clash), Sequential-Thinking MCP (no execution value).

> **Principle:** GARVIS earns *more* tooling than AlphaFlow because its mission is execution — but only **foundation-first, approval-gated, execution-valuable** tools. Build GARVIS's own operating model; borrow capability, not clutter.

*Read-only plan. No installs, no file modifications, no dependencies, no deletions. Stopped after the plan, as instructed.*
