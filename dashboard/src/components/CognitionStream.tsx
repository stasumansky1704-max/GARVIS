// =============================================================================
// CognitionStream — Phase 3: Live cognition event stream
// =============================================================================

import React, { useState, useRef, useEffect } from "react";
import Panel from "./common/Panel";
import Badge from "./common/Badge";
import { useApi } from "@/hooks/useApi";
import { api } from "@/api";
import type { CognitionEvent } from "@/types";

const severityBadge = (s: string) => s as "info" | "warn" | "critical" | "low";

const CognitionStream: React.FC = () => {
  const { data: events } = useApi(api.cognition.getEvents);
  const [paused, setPaused] = useState(false);
  const [filterType, setFilterType] = useState<string>("all");
  const scrollRef = useRef<HTMLDivElement>(null);

  const filtered = (events || []).filter((e) => {
    if (filterType === "all") return true;
    return e.severity === filterType;
  });

  useEffect(() => {
    if (!paused && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [filtered.length, paused]);

  const eventTypes = ["all", "info", "warning", "critical"];

  return (
    <Panel
      title="Live Cognition Stream"
      actions={
        <>
          <select value={filterType} onChange={(e) => setFilterType(e.target.value)}>
            {eventTypes.map((t) => (
              <option key={t} value={t}>{t.toUpperCase()}</option>
            ))}
          </select>
          <button className={`btn ${paused ? "btn-primary" : ""}`} onClick={() => setPaused(!paused)}>
            {paused ? "RESUME" : "PAUSE"}
          </button>
        </>
      }
      style={{ height: "100%" }}
    >
      <div ref={scrollRef} className="stream-feed" style={{ overflowY: "auto", flex: 1 }}>
        {filtered.map((evt) => (
          <StreamEntry key={evt.event_id} event={evt} />
        ))}
      </div>
    </Panel>
  );
};

const StreamEntry: React.FC<{ event: CognitionEvent }> = ({ event }) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="stream-entry" onClick={() => setExpanded(!expanded)} style={{ cursor: "pointer" }}>
      <span className="stream-timestamp">{event.timestamp.slice(11, 19)}</span>
      <span className="stream-badge">
        <Badge label={event.severity.toUpperCase()} variant={severityBadge(event.severity)} size="sm" />
      </span>
      <span className="stream-badge">
        <Badge label={event.event_type.toUpperCase()} variant="default" size="sm" />
      </span>
      <span className="stream-message" style={{ color: "#ccc" }}>
        {event.message}
      </span>
    </div>
  );
};

export default CognitionStream;
