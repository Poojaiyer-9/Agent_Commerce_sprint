import json

from app.audit.models import get_conn

AGENT_ICON = {
    "catalog_agent": "\U0001F4D1",
    "shopping_agent": "\U0001F6D2",
    "policy_agent": "\U0001F6E1",
    "checkout_agent": "\U0001F4B3",
    "upsell_agent": "✨",
}


def get_session_events(session_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_events WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
    events = []
    for row in rows:
        d = dict(row)
        for key in ("state_before", "state_after", "extra"):
            d[key] = json.loads(d[key]) if d[key] else None
        events.append(d)
    return events


def list_sessions(limit: int = 50) -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT session_id, MAX(id) as last_id FROM audit_events "
            "GROUP BY session_id ORDER BY last_id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [row["session_id"] for row in rows]


def render_human_readable(session_id: str) -> str:
    """Renders the full agent decision chain for a session as legible text.

    This is the CLI-equivalent of the frontend Audit Trail tab: it turns raw
    rows into a narrated sequence a judge/reviewer can read top to bottom.
    """
    events = get_session_events(session_id)
    if not events:
        return f"No audit events found for session '{session_id}'."

    lines = [f"Audit Trail — session {session_id}", "=" * 60]
    for e in events:
        icon = AGENT_ICON.get(e["agent"], "•")
        lines.append(f"\n{icon} [{e['timestamp']}] {e['agent']} -> {e['action']}")
        lines.append(f"   decision: {e['decision'].upper()}")
        lines.append(f"   reason:   {e['reason']}")
        if e.get("extra"):
            lines.append(f"   detail:   {json.dumps(e['extra'])}")
    lines.append("\n" + "=" * 60)
    lines.append(f"{len(events)} events total.")
    return "\n".join(lines)
