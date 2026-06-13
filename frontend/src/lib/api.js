// Falls back to the deployed Function URL so the Vercel build works even if the
// VITE_API_URL env var isn't set in the dashboard. Override locally via .env.local.
const DEPLOYED = "https://ahwfmhaqed45p5xxk2u663oi6m0mejgi.lambda-url.ca-central-1.on.aws";
const API_URL = (import.meta.env.VITE_API_URL || DEPLOYED).replace(/\/$/, "");

async function req(path, { method = "GET", body } = {}) {
  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`);
    err.status = res.status;
    try {
      err.detail = (await res.json()).detail;
    } catch {
      /* non-JSON error body */
    }
    throw err;
  }
  return res.json();
}

export const api = {
  base: API_URL,
  health: () => req("/health"),
  items: () => req("/items"),
  item: (id) => req(`/items/${id}`),
  // currentImages: optional base64 photos (no data: prefix) — grades the UPLOADED
  // current photos against the seeded day-0 baseline. Omit → seeded current photos.
  grade: (id, forceCached, currentImages) =>
    req("/grade", {
      method: "POST",
      body: {
        item_id: id,
        force_cached: !!forceCached,
        ...(currentImages && currentImages.length ? { current_images: currentImages } : {}),
      },
    }),
  route: (id) => req("/route", { method: "POST", body: { item_id: id } }),
  // MT8 — derived terminal-state waterfall (pure-Python, no AI). Needs a prior grade.
  cascade: (id) => req(`/cascade/${id}`),
  healthCard: (id) => req(`/health-card/${id}`),
  sealCheck: (id) => req("/seal-check", { method: "POST", body: { item_id: id } }),
  radar: (asin) => req(`/radar/${asin}`),
  priceCurve: (id) => req(`/price-curve/${id}`),
  diagnose: (asin) => req("/diagnose-listing", { method: "POST", body: { asin } }),
  metrics: () => req("/metrics"),
  // MT7 — two-sided console. Stateless reads, no passport prereq → no *Safe wrapper.
  // MT10: sizeAdvice takes an optional persona for the personal history block.
  sizeAdvice: (asin, persona) =>
    req(`/size-advice/${asin}${persona ? `?persona=${persona}` : ""}`),
  sellerReturns: () => req("/seller/returns"),
  orders: (persona) => req(`/orders/${persona}`),
  // MT10 — Ops returns desk + resell marketplace.
  returns: () => req("/returns"),
  addReturn: (body) => req("/returns", { method: "POST", body }),
  resellQuote: (body) => req("/resell/quote", { method: "POST", body }),
  createListing: (body) => req("/resell/listings", { method: "POST", body }),
  listings: () => req("/resell/listings"),
  listing: (id) => req(`/resell/listings/${id}`),
  addInterest: (id, body = {}) => req(`/resell/listings/${id}/interest`, { method: "POST", body }),
  // Reseller one-tap accepts / declines an interested buyer.
  sellToInterest: (id, interestId) =>
    req(`/resell/listings/${id}/sell`, { method: "POST", body: { interest_id: interestId } }),
  declineInterest: (id, interestId) =>
    req(`/resell/listings/${id}/decline`, { method: "POST", body: { interest_id: interestId } }),
  // MT9 — buyer storefront. Cart is a per-instance overlay; the rest are seed reads.
  cart: (persona) => req(`/cart/${persona}`),
  addToCart: (persona, asin, size, qty = 1) =>
    req(`/cart/${persona}`, { method: "POST", body: { asin, size: size || null, qty } }),
  notifications: (persona) => req(`/notifications/${persona}`),
  checkout: (persona, confirm = false) =>
    req(`/checkout/${persona}`, { method: "POST", body: { confirm } }),
};

// The in-memory passport is per-Lambda-instance: a cold start between calls
// resets grade/route state and downstream endpoints 409. These re-run the
// prerequisites once so the demo spine never breaks on a warm→cold swap.
api.routeSafe = async (id, forceCached) => {
  try {
    return await api.route(id);
  } catch (e) {
    if (e.status === 409) {
      await api.grade(id, forceCached);
      return api.route(id);
    }
    throw e;
  }
};

api.healthCardSafe = async (id, forceCached) => {
  try {
    return await api.healthCard(id);
  } catch (e) {
    if (e.status === 409) {
      await api.grade(id, forceCached);
      await api.route(id);
      return api.healthCard(id);
    }
    throw e;
  }
};

// A sealed RTO unit routes as factory-new with no grade — but /route reads the
// SEAL_CHECKED event from the same warm instance. On a cold-start 409, re-run the
// seal check (not a grade) then route.
api.routeRto = async (id, forceCached) => {
  try {
    return await api.route(id);
  } catch (e) {
    if (e.status === 409) {
      await api.sealCheck(id, forceCached);
      return api.route(id);
    }
    throw e;
  }
};

// The liquidity curve needs a prior GRADED event. For the idle-asset lane the
// grade is a hidden valuation step (we never show the grade screen), and the
// grade letter is invariant for a like-new idle unit — so use the instant cached
// grade so the slider never blocks on a live call.
api.priceCurveSafe = async (id) => {
  try {
    return await api.priceCurve(id);
  } catch (e) {
    if (e.status === 409) {
      await api.grade(id, true);
      return api.priceCurve(id);
    }
    throw e;
  }
};

// The cascade is read after /route on the same warm instance, so the GRADED event
// is normally present. On a cold-start 409, re-run the grade once (mirrors routeSafe).
api.cascadeSafe = async (id, forceCached) => {
  try {
    return await api.cascade(id);
  } catch (e) {
    if (e.status === 409) {
      await api.grade(id, forceCached);
      return api.cascade(id);
    }
    throw e;
  }
};
