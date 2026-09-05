"""Thin wrapper over the official razorpay-python SDK.

API shapes below are confirmed against Razorpay's own SDK docs
(razorpay/razorpay-python: documents/order.md, payment.md, paymentVerfication.md),
not guessed. Test-mode card numbers and the success/failure mock-bank-page
mechanism are confirmed against razorpay/markdown-docs
(payments/payments/test-card-details.md): in test mode, entering a 4-10
digit OTP at the mock bank page simulates success; an OTP under 4 digits
simulates a decline. Direct fetches to razorpay.com itself were blocked by
this environment's egress proxy, so these were verified via Razorpay's
own GitHub-hosted SDK/doc mirrors instead.
"""

import hashlib
import hmac

import razorpay

from app.config import settings

_client: razorpay.Client | None = None


def get_client() -> razorpay.Client:
    global _client
    if _client is None:
        _client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))
    return _client


def create_order(amount_paise: int, receipt: str, notes: dict | None = None) -> dict:
    """Creates a Razorpay order. amount_paise must be the smallest currency unit."""
    return get_client().order.create(
        {
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt,
            "payment_capture": 1,
            "notes": notes or {},
        }
    )


def fetch_payment(payment_id: str) -> dict:
    return get_client().payment.fetch(payment_id)


def capture_payment(payment_id: str, amount_paise: int) -> dict:
    return get_client().payment.capture(payment_id, {"amount": amount_paise, "currency": "INR"})


def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """Verifies the HMAC-SHA256 signature Razorpay Checkout returns after payment.

    Mirrors client.utility.verify_payment_signature but returns a bool instead
    of raising, so the caller can log a structured audit event either way.
    """
    try:
        get_client().utility.verify_payment_signature(
            {
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature,
            }
        )
        return True
    except razorpay.errors.SignatureVerificationError:
        return False


def verify_webhook_signature(payload_body: bytes, signature: str, webhook_secret: str) -> bool:
    """Verifies an inbound Razorpay webhook's X-Razorpay-Signature header.

    Uses the same HMAC-SHA256(payload, secret) scheme Razorpay documents for
    webhooks (distinct secret from the API key pair).
    """
    expected = hmac.new(webhook_secret.encode(), payload_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
