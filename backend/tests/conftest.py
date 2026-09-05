import atexit
import os
import tempfile

# Ensure app.config.Settings can construct even in a fresh checkout with no
# .env yet — tests should never depend on real Razorpay credentials being
# present (test_checkout_flow.py mocks the Razorpay client directly).
os.environ.setdefault("RAZORPAY_KEY_ID", "rzp_test_dummy")
os.environ.setdefault("RAZORPAY_KEY_SECRET", "dummy_secret")

# A fresh file per test *process*, not a fixed shared path: tests use
# hardcoded session ids (e.g. "audit-1"), so reusing one persistent file
# across separate pytest invocations accumulates rows from prior runs and
# makes exact-count/order assertions fail nondeterministically.
_fd, _audit_db_path = tempfile.mkstemp(prefix="agentcommerce_test_audit_", suffix=".db")
os.close(_fd)
os.environ["AUDIT_DB_PATH"] = _audit_db_path
atexit.register(lambda: os.path.exists(_audit_db_path) and os.remove(_audit_db_path))
