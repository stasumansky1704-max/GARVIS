// Shared, honest status system for Mission Control.
// One model used across business factories and intelligence layers so the UI can never
// imply more readiness than is real.

export type Status =
  | "Concept"
  | "Blueprint"
  | "Prototype"
  | "Ready"
  | "Active"
  | "Connected"
  | "Not Connected";

type Meta = { color: string; glow: string; dot: string };

// Maturity progresses cool -> warm -> green; connection states are green/red.
export const STATUS_META: Record<Status, Meta> = {
  Concept:         { color: "#6f8ca8", glow: "rgba(111,140,168,0.16)", dot: "#6f8ca8" },
  Blueprint:       { color: "#00a3cc", glow: "rgba(0,163,204,0.18)",  dot: "#00a3cc" },
  Prototype:       { color: "#ffb347", glow: "rgba(255,179,71,0.18)", dot: "#ffb347" },
  Ready:           { color: "#00d4ff", glow: "rgba(0,212,255,0.22)",  dot: "#00d4ff" },
  Active:          { color: "#00ff9c", glow: "rgba(0,255,156,0.22)",  dot: "#00ff9c" },
  Connected:       { color: "#00ff9c", glow: "rgba(0,255,156,0.22)",  dot: "#00ff9c" },
  "Not Connected": { color: "#ff5d7a", glow: "rgba(255,93,122,0.16)", dot: "#ff5d7a" },
};

export function StatusBadge({ status, pulse }: { status: Status; pulse?: boolean }) {
  const meta = STATUS_META[status] ?? STATUS_META.Concept;
  const live = pulse ?? (status === "Active" || status === "Connected");
  return (
    <span
      className={`status-badge${live ? " status-badge--live" : ""}`}
      style={{
        color: meta.color,
        borderColor: meta.color,
        background: meta.glow,
      }}
    >
      <span className="status-badge-dot" style={{ background: meta.dot }} />
      {status}
    </span>
  );
}

export default StatusBadge;
