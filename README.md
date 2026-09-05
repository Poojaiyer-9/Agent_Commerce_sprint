# AgentCommerce

[![CI](https://github.com/Poojaiyer-9/AgentCommerce/actions/workflows/ci.yml/badge.svg)](https://github.com/Poojaiyer-9/AgentCommerce/actions/workflows/ci.yml)

An agent-readable merchant catalog + a conversational AI shopping agent that
browses, negotiates within hard bounds, and completes a purchase end-to-end
on **Razorpay TEST-MODE** APIs — with a Policy/Guardrail Agent gating every
money-relevant action, a full queryable audit trail, and a graceful
decline → retry → success path. Built for the Razorpay AI Buildathon,
Track 1: AI Growth & Agentic Commerce.

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the agent graph, guardrail
logic, and why this satisfies "explainable, bounded, gated."

## Stack

- **Backend**: Python, FastAPI, LangGraph, `razorpay` (official SDK), SQLite.
- **Frontend**: React + Vite + TypeScript, Razorpay Checkout.js (test mode).

## 1. Setup

### Backend

Requires **Python 3.11 or 3.12**. (Newer versions — 3.13/3.14 — may not yet
have prebuilt wheels for `pydantic-core` on every platform, which forces pip
to compile it from source and fail without a C/Rust toolchain installed. If
`python3 --version`/`py -0` shows only a newer version, install 3.11 or 3.12
alongside it rather than fighting the build.)

macOS/Linux:
```bash
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env: set RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET to your own TEST keys
#   (dashboard.razorpay.com → Settings → API Keys → Generate Test Key)

python -m seed.seed_catalog     # writes backend/seed/catalog.json (12 products)
pytest -q                       # 27 tests: policy bounds, checkout flow, audit trail
uvicorn app.main:app --reload --port 8000
```

Windows (PowerShell):
```powershell
cd backend
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1      # if blocked: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
pip install -r requirements.txt
copy .env.example .env
notepad .env                    # set RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET

python -m seed.seed_catalog
pytest -q
uvicorn app.main:app --reload --port 8000
```

`ANTHROPIC_API_KEY` in `.env` is optional — the Shopping/Upsell agents use
deterministic rule-based reasoning by default, so the demo is reproducible
without any LLM key.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env   # VITE_API_BASE_URL=http://localhost:8000 (default is fine)
npm run dev             # http://localhost:5173
```

Both servers run locally — there's no external hosting required to use or
demo this project.

## 2. Scripted demo path (~5 minutes)

### (a) Happy path — browse → cart → policy approval → successful payment

1. Open `http://localhost:5173`.
2. Type: **"I need a laptop bag under ₹1500"** and hit Send.
   - Catalog Agent matches 3 bags under ₹1500; Shopping Agent triages them
     into 3 tiered options — **Most Affordable** ("Compact Commuter Bag",
     ₹999), **Best Value** ("Classic Black Laptop Bag", ₹1299), and
     **Premium Pick** ("Canvas Messenger Bag", ₹1499) — shown as cards to
     choose from, not a single silent pick.
   - Click **Choose this** on any option — Policy Agent approves it (shown
     as a green badge with the exact rule it checked), then Upsell Agent
     suggests a relevant add-on — click **Add to cart** (Policy Agent
     gates this too, same as any cart addition).
3. Click **Checkout with Razorpay (Test Mode)**.
   - Policy Agent re-checks the final cart total before Razorpay's Orders
     API is even called.
   - Razorpay's Checkout.js widget opens. Card number `4100 2800 0000 1007`
     (any future expiry, any CVV) → Pay.
   - At the mock bank page, enter an OTP with **4+ digits** (e.g. `1234`)
     → **Success**.
   - The backend verifies the signature, captures the payment, and the UI
     shows "Order complete."
4. Switch to the **Audit Trail** tab — the full sequence (catalog query →
   shopping proposal → 2× policy approvals → upsell suggestion → checkout
   approval → order created → signature verified → payment captured) is
   listed with timestamps and reasons.

### (b) Failure path — triggered decline → graceful retry → success

1. Start a new goal, e.g. **"I need a travel backpack"**, and get to
   checkout the same way.
2. In the Razorpay test checkout, use the same test card, but at the mock
   bank OTP page enter an OTP with **fewer than 4 digits** (e.g. `1`) →
   this simulates a decline (confirmed Razorpay test-mode behavior, see
   `ARCHITECTURE.md` §5 — not a random flaky failure).
3. The UI shows the decline reason, then: "Policy Agent approved a retry
   (within max attempts). Created a new order — reopening checkout."
   The Razorpay widget reopens automatically against a **new** order.
4. This time enter a valid OTP (`1234`) → Success. Payment captures.
5. Check the Audit Trail tab: the decline, the retry policy check (with
   `attempt_no` and the max-retry bound it was checked against), the new
   order creation, and the eventual success are all present as distinct,
   explained events — nothing was silently retried or lost.

To also show the *bound being hit* (not just a successful retry), lower
`POLICY_MAX_RETRY_ATTEMPTS=0` in `backend/.env`, restart uvicorn, and
repeat the decline once — the UI will show "Retry not approved: retry
attempt 1 exceeds max retry attempts (0)" instead of reopening checkout.
Set it back to `2` afterwards.

## 3. CLI audit trail viewer

Without the frontend, from `backend/`:

```bash
python -c "from app.audit.viewer import render_human_readable; print(render_human_readable('<session_id>'))"
```

`session_id` is printed at the top of every `/session/start` response and
shown in the Audit Trail tab.

## 4. API surface (backend/app/main.py)

| Method & path | Purpose |
|---|---|
| `GET /catalog` | Full agent-readable product catalog |
| `POST /session/start` | `{user_goal}` → runs the browse graph (catalog → shopping), returns up to 3 tiered options (Most Affordable / Best Value / Premium Pick) |
| `GET /session/{id}` | Current session state |
| `POST /session/{id}/select-option` | `{product_id}` → policy-gated add of the chosen tiered option, then runs the Upsell Agent |
| `POST /session/{id}/upsell-response` | `{product_id, accepted}` → policy-gated add if accepted |
| `POST /session/{id}/checkout` | Policy-gates and creates a Razorpay order |
| `POST /session/{id}/payment/success` | `{razorpay_order_id, razorpay_payment_id, razorpay_signature}` → verify + capture |
| `POST /session/{id}/payment/failed` | `{order_id, reason}` → logs decline, runs policy-gated retry graph |
| `GET /session/{id}/audit` | Structured audit events for the session |
| `GET /session/{id}/audit/text` | Human-readable narrated audit trail |

## 5. Guardrail bounds (backend/.env, all overridable)

| Var | Default | Meaning |
|---|---|---|
| `POLICY_MAX_SINGLE_ITEM_PRICE_PAISE` | 500000 (₹5000) | Max price for one line item |
| `POLICY_MAX_CART_VALUE_PAISE` | 1000000 (₹10000) | Max total cart value |
| `POLICY_MAX_RETRY_ATTEMPTS` | 2 | Max payment retries after a decline |
| `POLICY_RATE_LIMIT_ACTIONS` / `..._WINDOW_SECONDS` | 5 / 60 | Max gated actions per session per window |

## 6. Tests

```bash
cd backend && pytest -q
```

`tests/test_policy_agent.py` exercises the Policy Agent's bounding logic
directly (approve within bounds, deny over item/cart caps, deny past the
rate limit, deny duplicate charges, deny past max retries — both sides of
every rule, not just the happy path). `tests/test_checkout_flow.py` mocks
the Razorpay client to test order creation, signature verification
(valid and tampered), the decline → retry → new-order path, and the
duplicate-charge guard. `tests/test_audit_trail.py` covers event
persistence and the human-readable renderer.

CI runs this suite plus a frontend type-check/build on every push — see
the badge above.

## Repo layout

```
backend/app/graph/          # LangGraph state + node functions + graph wiring
backend/app/policy/rules.py # Policy/Guardrail Agent — all bounds in one place
backend/app/audit/          # SQLite audit log + human-readable viewer
backend/app/razorpay_client.py
backend/seed/seed_catalog.py
backend/tests/
frontend/src/components/    # ChatPanel-equivalent, CartPanel, PolicyLog, UpsellCard, AuditTrailView
ARCHITECTURE.md
```
