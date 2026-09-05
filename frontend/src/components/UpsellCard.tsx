import { formatPaise, type Product, type UpsellSuggestion } from "../api/client";

export function UpsellCard({
  suggestion,
  product,
  onRespond,
}: {
  suggestion: UpsellSuggestion;
  product: Product | undefined;
  onRespond: (productId: string, accepted: boolean) => void;
}) {
  if (suggestion.accepted !== null) {
    return (
      <div className="upsell-card">
        <span className={`badge ${suggestion.accepted ? "approved" : "denied"}`}>
          {suggestion.accepted ? "✓ Added" : "Skipped"}
        </span>{" "}
        {suggestion.name}
      </div>
    );
  }
  return (
    <div className="upsell-card">
      <div style={{ fontWeight: 600, marginBottom: 4 }}>✨ Upsell Agent suggests: {suggestion.name}</div>
      <div className="dim" style={{ fontSize: 12.5 }}>{suggestion.reason}</div>
      {product && (
        <div className="dim" style={{ fontSize: 12.5, marginTop: 4 }}>
          {formatPaise(product.price_paise)}
        </div>
      )}
      <div className="upsell-actions">
        <button className="btn primary small" onClick={() => onRespond(suggestion.product_id, true)}>
          Add to cart
        </button>
        <button className="btn ghost small" onClick={() => onRespond(suggestion.product_id, false)}>
          No thanks
        </button>
      </div>
    </div>
  );
}
