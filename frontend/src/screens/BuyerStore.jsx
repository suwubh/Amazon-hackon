import TopBar from "../components/TopBar";
import Thumb from "../components/Thumb";
import { SLBadge, Spinner } from "../components/ui";
import { inr } from "../lib/format";

// Buyer storefront (Rahul) — MT9 web hub with four areas:
//  • Shop — catalog grid → PDP (fit proof = PREVENT)
//  • Cart — server-computed lines + total → UPI checkout
//  • Orders — real history; one-tap Resell → radar (RECIRCULATE)
//  • Notifications — the idle-monitor nudge → resell
// Every figure is API-backed (/items, /cart, /orders, /notifications).
const FIT_ASINS = new Set(["B0SHOE500", "B0KURTA01"]);

export default function BuyerStore({
  items, cart, cartLoading, orders, ordersLoading, notifications, notifLoading,
  busy, tab, onTab, onOpenPdp, onResell, onReturn, onReplace, onCheckout, onNotif, onBack,
  onFlash, onResells,
}) {
  const cartCount = cart?.count || 0;
  const orderCount = orders?.length || 0;

  return (
    <div className="screen-page">
      <TopBar title="Amazon" subtitle="Hello, Rahul — your storefront" onBack={onBack} right={<SLBadge />} />

      <div className="flex flex-wrap gap-1.5 mb-5">
        <Tab active={tab === "shop"} onClick={() => onTab("shop")}>Shop</Tab>
        <Tab active={tab === "cart"} onClick={() => onTab("cart")}>Cart{cartCount ? ` · ${cartCount}` : ""}</Tab>
        <Tab active={tab === "orders"} onClick={() => onTab("orders")}>Your orders{orderCount ? ` · ${orderCount}` : ""}</Tab>
        <Tab active={tab === "flash"} onClick={() => onTab("flash")}>Flash deals</Tab>
        <Tab active={tab === "resells"} onClick={() => onTab("resells")}>My resells</Tab>
        <Tab active={tab === "notifications"} onClick={() => onTab("notifications")}>Notifications</Tab>
      </div>

      {tab === "shop" && <Shop items={items} onOpenPdp={onOpenPdp} />}
      {tab === "cart" && <Cart cart={cart} loading={cartLoading} busy={busy} onCheckout={onCheckout} onShop={() => onTab("shop")} />}
      {tab === "orders" && <Orders orders={orders} loading={ordersLoading} busy={busy} onResell={onResell} onReturn={onReturn} onReplace={onReplace} />}
      {tab === "flash" && onFlash}
      {tab === "resells" && onResells}
      {tab === "notifications" && <Notifications list={notifications} loading={notifLoading} busy={busy} onNotif={onNotif} />}
    </div>
  );
}

function Tab({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 rounded-full text-[13px] font-700 transition ring-1 ${
        active ? "bg-az-navy text-white ring-az-navy" : "bg-white text-sl-muted ring-sl-line hover:ring-az-steel/40"
      }`}
    >
      {children}
    </button>
  );
}

function Shop({ items, onOpenPdp }) {
  return (
    <div className="anim-fade-up">
      <p className="text-[12px] font-700 uppercase tracking-wider text-sl-muted mb-3">Recommended for you</p>
      <div className="grid gap-3 grid-cols-2 sm:grid-cols-3 lg:grid-cols-4">
        {items.map((it, i) => (
          <button
            key={it.item_id}
            onClick={() => onOpenPdp(it)}
            className="group text-left rounded-2xl bg-white ring-1 ring-sl-line shadow-card p-3 transition hover:ring-sl-green/60 hover:shadow-pop hover:-translate-y-0.5"
            style={{ animationDelay: `${i * 30}ms` }}
          >
            <Thumb src={it.thumb} alt={it.title} category={it.category} className="w-full aspect-square rounded-xl" />
            <h3 className="mt-2.5 font-600 text-[12.5px] leading-tight text-sl-ink line-clamp-2 min-h-[34px]">{it.title}</h3>
            <div className="mt-1 flex items-center justify-between">
              <span className="font-display font-800 text-[16px] tnum text-sl-ink">{inr(it.mrp)}</span>
              {FIT_ASINS.has(it.asin) && (
                <span className="rounded-full bg-sl-mint text-sl-green-deep text-[8.5px] font-800 px-1.5 py-0.5 tracking-wide">FIT PROOF</span>
              )}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

function Cart({ cart, loading, busy, onCheckout, onShop }) {
  if (loading) return <Center><Spinner /></Center>;
  const lines = cart?.lines || [];
  if (!lines.length) {
    return (
      <div className="rounded-2xl bg-white ring-1 ring-sl-line shadow-card p-10 text-center anim-fade-up">
        <p className="text-[15px] font-700 text-sl-ink">Your cart is empty</p>
        <p className="text-[13px] text-sl-muted mt-1">Find something with real fit proof.</p>
        <button onClick={onShop} className="mt-4 h-10 px-5 rounded-lg bg-az-orange text-az-navy text-[13px] font-700 hover:bg-az-orange-deep transition">
          Browse the shop
        </button>
      </div>
    );
  }
  return (
    <div className="grid gap-4 md:grid-cols-3 items-start anim-fade-up">
      <div className="md:col-span-2 rounded-2xl bg-white ring-1 ring-sl-line shadow-card divide-y divide-sl-line">
        {lines.map((l, i) => (
          <div key={i} className="flex gap-3 p-4">
            <Thumb src={l.thumb} alt={l.title} category={l.category} className="w-16 h-16 rounded-xl shrink-0" />
            <div className="min-w-0 flex-1">
              <h3 className="font-600 text-[13.5px] leading-tight text-sl-ink">{l.title}</h3>
              {l.size && <p className="text-[11.5px] text-sl-muted mt-0.5">Size {l.size}</p>}
              <p className="text-[11.5px] text-sl-muted mt-0.5">Qty {l.qty}</p>
            </div>
            <span className="font-display font-800 text-[15px] tnum text-sl-ink self-center">{inr(l.price * l.qty)}</span>
          </div>
        ))}
      </div>
      <div className="rounded-2xl bg-white ring-1 ring-sl-line shadow-card p-4">
        <div className="flex items-center justify-between text-[13px]">
          <span className="text-sl-muted">Subtotal ({cart.count} item{cart.count > 1 ? "s" : ""})</span>
          <span className="font-700 tnum text-sl-ink">{inr(cart.total)}</span>
        </div>
        <div className="flex items-center justify-between text-[13px] mt-1.5">
          <span className="text-sl-muted">Delivery</span>
          <span className="font-700 text-sl-green-deep">FREE</span>
        </div>
        <div className="mt-3 pt-3 border-t border-sl-line flex items-center justify-between">
          <span className="font-700 text-[14px] text-sl-ink">Order total</span>
          <span className="font-display font-800 text-[20px] tnum text-sl-ink">{inr(cart.total)}</span>
        </div>
        <button
          onClick={onCheckout}
          disabled={busy}
          className="mt-4 w-full h-11 rounded-xl bg-az-orange text-az-navy font-700 text-[14px] hover:bg-az-orange-deep transition active:scale-[0.99] disabled:opacity-60 flex items-center justify-center gap-2"
        >
          {busy && <Spinner className="w-4 h-4" />}
          Pay with UPI
        </button>
        <p className="mt-2 text-center text-[11px] text-sl-muted">Secure UPI collect · no card needed</p>
      </div>
    </div>
  );
}

function Orders({ orders, loading, busy, onResell, onReturn, onReplace }) {
  if (loading) return <Center><Spinner /></Center>;
  return (
    <div className="grid gap-3 md:grid-cols-2 anim-fade-up">
      {(orders || []).map((o, i) => (
        <div key={o.order_id} className="rounded-2xl bg-white ring-1 ring-sl-line shadow-card p-4" style={{ animationDelay: `${i * 40}ms` }}>
          <div className="flex gap-3">
            <Thumb src={`/items/${o.item_id || o.asin || "x"}/current_1.jpg`} alt={o.title} category={o.category || "electronics"} className="w-16 h-16 rounded-xl shrink-0" />
            <div className="min-w-0 flex-1">
              <h3 className="font-600 text-[13.5px] leading-tight text-sl-ink">{o.title}</h3>
              <p className="text-[11.5px] text-sl-muted mt-0.5">Delivered · {fmtDate(o.purchase_date)}</p>
              <p className="text-[11.5px] text-sl-muted mt-0.5">Paid {inr(o.price_paid)}</p>
            </div>
          </div>
          <div className="mt-3 space-y-2">
            {/* Return + Replace (within the return window), then Resell (NEW 4) */}
            {o.return_window_open ? (
              <div className="flex gap-2">
                <button
                  onClick={() => onReturn(o)}
                  className="flex-1 h-9 rounded-lg text-[12.5px] font-700 bg-white text-sl-ink ring-1 ring-sl-line hover:bg-sl-paper transition active:scale-[0.98]"
                >
                  Return · {o.days_left}d
                </button>
                <button
                  onClick={() => onReplace(o)}
                  className="flex-1 h-9 rounded-lg text-[12.5px] font-700 bg-white text-sl-ink ring-1 ring-sl-line hover:bg-sl-paper transition active:scale-[0.98]"
                >
                  Replace
                </button>
              </div>
            ) : (
              <span className="h-9 rounded-lg text-[11px] font-600 text-sl-muted bg-sl-paper ring-1 ring-sl-line grid place-items-center text-center px-1 leading-tight">
                Return window closed{o.return_by ? ` · ${fmtDate(o.return_by)}` : ""}
              </span>
            )}
            {o.resellable ? (
              <button
                onClick={() => onResell(o)}
                disabled={busy}
                className="w-full h-9 rounded-lg text-[12.5px] font-800 bg-sl-green text-white hover:bg-sl-green-deep transition active:scale-[0.98] disabled:opacity-60 flex items-center justify-center gap-1.5"
              >
                {busy && <Spinner className="w-3.5 h-3.5" />}
                Resell on Second Life
              </button>
            ) : (
              <span className="w-full h-9 rounded-lg text-[11px] font-600 text-sl-muted bg-sl-paper ring-1 ring-sl-line grid place-items-center">
                No local demand yet
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function Notifications({ list, loading, busy, onNotif }) {
  if (loading) return <Center><Spinner /></Center>;
  const items = list || [];
  return (
    <div className="space-y-3 max-w-2xl anim-fade-up">
      {items.map((n) =>
        n.hero ? (
          <div key={n.id} className="relative overflow-hidden rounded-2xl bg-sl-green-deep text-white p-5 shadow-card">
            <div className="absolute -right-6 -top-8 w-28 h-28 rounded-full bg-sl-green-soft/25 blur-2xl" />
            <div className="flex items-center gap-1.5 mb-1.5">
              <SLBadge />
              <span className="text-[10px] font-800 uppercase tracking-wider text-sl-mint">Idle Asset Radar</span>
            </div>
            <h3 className="font-display font-800 text-[16px] leading-tight">{n.title}</h3>
            <p className="text-white/85 text-[13px] leading-snug mt-1">{n.body}</p>
            <button
              onClick={() => onNotif(n)}
              disabled={busy}
              className="mt-3 h-10 px-5 rounded-lg bg-white text-sl-green-deep font-800 text-[13px] hover:bg-sl-mint transition active:scale-[0.98] disabled:opacity-60 flex items-center gap-2"
            >
              {busy && <Spinner className="w-4 h-4" />}
              {n.cta}
            </button>
          </div>
        ) : (
          <button
            key={n.id}
            onClick={() => onNotif(n)}
            className="group w-full text-left rounded-2xl bg-white ring-1 ring-sl-line shadow-card p-4 flex items-center gap-3 hover:ring-az-steel/40 transition"
          >
            <span className="w-10 h-10 rounded-xl grid place-items-center bg-sl-paper text-sl-muted shrink-0">{KIND_ICON[n.kind] || "•"}</span>
            <div className="min-w-0 flex-1">
              <h3 className="font-600 text-[13px] text-sl-ink truncate">{n.title}</h3>
              <p className="text-[12px] text-sl-muted leading-snug">{n.body}</p>
            </div>
            <span className="text-[11px] text-sl-muted shrink-0">{n.ts}</span>
          </button>
        )
      )}
    </div>
  );
}

const KIND_ICON = { price_drop: "₹", delivery: "📦" };

function Center({ children }) {
  return <div className="grid place-items-center py-16 text-sl-muted">{children}</div>;
}

function fmtDate(s) {
  try {
    return new Date(s).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
  } catch {
    return s;
  }
}
