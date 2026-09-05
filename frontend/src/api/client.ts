const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export type CartItem = {
  product_id: string;
  name: string;
  unit_price_paise: number;
  qty: number;
};

export type PolicyDecision = {
  agent: string;
  action: string;
  approved: boolean;
  reason: string;
  bounds_checked: Record<string, number | boolean>;
  timestamp: string;
};

export type PaymentAttempt = {
  attempt_no: number;
  order_id: string | null;
  payment_id: string | null;
  status: string;
  failure_reason: string | null;
};

export type UpsellSuggestion = {
  product_id: string;
  name: string;
  reason: string;
  accepted: boolean | null;
};

export type ProposedOption = {
  product_id: string;
  name: string;
  unit_price_paise: number;
  tier: "most_affordable" | "best_value" | "premium_pick";
  tier_label: string;
  reason: string;
};

export type SessionState = {
  session_id: string;
  user_goal: string;
  catalog_snapshot: Product[];
  proposed_options: ProposedOption[];
  cart: CartItem[];
  candidate_item: CartItem | null;
  policy_decisions: PolicyDecision[];
  payment_attempts: PaymentAttempt[];
  upsell_suggestions: UpsellSuggestion[];
  captured_order_ids: string[];
  retry_count: number;
  status: string;
  error: string | null;
  reasoning_trace: string[];
};

export type Product = {
  id: string;
  name: string;
  description: string;
  price_paise: number;
  currency: string;
  stock: number;
  category: string;
  attributes: Record<string, string>;
  upsell_ids: string[];
  image_url: string | null;
};

export type CheckoutResponse = {
  status: string;
  order_id?: string;
  amount_paise?: number;
  currency?: string;
  razorpay_key_id?: string;
  error?: string | null;
  state: SessionState;
};

export type AuditEvent = {
  id: number;
  session_id: string;
  timestamp: string;
  agent: string;
  action: string;
  decision: string;
  reason: string;
  state_before: unknown;
  state_after: unknown;
  extra: { bounds_checked?: Record<string, number | boolean> } | null;
};

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getCatalog: () => req<Product[]>("/catalog"),
  startSession: (userGoal: string) =>
    req<SessionState>("/session/start", { method: "POST", body: JSON.stringify({ user_goal: userGoal }) }),
  getSession: (sessionId: string) => req<SessionState>(`/session/${sessionId}`),
  selectOption: (sessionId: string, productId: string) =>
    req<SessionState>(`/session/${sessionId}/select-option`, {
      method: "POST",
      body: JSON.stringify({ product_id: productId }),
    }),
  respondUpsell: (sessionId: string, productId: string, accepted: boolean) =>
    req<SessionState>(`/session/${sessionId}/upsell-response`, {
      method: "POST",
      body: JSON.stringify({ product_id: productId, accepted }),
    }),
  checkout: (sessionId: string) =>
    req<CheckoutResponse>(`/session/${sessionId}/checkout`, { method: "POST" }),
  paymentSuccess: (
    sessionId: string,
    payload: { razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string }
  ) =>
    req<SessionState>(`/session/${sessionId}/payment/success`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  paymentFailed: (sessionId: string, orderId: string | null, reason: string) =>
    req<CheckoutResponse>(`/session/${sessionId}/payment/failed`, {
      method: "POST",
      body: JSON.stringify({ order_id: orderId, reason }),
    }),
  getAudit: (sessionId: string) => req<AuditEvent[]>(`/session/${sessionId}/audit`),
};

export function formatPaise(paise: number): string {
  return `₹${(paise / 100).toFixed(2)}`;
}
