from app.audit.logger import log_event

_TIERS = [
    ("most_affordable", "Most Affordable"),
    ("best_value", "Best Value"),
    ("premium_pick", "Premium Pick"),
]


def _reason_for(tier: str, product: dict) -> str:
    material = product.get("attributes", {}).get("material")
    hint = f", {material}" if material else ""
    price = f"₹{product['price_paise']/100:.2f}"
    if tier == "most_affordable":
        return f"Lowest price match ({price}{hint}) — good for short-term or budget use."
    if tier == "premium_pick":
        return f"Highest price point in the match set ({price}{hint}) — built for durability and longer-term use."
    return f"Balanced price and quality ({price}{hint}) — the middle ground between budget and premium."


def _pick_tiered_options(catalog: list[dict]) -> list[dict]:
    """Selects up to 3 distinct products across the price range of the
    matched catalog: cheapest, a middle pick, and the most expensive —
    a deterministic stand-in for "cheap and best / mid-range / luxury"
    the way a human shopping assistant would triage options, without
    relying on a ratings field the catalog doesn't have.
    """
    if not catalog:
        return []

    ranked = sorted(catalog, key=lambda p: p["price_paise"])
    n = len(ranked)

    if n == 1:
        # Only one match: it's simultaneously the cheapest and priciest
        # option available, so label it plainly rather than picking an
        # arbitrary tier.
        slots = [(0, "most_affordable", "Most Affordable")]
    elif n == 2:
        slots = [(0, "most_affordable", "Most Affordable"), (n - 1, "premium_pick", "Premium Pick")]
    else:
        indices = sorted({0, n // 2, n - 1})
        slots = [(idx, tier, label) for idx, (tier, label) in zip(indices, _TIERS)]

    options = []
    for idx, tier, tier_label in slots:
        product = ranked[idx]
        options.append(
            {
                "product_id": product["id"],
                "name": product["name"],
                "unit_price_paise": product["price_paise"],
                "tier": tier,
                "tier_label": tier_label,
                "reason": _reason_for(tier, product),
            }
        )
    return options


def shopping_agent_node(state: dict) -> dict:
    """The AI buyer: reasons over the catalog snapshot returned by the
    Catalog Agent and proposes up to 3 tiered options for the user to
    choose from, instead of unilaterally picking one — closer to how a
    human shopping assistant triages "cheap and cheerful" vs. "best
    value" vs. "premium" rather than silently defaulting to cheapest.

    Ranking is deterministic (by price within the matched set) rather
    than an LLM choice, so the demo path stays reproducible; the
    reasoning is still expressed in natural language and logged like
    any other agent decision.
    """
    session_id = state["session_id"]
    catalog = state["catalog_snapshot"]

    if not catalog:
        reason = "No products in the catalog matched the user's goal; nothing to propose."
        log_event(
            session_id=session_id,
            agent="shopping_agent",
            action="propose_options",
            decision="no_match",
            reason=reason,
            state_before={"catalog_count": 0},
            state_after=None,
        )
        return {
            "proposed_options": [],
            "status": "no_match",
            "reasoning_trace": [f"shopping_agent: {reason}"],
        }

    options = _pick_tiered_options(catalog)
    reason = (
        f"Triaged {len(catalog)} matching product(s) into {len(options)} option(s) — "
        + "; ".join(f"{o['tier_label']}: '{o['name']}' at ₹{o['unit_price_paise']/100:.2f}" for o in options)
        + "."
    )
    log_event(
        session_id=session_id,
        agent="shopping_agent",
        action="propose_options",
        decision="proposed",
        reason=reason,
        state_before={"catalog_count": len(catalog)},
        state_after={"options": options},
    )

    return {
        "proposed_options": options,
        "status": "awaiting_option_selection",
        "reasoning_trace": [f"shopping_agent: {reason}"],
    }
