import pytest

from app.policy.rules import evaluate_add_to_cart, evaluate_checkout, evaluate_retry, reset_rate_limiter


@pytest.fixture(autouse=True)
def _clear_rate_limiter():
    reset_rate_limiter()
    yield
    reset_rate_limiter()


def _item(price_paise: int, qty: int = 1, name: str = "Item"):
    return {"product_id": "p1", "name": name, "unit_price_paise": price_paise, "qty": qty}


class TestAddToCartBounds:
    def test_approves_item_within_bounds(self):
        result = evaluate_add_to_cart(cart=[], candidate=_item(129_900), session_id="s1")
        assert result.approved is True
        assert "within bounds" in result.reason.lower()

    def test_denies_single_item_over_max_price(self):
        # policy_max_single_item_price_paise default = 500_000 (₹5000)
        result = evaluate_add_to_cart(cart=[], candidate=_item(600_000), session_id="s2")
        assert result.approved is False
        assert "exceeds max single-item price" in result.reason

    def test_denies_when_projected_cart_total_exceeds_max(self):
        # max cart value default = 1_000_000 (₹10000)
        existing_cart = [_item(900_000, name="Existing")]
        result = evaluate_add_to_cart(cart=existing_cart, candidate=_item(200_000), session_id="s3")
        assert result.approved is False
        assert "exceed max cart value" in result.reason

    def test_approves_item_exactly_at_max_cart_value(self):
        existing_cart = [_item(500_000, name="Existing")]
        result = evaluate_add_to_cart(cart=existing_cart, candidate=_item(500_000), session_id="s4")
        assert result.approved is True

    def test_denies_after_rate_limit_exceeded(self):
        session_id = "s5"
        # default rate limit = 5 actions / 60s window
        for _ in range(5):
            result = evaluate_add_to_cart(cart=[], candidate=_item(1000), session_id=session_id)
            assert result.approved is True
        sixth = evaluate_add_to_cart(cart=[], candidate=_item(1000), session_id=session_id)
        assert sixth.approved is False
        assert "rate limit" in sixth.reason.lower()

    def test_bounds_checked_reported_for_transparency(self):
        result = evaluate_add_to_cart(cart=[], candidate=_item(1000), session_id="s6")
        assert "max_single_item_price_paise" in result.bounds_checked
        assert "max_cart_value_paise" in result.bounds_checked


class TestCheckoutBounds:
    def test_approves_checkout_within_bounds(self):
        result = evaluate_checkout(
            cart=[_item(100_000)], session_id="c1", already_captured_order_ids=[]
        )
        assert result.approved is True

    def test_denies_checkout_on_empty_cart(self):
        result = evaluate_checkout(cart=[], session_id="c2", already_captured_order_ids=[])
        assert result.approved is False
        assert "empty" in result.reason.lower()

    def test_denies_checkout_over_max_cart_value(self):
        result = evaluate_checkout(
            cart=[_item(1_100_000)], session_id="c3", already_captured_order_ids=[]
        )
        assert result.approved is False
        assert "exceeds max cart value" in result.reason

    def test_denies_duplicate_charge_on_already_captured_order(self):
        result = evaluate_checkout(
            cart=[_item(100_000)],
            session_id="c4",
            already_captured_order_ids=["order_123"],
            target_order_id="order_123",
        )
        assert result.approved is False
        assert "duplicate-charge guard" in result.reason.lower()

    def test_allows_checkout_against_a_different_order_id(self):
        result = evaluate_checkout(
            cart=[_item(100_000)],
            session_id="c5",
            already_captured_order_ids=["order_123"],
            target_order_id="order_456",
        )
        assert result.approved is True

    def test_denies_checkout_when_session_already_completed(self):
        """Regression: this is the guard that actually engages in the live
        API flow (POST /session/{id}/checkout carries no target_order_id
        ahead of time) — without it, calling checkout again after a
        successful payment would create and could pay for a second order
        against the same cart.
        """
        result = evaluate_checkout(
            cart=[_item(100_000)],
            session_id="c6",
            already_captured_order_ids=["order_999"],
            session_status="completed",
        )
        assert result.approved is False
        assert "already has a captured payment" in result.reason.lower()

    def test_denies_second_checkout_while_a_payment_is_in_progress(self):
        result = evaluate_checkout(
            cart=[_item(100_000)],
            session_id="c7",
            already_captured_order_ids=[],
            session_status="awaiting_payment",
        )
        assert result.approved is False
        assert "already in progress" in result.reason.lower()


class TestRetryBounds:
    def test_approves_retry_within_max_attempts(self):
        result = evaluate_retry(attempt_no=1, session_id="r1")
        assert result.approved is True
        result2 = evaluate_retry(attempt_no=2, session_id="r1")
        assert result2.approved is True

    def test_denies_retry_beyond_max_attempts(self):
        # default max retry attempts = 2
        result = evaluate_retry(attempt_no=3, session_id="r2")
        assert result.approved is False
        assert "exceeds max retry attempts" in result.reason
