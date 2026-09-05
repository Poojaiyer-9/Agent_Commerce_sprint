from app.audit.logger import log_event
from app.razorpay_client import capture_payment, create_order, fetch_payment, verify_payment_signature


def create_order_node(state: dict) -> dict:
    """Creates a Razorpay TEST-MODE order for the current cart total.

    Payment itself happens client-side via Razorpay Checkout.js (it needs a
    card entry UI), so this node only creates the order; capture + signature
    verification happen in confirm_payment / handle_payment_failure once the
    frontend hands back the checkout result.
    """
    session_id = state["session_id"]
    cart = state["cart"]
    total_paise = sum(i["unit_price_paise"] * i["qty"] for i in cart)
    attempt_no = len(state.get("payment_attempts", [])) + 1

    try:
        order = create_order(
            amount_paise=total_paise,
            receipt=f"{session_id}-{attempt_no}",
            notes={"session_id": session_id, "attempt_no": str(attempt_no)},
        )
    except Exception as exc:  # noqa: BLE001 - surfaced to the caller as a failed attempt
        attempt = {
            "attempt_no": attempt_no,
            "order_id": None,
            "payment_id": None,
            "status": "failed",
            "failure_reason": f"Razorpay order creation error: {exc}",
        }
        log_event(
            session_id=session_id,
            agent="checkout_agent",
            action="create_order",
            decision="error",
            reason=str(exc),
            state_before={"cart": cart, "total_paise": total_paise},
            state_after=attempt,
        )
        return {"payment_attempts": [attempt], "status": "failed", "error": str(exc)}

    attempt = {
        "attempt_no": attempt_no,
        "order_id": order["id"],
        "payment_id": None,
        "status": "created",
        "failure_reason": None,
    }
    log_event(
        session_id=session_id,
        agent="checkout_agent",
        action="create_order",
        decision="created",
        reason=f"Created Razorpay order {order['id']} for ₹{total_paise/100:.2f}.",
        state_before={"cart": cart, "total_paise": total_paise},
        state_after=attempt,
    )

    return {"payment_attempts": [attempt], "status": "awaiting_payment"}


def confirm_payment(session_id: str, order_id: str, payment_id: str, signature: str) -> dict:
    """Called by the /payment/success endpoint after Checkout.js succeeds.

    Verifies the signature, fetches + captures the payment, and logs both
    steps distinctly so a forged/tampered client callback is caught and
    surfaced in the audit trail rather than silently trusted.
    """
    valid = verify_payment_signature(order_id, payment_id, signature)
    log_event(
        session_id=session_id,
        agent="checkout_agent",
        action="verify_signature",
        decision="valid" if valid else "invalid",
        reason=(
            "Razorpay signature verified against order_id + payment_id."
            if valid
            else "Signature verification FAILED — possible tampering; payment not captured."
        ),
        state_before={"order_id": order_id, "payment_id": payment_id},
        state_after={"valid": valid},
    )

    if not valid:
        return {
            "status": "failed",
            "attempt": {
                "order_id": order_id,
                "payment_id": payment_id,
                "status": "signature_invalid",
                "failure_reason": "signature_verification_failed",
            },
        }

    payment = fetch_payment(payment_id)
    total_paise = payment["amount"]

    if payment["status"] != "captured":
        payment = capture_payment(payment_id, amount_paise=total_paise)

    log_event(
        session_id=session_id,
        agent="checkout_agent",
        action="capture_payment",
        decision=payment["status"],
        reason=f"Payment {payment_id} status: {payment['status']} for order {order_id}.",
        state_before={"order_id": order_id, "payment_id": payment_id},
        state_after={"status": payment["status"], "amount_paise": total_paise},
    )

    return {
        "status": "completed" if payment["status"] == "captured" else "failed",
        "attempt": {
            "order_id": order_id,
            "payment_id": payment_id,
            "status": payment["status"],
            "failure_reason": None,
        },
    }


def handle_payment_failure(session_id: str, order_id: str | None, reason: str) -> None:
    """Logs a client-reported decline (Checkout.js payment.failed handler)."""
    log_event(
        session_id=session_id,
        agent="checkout_agent",
        action="payment_declined",
        decision="failed",
        reason=reason,
        state_before={"order_id": order_id},
        state_after=None,
    )
