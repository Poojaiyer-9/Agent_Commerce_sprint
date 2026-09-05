import { formatPaise, type ProposedOption } from "../api/client";

type TierLook = {
  icon: string;
  accent: string;
  border: string;
  background: string;
};

const TIER_LOOK: Record<ProposedOption["tier"], TierLook> = {
  // Budget tier: bare ledger stock — flat, hairline rule, no fill at all.
  most_affordable: {
    icon: "💰",
    accent: "var(--paper-dim)",
    border: "1px solid var(--rule)",
    background: "transparent",
  },
  // Best value: filled stock with an amber top rule — the recommended pick
  // gets material weight, not just a different outline.
  best_value: {
    icon: "⭐",
    accent: "var(--amber)",
    border: "1px solid var(--amber)",
    background:
      "linear-gradient(180deg, var(--amber-wash), var(--ink-2) 45%), linear-gradient(var(--ink-2), var(--ink-2))",
  },
  // Premium: heavy cardstock — a double-rule frame (light outer, dark inner)
  // like the engraved border on a certificate.
  premium_pick: {
    icon: "💎",
    accent: "var(--paper)",
    border: "1px solid transparent",
    background:
      "linear-gradient(var(--ink-2), var(--ink-2)) padding-box, linear-gradient(160deg, var(--paper-dim), var(--rule-strong) 60%) border-box",
  },
};

export function OptionsPanel({
  options,
  onSelect,
  disabled,
}: {
  options: ProposedOption[];
  onSelect: (productId: string) => void;
  disabled?: boolean;
}) {
  if (options.length === 0) return null;

  return (
    <div style={{ display: "grid", gridTemplateColumns: `repeat(${options.length}, 1fr)`, gap: 10 }}>
      {options.map((o) => {
        const look = TIER_LOOK[o.tier];
        return (
          <div
            key={o.product_id}
            className="card interactive option-card"
            style={{
              border: look.border,
              background: look.background,
              display: "flex",
              flexDirection: "column",
              gap: 8,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span>{look.icon}</span>
              <span style={{ fontSize: 12, fontWeight: 700, color: look.accent }}>{o.tier_label}</span>
            </div>
            <div style={{ fontWeight: 600, fontSize: 13.5 }}>{o.name}</div>
            <div className="mono" style={{ fontSize: 15, fontWeight: 700 }}>{formatPaise(o.unit_price_paise)}</div>
            <div className="dim" style={{ fontSize: 12, flex: 1 }}>{o.reason}</div>
            <button
              className="btn primary small"
              style={{ width: "100%" }}
              disabled={disabled}
              onClick={() => onSelect(o.product_id)}
            >
              Choose option
            </button>
          </div>
        );
      })}
    </div>
  );
}
