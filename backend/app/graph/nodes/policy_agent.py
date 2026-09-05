from app.audit.logger import log_event
from app.policy.rules import evaluate_add_to_cart, evaluate_checkout, evaluate_retry


def _decision_dict(agent: str, result) -> dict:
    return {
        "agent": agent,
        "action": result.action,
        "approved": result.approved,
        "reason": result.reason,
        "bounds_checked": result.bounds_checked,
        "timestamp": "",
    }


def policy_agent_add_to_cart_node(state: dict) -> dict:
    session_id = state["session_id"]
    cart = state["cart"]
    candidate = state["candidate_item"]

    if candidate is None:
        return {"status": "no_match"}

    result = evaluate_add_to_cart(cart=cart, candidate=candidate, session_id=session_id)
    decision = _decision_dict("policy_agent", result)

    log_event(
        session_id=session_id,
        agent="policy_agent",
        action="add_to_cart",
        decision="approved" if result.approved else "denied",
        reason=result.reason,
        state_before={"cart": cart, "candidate": candidate},
        state_after={"approved": result.approved},
        extra={"bounds_checked": result.bounds_checked},
    )

    if result.approved:
        return {
            "cart": [candidate],
            "policy_decisions": [decision],
            "status": "approved_pending_upsell",
        }
    return {
        "policy_decisions": [decision],
        "status": "denied",
        "error": result.reason,
    }


def policy_agent_checkout_node(state: dict) -> dict:
    session_id = state["session_id"]
    result = evaluate_checkout(
        cart=state["cart"],
        session_id=session_id,
        already_captured_order_ids=state.get("captured_order_ids", []),
        session_status=state.get("status", ""),
    )
    decision = _decision_dict("policy_agent", result)

    log_event(
        session_id=session_id,
        agent="policy_agent",
        action="checkout",
        decision="approved" if result.approved else "denied",
        reason=result.reason,
        state_before={"cart": state["cart"]},
        state_after={"approved": result.approved},
        extra={"bounds_checked": result.bounds_checked},
    )

    return {
        "policy_decisions": [decision],
        "status": "checkout_approved" if result.approved else "denied",
        "error": None if result.approved else result.reason,
    }


def policy_agent_retry_node(state: dict) -> dict:
    session_id = state["session_id"]
    attempt_no = state.get("retry_count", 0) + 1
    result = evaluate_retry(attempt_no=attempt_no, session_id=session_id)
    decision = _decision_dict("policy_agent", result)

    log_event(
        session_id=session_id,
        agent="policy_agent",
        action="retry_payment",
        decision="approved" if result.approved else "denied",
        reason=result.reason,
        state_before={"retry_count": state.get("retry_count", 0)},
        state_after={"attempt_no": attempt_no, "approved": result.approved},
        extra={"bounds_checked": result.bounds_checked},
    )

    return {
        "policy_decisions": [decision],
        "retry_count": attempt_no,
        "status": "retry_approved" if result.approved else "retry_denied",
        "error": None if result.approved else result.reason,
    }
