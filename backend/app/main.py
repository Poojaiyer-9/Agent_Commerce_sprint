from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.audit.models import init_db
from app.audit.viewer import get_session_events, list_sessions, render_human_readable
from app.catalog.store import get_product, load_catalog
from app.config import settings
from app.graph.builder import browse_graph, checkout_graph, retry_graph
from app.graph.nodes.checkout_agent import confirm_payment, handle_payment_failure
from app.graph.nodes.policy_agent import policy_agent_add_to_cart_node
from app.graph.nodes.upsell_agent import upsell_agent_node
from app.sessions import get_session, new_session, replace_session, update_session

app = FastAPI(title="AgentCommerce API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    load_catalog()  # fail fast if the demo catalog hasn't been seeded


class StartSessionRequest(BaseModel):
    user_goal: str


@app.get("/catalog")
def get_catalog():
    return [p.model_dump() for p in load_catalog()]


@app.post("/session/start")
def start_session(req: StartSessionRequest):
    state = new_session(req.user_goal)
    result = browse_graph.invoke(state)
    replace_session(state["session_id"], result)
    return result


@app.get("/session/{session_id}")
def get_session_state(session_id: str):
    state = get_session(session_id)
    if state is None:
        raise HTTPException(404, "Session not found")
    return state


class SelectOptionRequest(BaseModel):
    product_id: str


@app.post("/session/{session_id}/select-option")
def select_option(session_id: str, req: SelectOptionRequest):
    """Gates and adds the user's chosen tiered option (Most Affordable /
    Best Value / Premium Pick) to the cart, then runs the Upsell Agent —
    the same policy-gated pattern used for upsell acceptance, just for
    the Shopping Agent's initial proposal instead of an add-on.
    """
    state = get_session(session_id)
    if state is None:
        raise HTTPException(404, "Session not found")

    options = state.get("proposed_options", [])
    match = next((o for o in options if o["product_id"] == req.product_id), None)
    if match is None:
        raise HTTPException(404, "Proposed option not found")

    candidate = {
        "product_id": match["product_id"],
        "name": match["name"],
        "unit_price_paise": match["unit_price_paise"],
        "qty": 1,
    }
    gate_input = {**state, "candidate_item": candidate}
    patch = policy_agent_add_to_cart_node(gate_input)
    update_session(session_id, patch)

    state = get_session(session_id)
    if state["status"] != "approved_pending_upsell":
        # Denied (e.g. rate-limited) — surface the reason, don't proceed to upsell.
        return state

    upsell_patch = upsell_agent_node(state)
    update_session(session_id, upsell_patch)
    return get_session(session_id)


class UpsellResponseRequest(BaseModel):
    product_id: str
    accepted: bool


@app.post("/session/{session_id}/upsell-response")
def upsell_response(session_id: str, req: UpsellResponseRequest):
    state = get_session(session_id)
    if state is None:
        raise HTTPException(404, "Session not found")

    suggestions = state.get("upsell_suggestions", [])
    match = next((s for s in suggestions if s["product_id"] == req.product_id), None)
    if match is None:
        raise HTTPException(404, "Upsell suggestion not found")
    match["accepted"] = req.accepted

    if not req.accepted:
        state["status"] = "ready_for_checkout"
        return state

    product = get_product(req.product_id)
    if product is None:
        raise HTTPException(404, "Product not found")

    candidate = {
        "product_id": product.id,
        "name": product.name,
        "unit_price_paise": product.price_paise,
        "qty": 1,
    }
    gate_input = {**state, "candidate_item": candidate}
    patch = policy_agent_add_to_cart_node(gate_input)
    update_session(session_id, patch)

    # Whether the Policy Agent approved or denied the add-on, the upsell
    # interaction itself is resolved either way — the original cart item
    # is still valid and checkout should not be left stuck on a denied
    # add-on. The denial is already recorded in policy_decisions for the
    # audit trail; it just shouldn't block the base purchase.
    state = get_session(session_id)
    state["status"] = "ready_for_checkout"
    return state


@app.post("/session/{session_id}/checkout")
def checkout(session_id: str):
    state = get_session(session_id)
    if state is None:
        raise HTTPException(404, "Session not found")

    result = checkout_graph.invoke(state)
    replace_session(session_id, result)

    if result["status"] != "awaiting_payment":
        return {"status": result["status"], "error": result.get("error"), "state": result}

    last_attempt = result["payment_attempts"][-1]
    return {
        "status": "awaiting_payment",
        "order_id": last_attempt["order_id"],
        "amount_paise": sum(i["unit_price_paise"] * i["qty"] for i in result["cart"]),
        "currency": "INR",
        "razorpay_key_id": settings.razorpay_key_id,
        "state": result,
    }


class PaymentSuccessRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


@app.post("/session/{session_id}/payment/success")
def payment_success(session_id: str, req: PaymentSuccessRequest):
    state = get_session(session_id)
    if state is None:
        raise HTTPException(404, "Session not found")

    result = confirm_payment(
        session_id=session_id,
        order_id=req.razorpay_order_id,
        payment_id=req.razorpay_payment_id,
        signature=req.razorpay_signature,
    )
    patch = {
        "payment_attempts": [result["attempt"]],
        "status": result["status"],
    }
    if result["status"] == "completed":
        patch["captured_order_ids"] = [req.razorpay_order_id]
    updated = update_session(session_id, patch)
    return updated


class PaymentFailureRequest(BaseModel):
    order_id: str | None = None
    reason: str


@app.post("/session/{session_id}/payment/failed")
def payment_failed(session_id: str, req: PaymentFailureRequest):
    state = get_session(session_id)
    if state is None:
        raise HTTPException(404, "Session not found")

    handle_payment_failure(session_id, req.order_id, req.reason)
    update_session(
        session_id,
        {
            "payment_attempts": [
                {
                    "attempt_no": len(state.get("payment_attempts", [])) + 1,
                    "order_id": req.order_id,
                    "payment_id": None,
                    "status": "failed",
                    "failure_reason": req.reason,
                }
            ],
            "status": "retrying",
        },
    )

    state = get_session(session_id)
    retry_result = retry_graph.invoke(state)
    replace_session(session_id, retry_result)

    if retry_result["status"] != "awaiting_payment":
        return {"status": "failed", "error": retry_result.get("error"), "state": retry_result}

    last_attempt = retry_result["payment_attempts"][-1]
    return {
        "status": "awaiting_payment",
        "order_id": last_attempt["order_id"],
        "amount_paise": sum(i["unit_price_paise"] * i["qty"] for i in retry_result["cart"]),
        "currency": "INR",
        "razorpay_key_id": settings.razorpay_key_id,
        "state": retry_result,
    }


@app.get("/sessions")
def sessions_list():
    return list_sessions()


@app.get("/session/{session_id}/audit")
def session_audit(session_id: str):
    return get_session_events(session_id)


@app.get("/session/{session_id}/audit/text")
def session_audit_text(session_id: str):
    return {"text": render_human_readable(session_id)}
