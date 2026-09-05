import { useState } from "react";
import { AuditTrailView } from "./components/AuditTrailView";
import { CartPanel } from "./components/CartPanel";
import { OptionsPanel } from "./components/OptionsPanel";
import { PolicyLog } from "./components/PolicyLog";
import { UpsellCard } from "./components/UpsellCard";
import { api, formatPaise, type SessionState } from "./api/client";

type ChatMessage = { role: "user" | "agent"; text: string };

export default function App() {
  const [tab, setTab] = useState<"shop" | "audit">("shop");
  const [goalInput, setGoalInput] = useState("");
  const [session, setSession] = useState<SessionState | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [payMessage, setPayMessage] = useState<string | null>(null);

  const addAgentMessage = (text: string) => setMessages((m) => [...m, { role: "agent", text }]);

  const handleStart = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!goalInput.trim() || busy) return;
    const goal = goalInput.trim();
    setMessages((m) => [...m, { role: "user", text: goal }]);
    setGoalInput("");
    setBusy(true);
    setPayMessage(null);
    try {
      const result = await api.startSession(goal);
      setSession(result);
      if (result.proposed_options.length > 0) {
        addAgentMessage(
          `Found ${result.catalog_snapshot.length} matching product(s) — here are ${result.proposed_options.length} options across the price range. Pick one below ↓`
        );
      } else if (result.status === "no_match") {
        addAgentMessage("No products matched that goal — try a different budget or category.");
      }
    } catch (err) {
      addAgentMessage(`Error: ${(err as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const handleSelectOption = async (productId: string) => {
    if (!session) return;
    setBusy(true);
    try {
      const result = await api.selectOption(session.session_id, productId);
      setSession(result);
      const lastDecision = result.policy_decisions.at(-1);
      const item = result.cart.at(-1);
      if (item && lastDecision?.approved) {
        addAgentMessage(
          `Added "${item.name}" (${formatPaise(item.unit_price_paise)}) to your cart. Policy Agent approved: ${lastDecision.reason}`
        );
      } else if (lastDecision && !lastDecision.approved) {
        addAgentMessage(`Policy Agent denied this: ${lastDecision.reason}`);
      }
      if (result.upsell_suggestions.length > 0) {
        addAgentMessage("Upsell Agent has a suggestion for you below ↓");
      }
    } catch (err) {
      addAgentMessage(`Error: ${(err as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const handleUpsellResponse = async (productId: string, accepted: boolean) => {
    if (!session) return;
    setBusy(true);
    try {
      const result = await api.respondUpsell(session.session_id, productId, accepted);
      setSession(result);
      const lastDecision = result.policy_decisions.at(-1);
      if (accepted && lastDecision) {
        addAgentMessage(
          lastDecision.approved
            ? `Added to cart. Policy Agent approved: ${lastDecision.reason}`
            : `Policy Agent denied adding this add-on: ${lastDecision.reason}`
        );
      } else if (!accepted) {
        addAgentMessage("No problem — skipping the add-on.");
      }
    } finally {
      setBusy(false);
    }
  };

  const openRazorpayCheckout = (
    orderId: string,
    amountPaise: number,
    keyId: string,
    sessionId: string
  ) => {
    const rzp = new window.Razorpay({
      key: keyId,
      amount: amountPaise,
      currency: "INR",
      name: "AgentCommerce Merchant (TEST MODE)",
      description: "AI Shopping Agent checkout",
      order_id: orderId,
      theme: { color: "#e8a33d" },
      handler: async (response: any) => {
        setPayMessage("Verifying payment signature…");
        try {
          const result = await api.paymentSuccess(sessionId, {
            razorpay_order_id: response.razorpay_order_id,
            razorpay_payment_id: response.razorpay_payment_id,
            razorpay_signature: response.razorpay_signature,
          });
          setSession(result);
          setPayMessage("✅ Payment captured. Order complete.");
          addAgentMessage("Checkout Agent verified the signature and captured the payment. Order complete.");
        } catch (err) {
          setPayMessage(`Error verifying payment: ${(err as Error).message}`);
        }
      },
    });
    rzp.on("payment.failed", async (response: any) => {
      const reason = response?.error?.description ?? "Payment declined by bank.";
      setPayMessage(`❌ Payment declined: ${reason}. Policy Agent is evaluating a retry…`);
      addAgentMessage(`Checkout declined: ${reason}`);
      const retry = await api.paymentFailed(sessionId, orderId, reason);
      setSession(retry.state);
      if (retry.status === "awaiting_payment" && retry.order_id) {
        addAgentMessage(
          `Policy Agent approved a retry (within max attempts). Created a new order — reopening checkout.`
        );
        openRazorpayCheckout(retry.order_id, retry.amount_paise!, retry.razorpay_key_id!, sessionId);
      } else {
        addAgentMessage(`Retry not approved: ${retry.error ?? "max retry attempts reached."}`);
        setPayMessage(`Checkout stopped: ${retry.error ?? "max retry attempts reached."}`);
      }
    });
    rzp.open();
  };

  const handleCheckout = async () => {
    if (!session) return;
    setBusy(true);
    setPayMessage(null);
    try {
      const result = await api.checkout(session.session_id);
      setSession(result.state);
      if (result.status === "awaiting_payment" && result.order_id) {
        addAgentMessage(
          `Policy Agent approved checkout for ${formatPaise(result.amount_paise!)}. Opening Razorpay test checkout…`
        );
        openRazorpayCheckout(result.order_id, result.amount_paise!, result.razorpay_key_id!, session.session_id);
      } else {
        addAgentMessage(`Checkout blocked: ${result.error ?? "unknown reason"}`);
      }
    } catch (err) {
      addAgentMessage(`Checkout error: ${(err as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const canCheckout =
    session &&
    session.cart.length > 0 &&
    session.status !== "completed" &&
    (session.status === "ready_for_checkout" || session.status === "awaiting_upsell_response");

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand">
          <span className="brand-dot" />
          AgentCommerce
        </div>
        <div className="tabs">
          <button className={`tab-btn ${tab === "shop" ? "active" : ""}`} onClick={() => setTab("shop")}>
            Shop
          </button>
          <button className={`tab-btn ${tab === "audit" ? "active" : ""}`} onClick={() => setTab("audit")}>
            Audit trail
          </button>
        </div>
        <div className="dim" style={{ fontSize: 12 }}>Razorpay TEST MODE</div>
      </header>

      {tab === "shop" ? (
        <div className="main-grid">
          <section className="panel">
            <div className="panel-header rule-teal">Shopping agent</div>
            <div className="panel-body chat-scroll">
              {messages.length === 0 && (
                <div className="empty-state">
                  Try: "I need a laptop bag under ₹1500"
                </div>
              )}
              {messages.map((m, i) => (
                <div className={`msg ${m.role}`} key={i}>
                  {m.text}
                </div>
              ))}
              {session?.status === "awaiting_option_selection" && (
                <OptionsPanel options={session.proposed_options} onSelect={handleSelectOption} disabled={busy} />
              )}
              {session?.upsell_suggestions.map((s) => (
                <UpsellCard
                  key={s.product_id}
                  suggestion={s}
                  product={session.catalog_snapshot.find((p) => p.id === s.product_id)}
                  onRespond={handleUpsellResponse}
                />
              ))}
              {payMessage && <div className="msg agent">{payMessage}</div>}
            </div>
            <form className="goal-form" onSubmit={handleStart}>
              <input
                placeholder="What are you shopping for?"
                value={goalInput}
                onChange={(e) => setGoalInput(e.target.value)}
                disabled={busy}
              />
              <button className="btn primary" type="submit" disabled={busy || !goalInput.trim()}>
                Send
              </button>
            </form>
          </section>

          <div style={{ display: "flex", flexDirection: "column", gap: 16, overflow: "hidden" }}>
            <section className="panel" style={{ flex: "0 0 auto", maxHeight: "40%" }}>
              <div className="panel-header rule-teal">Cart</div>
              <div className="panel-body">
                <CartPanel cart={session?.cart ?? []} />
                <button
                  className="btn primary"
                  style={{ width: "100%", marginTop: 8 }}
                  disabled={!canCheckout || busy}
                  onClick={handleCheckout}
                >
                  {busy ? "Working…" : "Checkout with Razorpay (Test Mode)"}
                </button>
              </div>
            </section>
            <section className="panel" style={{ flex: 1, minHeight: 0 }}>
              <div className="panel-header rule-purple">Policy gate log</div>
              <div className="panel-body">
                <PolicyLog decisions={session?.policy_decisions ?? []} />
              </div>
            </section>
          </div>
        </div>
      ) : (
        <div className="main-grid" style={{ gridTemplateColumns: "1fr" }}>
          <section className="panel">
            <div className="panel-header rule-purple">Audit trail</div>
            <div className="panel-body">
              <AuditTrailView sessionId={session?.session_id ?? null} />
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
