from unittest.mock import MagicMock, patch

import pytest

from app.audit.models import init_db
from app.graph.builder import checkout_graph, retry_graph
from app.graph.nodes.checkout_agent import confirm_payment
from app.policy.rules import reset_rate_limiter


@pytest.fixture(autouse=True)
def _setup():
    init_db()
    reset_rate_limiter()
    yield


def _base_state(session_id: str):
    return {
        "session_id": session_id,
        "user_goal": "test goal",
        "catalog_snapshot": [],
        "cart": [{"product_id": "p1", "name": "Test Bag", "unit_price_paise": 129_900, "qty": 1}],
        "candidate_item": None,
        "policy_decisions": [],
        "payment_attempts": [],
        "upsell_suggestions": [],
        "captured_order_ids": [],
        "retry_count": 0,
        "status": "ready_for_checkout",
        "error": None,
        "reasoning_trace": [],
    }


@patch("app.graph.nodes.checkout_agent.create_order")
def test_checkout_creates_order_when_policy_approves(mock_create_order):
    mock_create_order.return_value = {"id": "order_test123", "amount": 129_900, "currency": "INR"}

    result = checkout_graph.invoke(_base_state("sess-success"))

    assert result["status"] == "awaiting_payment"
    assert result["payment_attempts"][-1]["order_id"] == "order_test123"
    assert result["policy_decisions"][-1]["approved"] is True


def test_checkout_denied_on_empty_cart():
    state = _base_state("sess-empty")
    state["cart"] = []

    result = checkout_graph.invoke(state)

    assert result["status"] == "denied"
    assert "empty" in result["policy_decisions"][-1]["reason"].lower()


@patch("app.graph.nodes.checkout_agent.capture_payment")
@patch("app.graph.nodes.checkout_agent.fetch_payment")
@patch("app.graph.nodes.checkout_agent.verify_payment_signature")
def test_confirm_payment_success_path(mock_verify, mock_fetch, mock_capture):
    mock_verify.return_value = True
    mock_fetch.return_value = {"id": "pay_1", "status": "authorized", "amount": 129_900}
    mock_capture.return_value = {"id": "pay_1", "status": "captured", "amount": 129_900}

    result = confirm_payment(
        session_id="sess-pay-ok",
        order_id="order_test123",
        payment_id="pay_1",
        signature="valid_sig",
    )

    assert result["status"] == "completed"
    assert result["attempt"]["status"] == "captured"
    mock_capture.assert_called_once()


@patch("app.graph.nodes.checkout_agent.verify_payment_signature")
def test_confirm_payment_rejects_invalid_signature(mock_verify):
    mock_verify.return_value = False

    result = confirm_payment(
        session_id="sess-pay-tampered",
        order_id="order_test123",
        payment_id="pay_1",
        signature="bad_sig",
    )

    assert result["status"] == "failed"
    assert result["attempt"]["status"] == "signature_invalid"


@patch("app.graph.nodes.checkout_agent.create_order")
def test_declined_payment_triggers_gated_retry_then_new_order(mock_create_order):
    """Simulates the graceful-failure demo path: a declined test-card payment
    is followed by a policy-gated retry that creates a fresh order, without
    crashing or losing cart state.
    """
    mock_create_order.return_value = {"id": "order_retry_1", "amount": 129_900, "currency": "INR"}

    state = _base_state("sess-decline")
    state["payment_attempts"] = [
        {"attempt_no": 1, "order_id": "order_failed_1", "payment_id": None,
         "status": "failed", "failure_reason": "Card declined by mock bank page"}
    ]
    state["retry_count"] = 0

    result = retry_graph.invoke(state)

    assert result["status"] == "awaiting_payment"
    assert result["payment_attempts"][-1]["order_id"] == "order_retry_1"
    assert result["retry_count"] == 1
    assert result["policy_decisions"][-1]["action"] == "retry_payment"
    assert result["policy_decisions"][-1]["approved"] is True


@patch("app.graph.nodes.checkout_agent.create_order")
def test_checkout_graph_denies_second_checkout_on_completed_session(mock_create_order):
    """Regression for the double-charge gap: calling POST /checkout again
    on a session whose status is already "completed" must be refused by
    the Policy Agent, not silently create (and risk paying) a second order.
    """
    state = _base_state("sess-already-paid")
    state["status"] = "completed"
    state["captured_order_ids"] = ["order_already_paid"]

    result = checkout_graph.invoke(state)

    assert result["status"] == "denied"
    assert "already has a captured payment" in result["policy_decisions"][-1]["reason"].lower()
    mock_create_order.assert_not_called()


@patch("app.graph.nodes.checkout_agent.create_order")
def test_checkout_graph_denies_second_checkout_while_awaiting_payment(mock_create_order):
    state = _base_state("sess-mid-payment")
    state["status"] = "awaiting_payment"

    result = checkout_graph.invoke(state)

    assert result["status"] == "denied"
    assert "already in progress" in result["policy_decisions"][-1]["reason"].lower()
    mock_create_order.assert_not_called()


@patch("app.graph.nodes.checkout_agent.create_order")
def test_retry_denied_after_max_attempts_exceeded(mock_create_order):
    state = _base_state("sess-max-retries")
    state["retry_count"] = 2  # already at policy_max_retry_attempts default

    result = retry_graph.invoke(state)

    assert result["status"] == "retry_denied"
    assert "exceeds max retry attempts" in result["policy_decisions"][-1]["reason"]
    mock_create_order.assert_not_called()
