"""In-memory session store keyed by session_id.

A single-process dict is sufficient for this demo (one merchant, one
FastAPI worker); every state transition is also durably logged to SQLite
via app.audit, so the audit trail survives even if this in-memory state
were lost.
"""
import uuid

from app.graph.state import AgentState

_SESSIONS: dict[str, AgentState] = {}


def new_session(user_goal: str) -> AgentState:
    session_id = str(uuid.uuid4())
    state: AgentState = {
        "session_id": session_id,
        "user_goal": user_goal,
        "catalog_snapshot": [],
        "proposed_options": [],
        "cart": [],
        "candidate_item": None,
        "policy_decisions": [],
        "payment_attempts": [],
        "upsell_suggestions": [],
        "captured_order_ids": [],
        "retry_count": 0,
        "status": "browsing",
        "error": None,
        "reasoning_trace": [],
    }
    _SESSIONS[session_id] = state
    return state


def get_session(session_id: str) -> AgentState | None:
    return _SESSIONS.get(session_id)


_APPEND_FIELDS = (
    "cart", "policy_decisions", "payment_attempts", "upsell_suggestions",
    "captured_order_ids", "reasoning_trace", "proposed_options",
)


def update_session(session_id: str, patch: dict) -> AgentState:
    """Applies a partial node-style patch (new items to append) onto a session."""
    state = _SESSIONS[session_id]
    for key, value in patch.items():
        if key in _APPEND_FIELDS and isinstance(value, list):
            state[key] = [*state.get(key, []), *value]
        else:
            state[key] = value
    return state


def replace_session(session_id: str, full_state: AgentState) -> AgentState:
    """Overwrites a session with an already-fully-merged state (e.g. a
    compiled LangGraph's invoke() output, which returns the complete state
    with reducers already applied — not a partial patch).
    """
    _SESSIONS[session_id] = full_state
    return full_state
