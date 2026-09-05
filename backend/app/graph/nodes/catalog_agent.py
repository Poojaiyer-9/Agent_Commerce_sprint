import re

from app.audit.logger import log_event
from app.catalog.store import query_catalog

_PRICE_RE = re.compile(r"under\s*(?:rs\.?|inr|₹)?\s*(\d[\d,]*)", re.IGNORECASE)
_CATEGORY_KEYWORDS = {
    "bag": "bags", "bags": "bags", "backpack": "bags", "briefcase": "bags",
    "sleeve": "accessories", "mouse": "accessories", "charger": "accessories",
    "stand": "accessories", "keyboard": "accessories", "hub": "accessories", "lock": "accessories",
}


def catalog_agent_node(state: dict) -> dict:
    """Parses the user's natural-language goal into catalog query filters
    and exposes the matching agent-readable products.
    """
    goal = state["user_goal"]
    before = {"user_goal": goal}

    max_price_paise = None
    m = _PRICE_RE.search(goal)
    if m:
        max_price_paise = int(m.group(1).replace(",", "")) * 100

    category = None
    lowered = goal.lower()
    for kw, cat in _CATEGORY_KEYWORDS.items():
        if kw in lowered:
            category = cat
            break

    results = query_catalog(max_price_paise=max_price_paise, category=category)
    snapshot = [p.model_dump() for p in results]

    reason = (
        f"Parsed goal into filters: max_price_paise={max_price_paise}, category={category!r}. "
        f"Matched {len(snapshot)} product(s)."
    )
    log_event(
        session_id=state["session_id"],
        agent="catalog_agent",
        action="query_catalog",
        decision="ok",
        reason=reason,
        state_before=before,
        state_after={"matched_count": len(snapshot), "product_ids": [p["id"] for p in snapshot]},
    )

    return {
        "catalog_snapshot": snapshot,
        "reasoning_trace": [f"catalog_agent: {reason}"],
    }
