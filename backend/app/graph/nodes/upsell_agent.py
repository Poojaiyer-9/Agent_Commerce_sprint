from app.audit.logger import log_event
from app.catalog.store import get_product


def upsell_agent_node(state: dict) -> dict:
    """After a successful cart addition, suggests 1-2 relevant add-ons using
    the catalog's declared upsell_ids relationship (rule-based). The
    suggestion + eventual accept/decline is logged so it's auditable like
    any other agent decision, even though it isn't a money-gated action.
    """
    session_id = state["session_id"]
    cart = state["cart"]
    if not cart:
        return {}

    last_item = cart[-1]
    product = get_product(last_item["product_id"])
    cart_ids = {i["product_id"] for i in cart}

    suggestions = []
    if product:
        for upsell_id in product.upsell_ids:
            if upsell_id in cart_ids:
                continue
            upsell_product = get_product(upsell_id)
            if not upsell_product or upsell_product.stock <= 0:
                continue
            suggestions.append(
                {
                    "product_id": upsell_product.id,
                    "name": upsell_product.name,
                    "reason": (
                        f"Pairs with '{product.name}' — customers who buy this "
                        f"item often add '{upsell_product.name}' "
                        f"(₹{upsell_product.price_paise/100:.2f})."
                    ),
                    "accepted": None,
                }
            )
            if len(suggestions) == 2:
                break

    reason = (
        f"Found {len(suggestions)} upsell candidate(s) for '{product.name if product else last_item['name']}'."
        if suggestions
        else "No relevant upsell candidates found for the current cart."
    )
    log_event(
        session_id=session_id,
        agent="upsell_agent",
        action="suggest_upsell",
        decision="suggested" if suggestions else "none",
        reason=reason,
        state_before={"cart": cart},
        state_after={"suggestions": suggestions},
    )

    return {
        "upsell_suggestions": suggestions,
        "status": "awaiting_upsell_response" if suggestions else "ready_for_checkout",
        "reasoning_trace": [f"upsell_agent: {reason}"],
    }
