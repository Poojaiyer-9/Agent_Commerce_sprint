import pytest

from app.audit.logger import log_event
from app.audit.models import init_db
from app.audit.viewer import get_session_events, render_human_readable


@pytest.fixture(autouse=True)
def _setup():
    init_db()
    yield


def test_log_event_persists_structured_fields():
    event = log_event(
        session_id="audit-1",
        agent="policy_agent",
        action="add_to_cart",
        decision="approved",
        reason="Within bounds.",
        state_before={"cart": []},
        state_after={"cart": [{"product_id": "p1"}]},
        extra={"bounds_checked": {"max_cart_value_paise": 1_000_000}},
    )

    assert event["id"] is not None
    events = get_session_events("audit-1")
    assert len(events) == 1
    assert events[0]["agent"] == "policy_agent"
    assert events[0]["decision"] == "approved"
    assert events[0]["state_before"] == {"cart": []}
    assert events[0]["extra"]["bounds_checked"]["max_cart_value_paise"] == 1_000_000


def test_events_are_ordered_and_scoped_per_session():
    log_event("audit-2", "catalog_agent", "query_catalog", "ok", "matched 3")
    log_event("audit-2", "shopping_agent", "propose_cart_item", "proposed", "picked item")
    log_event("audit-other", "catalog_agent", "query_catalog", "ok", "unrelated session")

    events = get_session_events("audit-2")
    assert [e["agent"] for e in events] == ["catalog_agent", "shopping_agent"]


def test_human_readable_render_includes_agent_and_reason():
    log_event("audit-3", "policy_agent", "checkout", "denied", "Cart total exceeds max cart value ₹10000.00.")

    text = render_human_readable("audit-3")
    assert "policy_agent" in text
    assert "DENIED" in text
    assert "Cart total exceeds max cart value" in text


def test_human_readable_handles_missing_session_gracefully():
    text = render_human_readable("does-not-exist")
    assert "No audit events found" in text
