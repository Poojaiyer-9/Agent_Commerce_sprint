import time
from dataclasses import dataclass

from app.config import settings


@dataclass
class PolicyResult:
    action: str
    approved: bool
    reason: str
    bounds_checked: dict
    timestamp: str = ""


class RateLimiter:
    """In-memory sliding-window rate limiter, keyed by session_id.

    Kept simple (process-local dict) since this is a single-instance demo;
    a production version would back this with Redis.
    """

    def __init__(self, max_actions: int, window_seconds: int):
        self.max_actions = max_actions
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = {}

    def check_and_record(self, session_id: str) -> bool:
        now = time.time()
        hits = [t for t in self._hits.get(session_id, []) if now - t < self.window_seconds]
        allowed = len(hits) < self.max_actions
        if allowed:
            hits.append(now)
        self._hits[session_id] = hits
        return allowed


_rate_limiter = RateLimiter(
    max_actions=settings.policy_rate_limit_actions,
    window_seconds=settings.policy_rate_limit_window_seconds,
)


def evaluate_add_to_cart(cart: list[dict], candidate: dict, session_id: str) -> PolicyResult:
    """Gate for adding one item to the cart.

    Bounds enforced, each independently checked and reported:
      1. rate limit — too many gated actions in the window
      2. single-item price ceiling
      3. projected cart total ceiling (existing cart + candidate)
    """
    bounds_checked = {
        "max_single_item_price_paise": settings.policy_max_single_item_price_paise,
        "max_cart_value_paise": settings.policy_max_cart_value_paise,
        "rate_limit_actions": settings.policy_rate_limit_actions,
        "rate_limit_window_seconds": settings.policy_rate_limit_window_seconds,
    }

    if not _rate_limiter.check_and_record(session_id):
        return PolicyResult(
            action="add_to_cart",
            approved=False,
            reason=(
                f"Rate limit exceeded: more than {settings.policy_rate_limit_actions} "
                f"gated actions within {settings.policy_rate_limit_window_seconds}s."
            ),
            bounds_checked=bounds_checked,
        )

    item_price = candidate["unit_price_paise"] * candidate.get("qty", 1)
    if item_price > settings.policy_max_single_item_price_paise:
        return PolicyResult(
            action="add_to_cart",
            approved=False,
            reason=(
                f"Item '{candidate.get('name', candidate.get('product_id'))}' line total "
                f"₹{item_price/100:.2f} exceeds max single-item price "
                f"₹{settings.policy_max_single_item_price_paise/100:.2f}."
            ),
            bounds_checked=bounds_checked,
        )

    current_total = sum(i["unit_price_paise"] * i["qty"] for i in cart)
    projected_total = current_total + item_price
    if projected_total > settings.policy_max_cart_value_paise:
        return PolicyResult(
            action="add_to_cart",
            approved=False,
            reason=(
                f"Projected cart total ₹{projected_total/100:.2f} would exceed max cart value "
                f"₹{settings.policy_max_cart_value_paise/100:.2f}."
            ),
            bounds_checked=bounds_checked,
        )

    return PolicyResult(
        action="add_to_cart",
        approved=True,
        reason=(
            f"Within bounds: item ₹{item_price/100:.2f} <= max item "
            f"₹{settings.policy_max_single_item_price_paise/100:.2f}; "
            f"projected cart ₹{projected_total/100:.2f} <= max cart "
            f"₹{settings.policy_max_cart_value_paise/100:.2f}."
        ),
        bounds_checked=bounds_checked,
    )


def evaluate_checkout(
    cart: list[dict],
    session_id: str,
    already_captured_order_ids: list[str],
    target_order_id: str | None = None,
    session_status: str = "",
) -> PolicyResult:
    """Second, final gate before money moves: re-checks cart total and
    blocks a duplicate charge against an order that's already captured.

    ``session_status`` is the session's current status *at the moment
    checkout is requested* (before this evaluation runs). It's how the
    duplicate-charge guard actually engages in the live flow: the API
    layer never has a captured order_id to compare against ahead of
    time (that's `target_order_id`, used by the direct-call test path),
    but it always knows whether this session already has a captured
    payment or one in flight, and that's exactly what must block a
    second checkout against the same cart.
    """
    bounds_checked = {
        "max_cart_value_paise": settings.policy_max_cart_value_paise,
        "duplicate_charge_guard": True,
    }

    if target_order_id and target_order_id in already_captured_order_ids:
        return PolicyResult(
            action="checkout",
            approved=False,
            reason=f"Duplicate-charge guard: order '{target_order_id}' is already captured.",
            bounds_checked=bounds_checked,
        )

    if session_status == "completed":
        return PolicyResult(
            action="checkout",
            approved=False,
            reason="Duplicate-charge guard: this session already has a captured payment.",
            bounds_checked=bounds_checked,
        )

    if session_status == "awaiting_payment":
        return PolicyResult(
            action="checkout",
            approved=False,
            reason="A payment is already in progress for this session; refusing to open a second checkout.",
            bounds_checked=bounds_checked,
        )

    if not cart:
        return PolicyResult(
            action="checkout",
            approved=False,
            reason="Cart is empty; nothing to charge.",
            bounds_checked=bounds_checked,
        )

    total = sum(i["unit_price_paise"] * i["qty"] for i in cart)
    if total > settings.policy_max_cart_value_paise:
        return PolicyResult(
            action="checkout",
            approved=False,
            reason=(
                f"Cart total ₹{total/100:.2f} exceeds max cart value "
                f"₹{settings.policy_max_cart_value_paise/100:.2f}."
            ),
            bounds_checked=bounds_checked,
        )

    return PolicyResult(
        action="checkout",
        approved=True,
        reason=f"Cart total ₹{total/100:.2f} within bound and no duplicate charge detected.",
        bounds_checked=bounds_checked,
    )


def evaluate_retry(attempt_no: int, session_id: str) -> PolicyResult:
    bounds_checked = {"max_retry_attempts": settings.policy_max_retry_attempts}
    if attempt_no > settings.policy_max_retry_attempts:
        return PolicyResult(
            action="retry_payment",
            approved=False,
            reason=(
                f"Retry attempt {attempt_no} exceeds max retry attempts "
                f"({settings.policy_max_retry_attempts})."
            ),
            bounds_checked=bounds_checked,
        )
    return PolicyResult(
        action="retry_payment",
        approved=True,
        reason=f"Retry attempt {attempt_no} within max retry attempts ({settings.policy_max_retry_attempts}).",
        bounds_checked=bounds_checked,
    )


def reset_rate_limiter() -> None:
    """Test helper — clears in-memory rate-limit state between test cases."""
    _rate_limiter._hits.clear()
