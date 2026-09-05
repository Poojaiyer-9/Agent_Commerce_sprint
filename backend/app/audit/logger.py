import json
from datetime import datetime, timezone

from app.audit.models import get_conn


def log_event(
    session_id: str,
    agent: str,
    action: str,
    decision: str,
    reason: str,
    state_before: dict | list | None = None,
    state_after: dict | list | None = None,
    extra: dict | None = None,
) -> dict:
    """Persist one structured audit event and return it as a dict.

    Every state transition in the graph (catalog query, policy check, cart
    change, payment attempt, retry, failure, success) should call this so
    the full agent decision chain is reconstructable per session.
    """
    event = {
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": agent,
        "action": action,
        "decision": decision,
        "reason": reason,
        "state_before": json.dumps(state_before, default=str) if state_before is not None else None,
        "state_after": json.dumps(state_after, default=str) if state_after is not None else None,
        "extra": json.dumps(extra, default=str) if extra is not None else None,
    }
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO audit_events
                (session_id, timestamp, agent, action, decision, reason, state_before, state_after, extra)
            VALUES (:session_id, :timestamp, :agent, :action, :decision, :reason, :state_before, :state_after, :extra)
            """,
            event,
        )
        event["id"] = cur.lastrowid
    return event
