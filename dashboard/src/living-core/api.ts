// Living-core bridge to the real GARVIS backend (runtime command endpoint).
const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

export interface RuntimeResult {
  command_id: string;
  status: string;
  response_text: string;
  governance_decision?: { decision: string; allowed: boolean; reason: string } | null;
  errors?: string[];
}

export async function sendCommand(text: string, sessionId = "living-core"): Promise<RuntimeResult> {
  const res = await fetch(`${API_BASE}/runtime/command`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, source: "text", session_id: sessionId, metadata: {} }),
  });
  if (!res.ok) {
    throw new Error(`GARVIS backend ${res.status}`);
  }
  return res.json();
}
