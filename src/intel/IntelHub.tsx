import { useEffect, useState } from "react";
import {
  RUNTIME_MODULES, WORKFLOWS, SKILLS, SKILLS_SUMMARY, APPROVAL_QUEUE, AUDIT_STREAM,
  INTEL_SIGNALS, PROJECTS, HEALTH_COLOR,
} from "./intelData";
import type { Health } from "./intelData";

/**
 * GARVIS Intel Hub — a DIEGETIC HUD layer of holographic readouts that FRAME the living core.
 * Display-only: it renders static status snapshots and never executes anything. Two minimal,
 * translucent, bracketed rails (left + right) sit around the core, hidden on small screens so the
 * core + command bar remain the focus. Built from the existing hud-* primitives.
 */

/* ---------- shared primitives ---------- */

function Dot({ health }: { health: Health }) {
  const c = HEALTH_COLOR[health];
  return (
    <span
      className="pulse-dot inline-block h-1.5 w-1.5 shrink-0 rounded-full"
      style={{ background: c, color: c }}
    />
  );
}

function Panel({ title, code, children }: { title: string; code: string; children: React.ReactNode }) {
  return (
    <div className="hud-panel bracket w-[236px] px-3 py-2.5">
      <div className="flex items-center justify-between">
        <span className="hud-label hud-glow text-[10px] text-sky-100">{title}</span>
        <span className="hud-label text-[7px] text-sky-300/40">{code}</span>
      </div>
      <div className="hud-line mt-1.5 h-px w-full opacity-50" />
      <div className="mt-2 space-y-[7px]">{children}</div>
    </div>
  );
}

function Row({ label, value, health }: { label: string; value: string; health: Health }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="hud-label truncate text-[8px] text-sky-300/45">{label}</span>
      <span className="flex shrink-0 items-center gap-1.5">
        <Dot health={health} />
        <span className="hud-label text-[9px]" style={{ color: HEALTH_COLOR[health] }}>{value}</span>
      </span>
    </div>
  );
}

/** Tiny state chip (Ready / Locked / Waiting). */
function Chip({ text, health }: { text: string; health: Health }) {
  const c = HEALTH_COLOR[health];
  return (
    <span
      className="hud-label rounded-sm px-1.5 py-[1px] text-[7px]"
      style={{ color: c, border: `1px solid ${c}44`, background: `${c}10` }}
    >
      {text}
    </span>
  );
}

/* ---------- panels ---------- */

function RuntimePanel() {
  return (
    <Panel title="Runtime" code="SYS·01">
      {RUNTIME_MODULES.map((m) => (
        <Row key={m.label} label={m.label} value={m.value} health={m.health} />
      ))}
    </Panel>
  );
}

function WorkflowsPanel() {
  return (
    <Panel title="Workflows" code="WF·02">
      {WORKFLOWS.map((w) => (
        <div key={w.name} className="flex items-center justify-between gap-2">
          <div className="min-w-0 leading-tight">
            <div className="hud-label truncate text-[8px] text-sky-100/80">{w.name}</div>
            <div className="hud-label text-[7px] text-sky-300/40">{w.policy}</div>
          </div>
          <Chip text={w.state} health={w.health} />
        </div>
      ))}
    </Panel>
  );
}

function SkillsPanel() {
  return (
    <Panel title="Skills" code="SK·03">
      <div className="flex items-center justify-between">
        <span className="hud-label text-[8px] text-sky-300/45">Installed {SKILLS_SUMMARY.installed}</span>
        <span className="flex items-center gap-2">
          <span className="hud-label text-[8px]" style={{ color: HEALTH_COLOR.ok }}>Ready {SKILLS_SUMMARY.ready}</span>
          <span className="hud-label text-[8px]" style={{ color: HEALTH_COLOR.locked }}>Locked {SKILLS_SUMMARY.locked}</span>
        </span>
      </div>
      <div className="hud-line h-px w-full opacity-30" />
      {SKILLS.map((s) => (
        <div key={s.name} className="flex items-center justify-between gap-2">
          <span className="hud-label truncate text-[8px] text-sky-100/75">{s.name}</span>
          <Chip text={s.state} health={s.state === "Ready" ? "ok" : "locked"} />
        </div>
      ))}
    </Panel>
  );
}

function ApprovalsPanel() {
  return (
    <Panel title="Approvals" code="AP·04">
      <Row label="Waiting" value={`${APPROVAL_QUEUE.length}`} health={APPROVAL_QUEUE.length ? "waiting" : "ok"} />
      <div className="hud-line h-px w-full opacity-30" />
      {APPROVAL_QUEUE.map((a) => (
        <div key={a.workflow} className="leading-tight">
          <div className="hud-label truncate text-[8px] text-sky-100/80">{a.workflow}</div>
          <div className="flex items-center justify-between">
            <span className="hud-label text-[7px] text-sky-300/40">{a.action}</span>
            <Chip text={a.scope} health="waiting" />
          </div>
        </div>
      ))}
      <div className="hud-label pt-0.5 text-[7px] text-sky-300/35">No direct execution · routed through the Gate</div>
    </Panel>
  );
}

/** Audit stream with a slow "live" highlight cycling down the redacted event lines. */
function AuditPanel() {
  const [active, setActive] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setActive((i) => (i + 1) % AUDIT_STREAM.length), 2200);
    return () => clearInterval(id);
  }, []);
  return (
    <Panel title="Audit" code="AU·05">
      <div className="space-y-[5px]">
        {AUDIT_STREAM.slice(0, 5).map((e, i) => {
          const live = i === active % 5;
          return (
            <div key={`${e.event}-${i}`} className="flex items-center gap-1.5" style={{ opacity: live ? 1 : 0.5 }}>
              <span
                className={`inline-block h-1 w-1 shrink-0 rounded-full ${live ? "pulse-dot" : ""}`}
                style={{ background: live ? "#7dd3fc" : "#38507a", color: "#7dd3fc" }}
              />
              <span className="hud-mono truncate text-[7.5px] text-sky-200/80">
                {e.event}
                <span className="text-sky-300/35"> · {e.target} · </span>
                <span style={{ color: HEALTH_COLOR.active }}>{e.status}</span>
              </span>
            </div>
          );
        })}
      </div>
      <div className="hud-label pt-1 text-[7px] text-sky-300/30">Redacted summaries · display only</div>
    </Panel>
  );
}

function IntelPanel() {
  return (
    <Panel title="Intel Hub" code="IN·06">
      {INTEL_SIGNALS.map((s) => (
        <Row key={s.label} label={s.label} value={s.value} health={s.health} />
      ))}
      <div className="hud-line h-px w-full opacity-30" />
      <div className="hud-label text-[7px] text-sky-300/40">Projects</div>
      {PROJECTS.map((p) => (
        <Row key={p.name} label={p.name} value={p.state} health={p.health} />
      ))}
      <div className="hud-label pt-0.5 text-[7px] text-sky-300/30">Static preview · no live bridge yet</div>
    </Panel>
  );
}

/* ---------- rails ---------- */

export function LeftIntelRail() {
  return (
    <div className="pointer-events-none absolute left-6 top-1/2 z-20 hidden -translate-y-1/2 flex-col gap-3 lg:flex">
      <div className="hud-label hud-glow text-[10px] text-sky-100/90">GARVIS · Active</div>
      <RuntimePanel />
      <WorkflowsPanel />
      <AuditPanel />
    </div>
  );
}

export function RightIntelRail() {
  return (
    <div className="pointer-events-none absolute right-6 top-1/2 z-20 hidden -translate-y-1/2 flex-col items-end gap-3 lg:flex">
      <div className="listening hud-label text-[10px] text-sky-300/70">Intel Hub · Online</div>
      <SkillsPanel />
      <ApprovalsPanel />
      <IntelPanel />
    </div>
  );
}
