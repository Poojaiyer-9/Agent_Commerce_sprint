import { formatPaise, type CartItem } from "../api/client";

export function CartPanel({ cart }: { cart: CartItem[] }) {
  const total = cart.reduce((sum, i) => sum + i.unit_price_paise * i.qty, 0);
  if (cart.length === 0) {
    return <div className="empty-state">Cart is empty.</div>;
  }
  return (
    <div className="card">
      {cart.map((item) => (
        <div className="cart-item" key={item.product_id}>
          <span>
            {item.name} {item.qty > 1 && <span className="dim">×{item.qty}</span>}
          </span>
          <span className="mono">{formatPaise(item.unit_price_paise * item.qty)}</span>
        </div>
      ))}
      <div className="cart-total">
        <span>Total</span>
        <span className="mono">{formatPaise(total)}</span>
      </div>
    </div>
  );
}
