# AgentCommerce — Architecture

Built for Razorpay AI Buildathon, Track 1: AI Growth & Agentic Commerce.

## 1. Agent graph (LangGraph)

Three compiled `StateGraph`s over one typed `AgentState` (`backend/app/graph/state.py`),
plus small directly-called node functions for steps that depend on an
external event — either a client-side UI action (the user picking one of
the Shopping Agent's proposed options, or accepting an upsell) or the
Razorpay Checkout.js payment result.

```
Browse graph (one user goal → up to 3 tiered options, nothing added yet)
───────────────────────────────────────────────────
catalog_agent → shopping_agent → END

  shopping_agent triages the matched catalog into up to 3 options —
  Most Affordable / Best Value / Premium Pick — by price within the
  match set. Nothing is added to the cart here, so there is no policy
  gate in this graph; the gate happens once the user picks one, via
  POST /session/{id}/select-option, which calls policy_agent_add_to_cart_node
  directly (same pattern as accepting an upsell suggestion) — money-
  relevant state never changes on this path without going through it.

Checkout graph (invoked on "proceed to checkout")
───────────────────────────────────────────────────
policy_agent(checkout) ──approved──→ create_order ──→ END
        │
       denied ──→ END

Retry graph (invoked on a declined payment.failed event from Checkout.js)
───────────────────────────────────────────────────
policy_agent(retry) ──approved──→ create_order (new order) ──→ END
        │
       denied (max attempts) ──→ END, graceful stop
```

`capture_payment` / `verify_payment_signature` are called directly (not as
graph nodes) from `POST /session/{id}/payment/success`, because they only
run once the browser has completed Razorpay's Checkout.js flow and handed
back `razorpay_payment_id` + `razorpay_signature` — there's no agent
reasoning at that step, just a deterministic verify-then-capture, so it's
logged to the audit trail the same way but doesn't need graph orchestration.

### Why three separate graphs instead of one long one?

Each boundary here is a real pause for an external event LangGraph doesn't
control: the browse phase ends the moment options are proposed, because
only the user — clicking a card in the browser — can decide which one to
buy; the checkout/payment phase (gate → create order → wait for a real
card entry in the browser → capture) is separated from that by the same
kind of pause, plus a real network round-trip through Razorpay's hosted
Checkout.js widget. LangGraph graphs run to completion in one `invoke()`
call; they aren't a natural fit for "pause until a human clicks something
in a browser," so each boundary is expressed as a graph edge into `END`
plus a thin FastAPI layer holding session state between them (`policy_agent_add_to_cart_node`
and `upsell_agent_node` are called directly, not wrapped in a graph, for
exactly this reason — see `POST /select-option` and `POST /upsell-response`
in `backend/app/main.py`), rather than forcing an `interrupt()` around UI
events LangGraph doesn't control.

## 2. State schema

`AgentState` (TypedDict) carries `session_id`, `user_goal`,
`catalog_snapshot`, `proposed_options`, `cart`, `candidate_item`,
`policy_decisions`, `payment_attempts`, `upsell_suggestions`,
`captured_order_ids`, `retry_count`, `status`, `error`, `reasoning_trace`.
List fields use a custom `_append` reducer so each graph invocation
accumulates onto prior history instead of overwriting it — the same state
doubles as the in-memory session record returned to the frontend.

## 3. The Policy/Guardrail Agent — what makes this "bounded and gated"

`backend/app/policy/rules.py` is the single place all money-relevant
bounds are defined and checked. Every action goes through it before it
takes effect — the browse graph has no path that touches `cart` at all
(it only proposes `proposed_options`), and the only way an option or an
upsell add-on reaches the cart is through `policy_agent_add_to_cart_node`,
called directly from `/select-option` and `/upsell-response` respectively.
The checkout graph cannot call Razorpay's Orders API without first passing
through `policy_agent_checkout_node` either — this is a hard structural
property of the code (there is no function that appends to `cart` or
calls `create_order` without going through the corresponding
`policy_agent_*` call first), not a convention:

| Rule | Enforced by | Rationale |
|---|---|---|
| Max single-item price | `evaluate_add_to_cart` | Caps blast radius of one bad catalog match |
| Max cart value | `evaluate_add_to_cart`, `evaluate_checkout` | Caps blast radius of the whole session, checked twice (add-time and checkout-time, since upsells change the total) |
| Rate limit (N gated actions / window) | `evaluate_add_to_cart` | Stops runaway agent loops from hammering the catalog/cart |
| Duplicate-charge guard | `evaluate_checkout` | Refuses to checkout against an `order_id` already in `captured_order_ids` |
| Max retry attempts | `evaluate_retry` | Bounds how many times a declined payment can be retried before the agent must stop and report failure, rather than looping forever |

Every `PolicyResult` carries `approved`, a human-readable `reason` string
naming the exact rule and numbers involved, and `bounds_checked` (the
config values it evaluated against) — this is what the frontend renders as
"Policy Agent approved/denied this because X" and what
`tests/test_policy_agent.py` asserts against directly (approve-in-bounds,
deny-over-item-cap, deny-over-cart-cap, deny-rate-limited,
deny-duplicate-charge, deny-empty-cart, deny-over-max-retries — see that
file for the full list). Bounds are all read from `.env` via
`app/config.py`, never hardcoded inline in a node.

## 4. Audit trail — what makes this "explainable"

Every node that changes state or makes a decision calls
`app.audit.logger.log_event(session_id, agent, action, decision, reason,
state_before, state_after, extra)`, persisted to SQLite
(`app/audit/models.py`). This includes non-money steps (catalog query,
upsell suggestion) alongside every policy check and payment attempt, so
the full session — not just the money-moving parts — is reconstructable.

`app.audit.viewer` exposes this two ways:
- `GET /session/{id}/audit` — structured JSON, used by the frontend's
  Audit Trail tab (`frontend/src/components/AuditTrailView.tsx`), rendered
  as a table of timestamp / agent / action / decision / reason.
- `render_human_readable(session_id)` — a narrated plain-text version of
  the same events, for a CLI/terminal walkthrough
  (`python -m app.audit.viewer` equivalent, see README).

## 5. Failure handling — the graceful-decline path

Razorpay's test mode does not use a "magic decline card number"; instead,
at the mock bank OTP page, a 4–10 digit OTP simulates success and an OTP
under 4 digits simulates a decline (confirmed against Razorpay's own
`markdown-docs` GitHub mirror — `payments/payments/test-card-details.md` —
since direct fetches to razorpay.com were blocked by this build
environment's network policy). This makes the failure path a deterministic
UI action for the demo, not a flaky "sometimes declines" card.

When Checkout.js's `payment.failed` handler fires, the frontend calls
`POST /session/{id}/payment/failed`, which:
1. Logs the decline (`checkout_agent.payment_declined`) with the reason
   Razorpay returned.
2. Runs the retry graph: `policy_agent_retry` re-checks the attempt count
   against `POLICY_MAX_RETRY_ATTEMPTS`.
3. If approved, `create_order_node` creates a **fresh** Razorpay order
   (not a resubmission of the same one — required by Razorpay, and
   double-checked by the duplicate-charge guard) and the frontend reopens
   Checkout.js against it.
4. If the retry cap is hit, the graph ends in `retry_denied` with the
   reason surfaced to the user — no crash, no silent loop, cart and audit
   history both intact.

## 6. Why this satisfies "explainable, bounded, gated"

- **Explainable**: every decision (not just approvals) carries a
  human-readable reason and is queryable per-session, both as raw JSON and
  as narrated text.
- **Bounded**: hard numeric ceilings (item price, cart value, retry count,
  rate limit) live in one module, are structurally unavoidable in the
  graph wiring, and are unit-tested directly against both the approve and
  the deny side of each rule.
- **Gated**: no code path adds to the cart or calls Razorpay's Orders API
  without first passing through a `policy_agent_*` node whose `approved`
  flag the graph's conditional edge inspects — approval is not
  advisory, it's what the conditional edge branches on.

## 7. Known limitation of this build session

This build ran in a sandboxed environment whose network egress proxy
blocks `api.razorpay.com` (and `razorpay.com` docs) directly — confirmed
via the proxy's own status endpoint, not assumed. Razorpay API shapes
(`order.create`, `payment.capture`, `payment.fetch`,
`utility.verify_payment_signature`) and test-card/OTP behavior were
confirmed against Razorpay's own GitHub-hosted SDK and docs mirrors
(`razorpay/razorpay-python`, `razorpay/markdown-docs`) rather than guessed.
The checkout error path was exercised for real against this exact
network block (a real `ConnectionError` was caught, logged, and returned
as a clean `failed` status with no crash) — but a live create-order /
capture / verify round-trip against Razorpay's actual test API has not
been run inside this session. Run it once locally against your own test
keys before recording the demo video (see README "Before you record").
