import { useEffect, useState } from "react";
import { api, type AuditEvent } from "../api/client";

const AGENT_ICON: Record<string, string> = {
  catalog_agent: "📑",
  shopping_agent: "🛒",
  policy_agent: "🛡️",
  checkout_agent: "💳",
  upsell_agent: "✨",
};

export function AuditTrailView({ sessionId }: { sessionId: string | null }) {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = () => {
    if (!sessionId) return;
    setLoading(true);
    api
      .getAudit(sessionId)
      .then(setEvents)
      .finally(() => setLoading(false));
  };

  useEffect(refresh, [sessionId]);

  if (!sessionId) {
    return <div className="empty-state">Start a session in the Shop tab to see its audit trail here.</div>;
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
        <div className="dim mono" style={{ fontSize: 12 }}>session {sessionId}</div>
        <button className="btn small" onClick={refresh} disabled={loading}>
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>
      {events.length === 0 ? (
        <div className="empty-state">No events logged yet.</div>
      ) : (
        <table className="audit-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Time</th>
              <th>Agent</th>
              <th>Action</th>
              <th>Decision</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.id}>
                <td className="dim">{e.id}</td>
                <td className="mono dim">{new Date(e.timestamp).toLocaleTimeString()}</td>
                <td>{AGENT_ICON[e.agent] ?? "•"} {e.agent}</td>
                <td>{e.action}</td>
                <td>
                  <span className={`status-pill ${e.decision}`}>{e.decision}</span>
                </td>
                <td>{e.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
