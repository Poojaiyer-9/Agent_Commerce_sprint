import type { PolicyDecision } from "../api/client";

export function PolicyLog({ decisions }: { decisions: PolicyDecision[] }) {
  if (decisions.length === 0) {
    return <div className="empty-state">No policy decisions yet. Start a chat to see the Policy Agent gate actions here.</div>;
  }
  return (
    <div className="policy-log">
      {decisions.map((d, i) => (
        <div className="policy-entry" key={i}>
          <div>
            <span className={`badge ${d.approved ? "approved" : "denied"}`}>
              {d.approved ? "✓ Approved" : "✕ Denied"}
            </span>{" "}
            <strong style={{ fontSize: 13 }}>{d.action.replace(/_/g, " ")}</strong>
          </div>
          <div className="reason">{d.reason}</div>
          <div className="bounds">
            {Object.entries(d.bounds_checked).map(([k, v]) => (
              <span key={k}>
                {k}: <span className="mono">{String(v)}</span>
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
