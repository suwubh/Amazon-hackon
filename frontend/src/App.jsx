import { useEffect, useState } from "react";
import { api } from "./lib/api";
import WebShell from "./components/WebShell";
import RadarToast from "./components/RadarToast";
import { ErrorNote } from "./components/ui";
import { inr } from "./lib/format";
import Inbox from "./screens/Inbox";
import ItemIntro from "./screens/ItemIntro";
import Grade from "./screens/Grade";
import RouteScreen from "./screens/RouteScreen";
import HealthCard from "./screens/HealthCard";
import RadarScreen from "./screens/RadarScreen";
import LiquidityScreen from "./screens/LiquidityScreen";
import SealLane from "./screens/SealLane";
import DiagnoseScreen from "./screens/DiagnoseScreen";
import MetricsScreen from "./screens/MetricsScreen";
import Home from "./screens/Home";
import BuyerStore from "./screens/BuyerStore";
import Pdp from "./screens/Pdp";
import Checkout from "./screens/Checkout";
import SellerDashboard from "./screens/SellerDashboard";

// Each inbox item drives a dedicated flow. SL-001 is the ⭐ spine; the rest are
// the MT4 supporting beats. Anything not mapped here stays QUEUED in the inbox.
const LANE = { "SL-002": "radar", "SL-003": "diagnose", "SL-004": "rto" };
const PERSONA = "rahul";

export default function App() {
  const [screen, setScreen] = useState("home");
  const [items, setItems] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [itemsLoading, setItemsLoading] = useState(true);

  // persona views (buyer / seller) so shared screens return to the right home.
  const [origin, setOrigin] = useState("ops");
  const [buyerTab, setBuyerTab] = useState("shop");
  const [buyerOrders, setBuyerOrders] = useState(null);
  const [ordersLoading, setOrdersLoading] = useState(false);
  const [cart, setCart] = useState(null);
  const [cartLoading, setCartLoading] = useState(false);
  const [notifications, setNotifications] = useState(null);
  const [notifLoading, setNotifLoading] = useState(false);
  const [checkout, setCheckout] = useState(null);
  const [checkoutBusy, setCheckoutBusy] = useState(false);
  const [sellerData, setSellerData] = useState(null);
  const [sellerLoading, setSellerLoading] = useState(false);
  const [busyAsin, setBusyAsin] = useState(null);
  const [advice, setAdvice] = useState(null); // size-advice payload for the PDP

  const [item, setItem] = useState(null);
  const [lane, setLane] = useState("spine");
  const [grade, setGrade] = useState(null);
  const [route, setRoute] = useState(null);
  const [cascade, setCascade] = useState(null); // MT8 derived waterfall
  const [card, setCard] = useState(null);
  const [radarData, setRadarData] = useState(null);
  const [curve, setCurve] = useState(null);
  const [seal, setSeal] = useState(null);
  const [diagnose, setDiagnose] = useState(null);

  const [busy, setBusy] = useState(false); // in-flight transition
  const [listed, setListed] = useState(false);
  const [toast, setToast] = useState(null); // { title, message }
  const [err, setErr] = useState(null);

  const [forceCached, setForceCached] = useState(
    () => localStorage.getItem("sl_force_cached") === "1"
  );
  useEffect(() => {
    localStorage.setItem("sl_force_cached", forceCached ? "1" : "0");
  }, [forceCached]);

  // load inbox + cart count + warm the lambda
  useEffect(() => {
    api.health().catch(() => {});
    (async () => {
      try {
        const { items } = await api.items();
        setItems(items);
      } catch (e) {
        setErr({ message: `Couldn't reach the grading engine (${e.message}).`, retry: reloadInbox });
      } finally {
        setItemsLoading(false);
      }
    })();
    refreshMetrics();
    api.cart(PERSONA).then(setCart).catch(() => {});
  }, []);

  function refreshMetrics() {
    api.metrics().then(setMetrics).catch(() => {});
  }

  function reloadInbox() {
    setErr(null);
    setItemsLoading(true);
    api
      .items()
      .then(({ items }) => setItems(items))
      .catch((e) => setErr({ message: `Still can't reach the engine (${e.message}).`, retry: reloadInbox }))
      .finally(() => setItemsLoading(false));
  }

  function resetItemState() {
    setGrade(null);
    setRoute(null);
    setCascade(null);
    setCard(null);
    setRadarData(null);
    setCurve(null);
    setSeal(null);
    setDiagnose(null);
    setListed(false);
    setToast(null);
  }

  async function openItem(row) {
    setErr(null);
    resetItemState();
    setOrigin("ops");
    const thisLane = LANE[row.item_id] || "spine";
    setLane(thisLane);
    setBusy(true);
    try {
      const detail = await api.item(row.item_id).catch(() => null);
      const it = detail ? { ...row, ...detail.item, passport: detail.passport } : row;
      setItem(it);
      if (thisLane === "radar") {
        const r = await api.radar(it.asin);
        setRadarData(r);
        setScreen("radar");
      } else if (thisLane === "diagnose") {
        const d = await api.diagnose(it.asin);
        setDiagnose(d);
        setScreen("diagnose");
      } else if (thisLane === "rto") {
        const s = await api.sealCheck(it.item_id, forceCached);
        setSeal(s);
        setScreen("seal");
      } else {
        setScreen("intro");
      }
    } catch (e) {
      setErr({ message: `Couldn't open this item (${e.detail || e.message}).`, retry: () => openItem(row) });
    } finally {
      setBusy(false);
    }
  }

  // --- spine (SL-001) ---
  async function runScan(currentImages) {
    setErr(null);
    setBusy(true);
    try {
      const g = await api.grade(item.item_id, forceCached, currentImages);
      setGrade(g);
      setScreen("grade");
    } catch (e) {
      setErr({ message: `Grading failed (${e.detail || e.message}).`, retry: () => runScan(currentImages) });
    } finally {
      setBusy(false);
    }
  }

  async function runRoute() {
    setErr(null);
    setBusy(true);
    try {
      const r = await api.routeSafe(item.item_id, forceCached);
      setRoute(r);
      setScreen("route");
      // Derived terminal-state cascade (MT8) — non-blocking so the route screen
      // never waits on it; the strip fills in when it lands.
      api.cascadeSafe(item.item_id, forceCached).then(setCascade).catch(() => {});
    } catch (e) {
      setErr({ message: `Routing failed (${e.detail || e.message}).`, retry: runRoute });
    } finally {
      setBusy(false);
    }
  }

  async function buildCard() {
    setErr(null);
    setBusy(true);
    try {
      const c = await api.healthCardSafe(item.item_id, forceCached);
      setCard(c);
      setScreen("card");
    } catch (e) {
      setErr({ message: `Health Card failed (${e.detail || e.message}).`, retry: buildCard });
    } finally {
      setBusy(false);
    }
  }

  function listItem() {
    setListed(true);
    const w = route?.paths.find((p) => p.winner);
    const msg = w
      ? `${w.note || "Buyers matched nearby"}${w.distance_km != null ? ` · nearest ${w.distance_km} km` : ""}`
      : "Buyers matched nearby";
    setToast({ title: "Idle Asset Radar · ping sent", message: msg });
    refreshMetrics();
  }

  // --- radar lane (SL-002) ---
  async function openLiquidity() {
    setErr(null);
    setBusy(true);
    try {
      const c = await api.priceCurveSafe(item.item_id);
      setCurve(c);
      setScreen("liquidity");
    } catch (e) {
      setErr({ message: `Couldn't price this item (${e.detail || e.message}).`, retry: openLiquidity });
    } finally {
      setBusy(false);
    }
  }

  function listIdle(point) {
    setToast({
      title: "Listed · buyers pinged",
      message: `${inr(point.price)} ask · ${point.buyers_at_price} buyers ready, sells in ~${point.est_days_to_sell} days. Refund parked as Amazon credit.`,
    });
    refreshMetrics();
  }

  // --- RTO lane (SL-004) ---
  async function runRtoRoute() {
    setErr(null);
    setBusy(true);
    try {
      const r = await api.routeRto(item.item_id, forceCached);
      setRoute(r);
      setScreen("route");
    } catch (e) {
      setErr({ message: `Routing failed (${e.detail || e.message}).`, retry: runRtoRoute });
    } finally {
      setBusy(false);
    }
  }

  function listRto() {
    setListed(true);
    setToast({
      title: "Sealed unit relisted",
      message: "Local pickup booked — refund already released as credit. The box never saw a warehouse.",
    });
    refreshMetrics();
  }

  function goInbox() {
    setToast(null);
    setErr(null);
    setScreen("inbox");
  }

  // --- persona console nav ---
  function originHome() {
    return origin === "buyer" ? "buyer" : origin === "seller" ? "seller" : "inbox";
  }
  function backToOrigin() {
    setToast(null);
    setErr(null);
    setScreen(originHome());
  }
  function goHome() {
    setToast(null);
    setErr(null);
    setScreen("home");
  }

  function openOps() {
    setErr(null);
    setScreen("inbox");
  }

  function openBuyer(tab = "shop") {
    setErr(null);
    setOrigin("buyer");
    setBuyerTab(tab);
    setScreen("buyer");
    if (!buyerOrders) {
      setOrdersLoading(true);
      api.orders(PERSONA).then((d) => setBuyerOrders(d.orders)).catch(() => setBuyerOrders([])).finally(() => setOrdersLoading(false));
    }
    if (!cart) {
      setCartLoading(true);
      api.cart(PERSONA).then(setCart).catch(() => setCart({ lines: [], total: 0, count: 0 })).finally(() => setCartLoading(false));
    }
    if (!notifications) {
      setNotifLoading(true);
      api.notifications(PERSONA).then((d) => setNotifications(d.notifications)).catch(() => setNotifications([])).finally(() => setNotifLoading(false));
    }
  }

  function openSeller() {
    setErr(null);
    setOrigin("seller");
    setScreen("seller");
    if (!sellerData) {
      setSellerLoading(true);
      api
        .sellerReturns()
        .then(setSellerData)
        .catch((e) => setErr({ message: `Couldn't load the dashboard (${e.message}).`, retry: openSeller }))
        .finally(() => setSellerLoading(false));
    }
  }

  // buyer: shop → PDP (size proof, PREVENT)
  async function openPdp(gridItem) {
    setErr(null);
    setBusy(true);
    try {
      const a = await api.sizeAdvice(gridItem.asin);
      setAdvice(a);
      setScreen("pdp");
    } catch (e) {
      setErr({ message: `Couldn't open this product (${e.detail || e.message}).`, retry: () => openPdp(gridItem) });
    } finally {
      setBusy(false);
    }
  }

  // PDP add-to-cart → real /cart write, then land in the cart
  async function buyPdp(size) {
    setBusy(true);
    try {
      const c = await api.addToCart(PERSONA, advice.asin, size);
      setCart(c);
      setOrigin("buyer");
      setBuyerTab("cart");
      setScreen("buyer");
      setToast({
        title: "Added to cart",
        message: size ? `${advice.title} · size ${size} — the size most buyers kept.` : `${advice.title} added to your cart.`,
      });
    } catch (e) {
      setErr({ message: `Couldn't add to cart (${e.detail || e.message}).` });
    } finally {
      setBusy(false);
    }
  }

  // cart → UPI checkout (pending) → confirm (success)
  async function openCheckout() {
    setErr(null);
    setCheckoutBusy(true);
    try {
      const co = await api.checkout(PERSONA);
      setCheckout(co);
      setScreen("checkout");
    } catch (e) {
      setErr({ message: `Couldn't start checkout (${e.detail || e.message}).`, retry: openCheckout });
    } finally {
      setCheckoutBusy(false);
    }
  }

  async function confirmCheckout() {
    setCheckoutBusy(true);
    try {
      const co = await api.checkout(PERSONA, true);
      // The cart is a per-instance overlay, so a confirm landing on a different
      // warm Lambda could recompute a different total/order id. Keep the order id +
      // amount the user actually approved; the confirm only flips status to success.
      setCheckout((prev) => ({ ...co, order_id: prev.order_id, amount: prev.amount }));
      const fresh = await api.cart(PERSONA).catch(() => null);
      if (fresh) setCart(fresh);
    } catch (e) {
      setErr({ message: `Couldn't confirm payment (${e.detail || e.message}).`, retry: confirmCheckout });
    } finally {
      setCheckoutBusy(false);
    }
  }

  // buyer: order history → one-tap resell (RECIRCULATE) → reuses the radar lane
  async function resellOrder(order) {
    if (!order.resellable || !order.item_id) return;
    setErr(null);
    resetItemState();
    setOrigin("buyer");
    setLane("radar");
    setBusy(true);
    try {
      const detail = await api.item(order.item_id).catch(() => null);
      const it = detail
        ? { ...detail.item, passport: detail.passport }
        : { item_id: order.item_id, asin: order.asin, title: order.title };
      setItem(it);
      const r = await api.radar(order.asin);
      setRadarData(r);
      setScreen("radar");
    } catch (e) {
      setErr({ message: `Couldn't open resale (${e.detail || e.message}).`, retry: () => resellOrder(order) });
    } finally {
      setBusy(false);
    }
  }

  function returnOrder(order) {
    setToast({
      title: "Return started",
      message: `${order.title} → heading to the Returns desk for grading.`,
    });
  }

  // notification tap → the idle-monitor nudge resells; the rest are informational
  function openNotif(n) {
    if (n.kind === "resell" && n.item_id) {
      resellOrder({ item_id: n.item_id, asin: n.asin, title: n.title, resellable: true });
    } else {
      setToast({ title: n.title, message: n.body });
    }
  }

  // seller: tap a high-return SKU → diagnose drill-down (PREVENT) → reuses DiagnoseScreen
  async function openSellerDiagnose(sku) {
    setErr(null);
    setOrigin("seller");
    setBusyAsin(sku.asin);
    setBusy(true);
    try {
      setItem({ item_id: sku.item_id, asin: sku.asin, title: sku.title, category: sku.category, thumb: sku.thumb });
      const d = await api.diagnose(sku.asin);
      setDiagnose(d);
      setScreen("diagnose");
    } catch (e) {
      setErr({ message: `Couldn't load the fix (${e.detail || e.message}).`, retry: () => openSellerDiagnose(sku) });
    } finally {
      setBusy(false);
      setBusyAsin(null);
    }
  }

  // The landing owns the full-screen dark stage and has no top bar; every inner
  // page lives inside the slim WebShell chrome.
  if (screen === "home") {
    return (
      <div className="anim-fade-in">
        <Home onOps={openOps} onBuyer={() => openBuyer("shop")} onSeller={openSeller} />
      </div>
    );
  }

  return (
    <WebShell onHome={goHome}>
      <div key={screen} className="anim-fade-in">
        {screen === "inbox" && (
          <Inbox
            items={items}
            metrics={metrics}
            loading={itemsLoading}
            forceCached={forceCached}
            onForceCached={setForceCached}
            onOpen={openItem}
            onShowMetrics={() => setScreen("metrics")}
            onBack={goHome}
          />
        )}
        {screen === "buyer" && (
          <BuyerStore
            items={items}
            cart={cart}
            cartLoading={cartLoading}
            orders={buyerOrders}
            ordersLoading={ordersLoading}
            notifications={notifications}
            notifLoading={notifLoading}
            busy={busy}
            tab={buyerTab}
            onTab={setBuyerTab}
            onOpenPdp={openPdp}
            onResell={resellOrder}
            onReturn={returnOrder}
            onCheckout={openCheckout}
            onNotif={openNotif}
            onBack={goHome}
          />
        )}
        {screen === "pdp" && advice && (
          <Pdp advice={advice} busy={busy} onBuy={buyPdp} onBack={() => setScreen("buyer")} />
        )}
        {screen === "checkout" && checkout && (
          <Checkout
            checkout={checkout}
            confirming={checkoutBusy}
            onConfirm={confirmCheckout}
            onDone={() => openBuyer("shop")}
            onBack={() => { setBuyerTab("cart"); setScreen("buyer"); }}
          />
        )}
        {screen === "seller" && (
          <SellerDashboard
            data={sellerData}
            loading={sellerLoading}
            busy={busy}
            busyAsin={busyAsin}
            onDiagnose={openSellerDiagnose}
            onBack={goHome}
          />
        )}
        {screen === "intro" && item && (
          <ItemIntro item={item} scanning={busy} onScan={runScan} onBack={goInbox} />
        )}
        {screen === "grade" && grade && (
          <Grade item={item} grade={grade} routing={busy} onRoute={runRoute} onBack={() => setScreen("intro")} />
        )}
        {screen === "route" && route && (
          <RouteScreen
            route={route}
            cascade={lane === "rto" ? null : cascade}
            building={busy}
            onHealthCard={lane === "rto" ? listRto : buildCard}
            nextLabel={lane === "rto" ? "List for local pickup" : undefined}
            nextHint={lane === "rto" ? "Sealed unit · routes straight to a local buyer" : undefined}
            onBack={() => setScreen(lane === "rto" ? "seal" : "grade")}
          />
        )}
        {screen === "card" && card && (
          <HealthCard
            item={item}
            card={card}
            listed={listed}
            building={false}
            onList={listItem}
            onBack={() => setScreen("route")}
          />
        )}
        {screen === "radar" && radarData && item && (
          <RadarScreen item={item} radar={radarData} valuing={busy} onSell={openLiquidity} onBack={backToOrigin} />
        )}
        {screen === "liquidity" && curve && item && (
          <LiquidityScreen item={item} curve={curve} listing={false} onList={listIdle} onBack={() => setScreen("radar")} />
        )}
        {screen === "seal" && seal && item && (
          <SealLane item={item} seal={seal} routing={busy} onRoute={runRtoRoute} onBack={goInbox} />
        )}
        {screen === "diagnose" && diagnose && item && (
          <DiagnoseScreen item={item} diagnose={diagnose} onBack={backToOrigin} />
        )}
        {screen === "metrics" && (
          <MetricsScreen metrics={metrics} onBack={goInbox} onDone={goInbox} />
        )}
      </div>

      {/* radar ping — fires on every list/handoff beat */}
      {toast && <RadarToast title={toast.title} message={toast.message} onClose={() => setToast(null)} />}

      {/* global error */}
      {err && (
        <div className="fixed inset-x-0 bottom-0 z-[60] px-4 pb-4">
          <div className="mx-auto max-w-md">
            <ErrorNote
              onRetry={
                err.retry
                  ? () => {
                      const r = err.retry;
                      setErr(null);
                      r();
                    }
                  : undefined
              }
            >
              {err.message}
            </ErrorNote>
          </div>
        </div>
      )}
    </WebShell>
  );
}
