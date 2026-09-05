import operator
from typing import Annotated, TypedDict


class CartItem(TypedDict):
    product_id: str
    name: str
    unit_price_paise: int
    qty: int


class PolicyDecision(TypedDict):
    agent: str
    action: str
    approved: bool
    reason: str
    bounds_checked: dict
    timestamp: str


class PaymentAttempt(TypedDict):
    attempt_no: int
    order_id: str | None
    payment_id: str | None
    status: str  # "created" | "captured" | "failed" | "signature_invalid"
    failure_reason: str | None


class UpsellSuggestion(TypedDict):
    product_id: str
    name: str
    reason: str
    accepted: bool | None  # None until the user responds


class ProposedOption(TypedDict):
    product_id: str
    name: str
    unit_price_paise: int
    tier: str  # "most_affordable" | "best_value" | "premium_pick"
    tier_label: str  # human-readable, e.g. "Most Affordable"
    reason: str


def _append(a: list, b: list) -> list:
    return a + b


class AgentState(TypedDict):
    session_id: str
    user_goal: str

    catalog_snapshot: list[dict]
    proposed_options: Annotated[list[ProposedOption], _append]
    cart: Annotated[list[CartItem], _append]
    candidate_item: CartItem | None

    policy_decisions: Annotated[list[PolicyDecision], _append]
    payment_attempts: Annotated[list[PaymentAttempt], _append]
    upsell_suggestions: Annotated[list[UpsellSuggestion], _append]

    captured_order_ids: Annotated[list[str], _append]
    retry_count: int

    status: str  # browsing | policy_review | payment | retrying | failed | completed
    error: str | None
    reasoning_trace: Annotated[list[str], _append]
