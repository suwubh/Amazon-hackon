import { useEffect, useState } from "react";
import { api } from "../lib/api";
import Thumb from "../components/Thumb";
import { SLBadge, Spinner } from "../components/ui";
import { inr } from "../lib/format";

// Flash deals near you (MT10 Fix 4) — the public resell board. Any tab can browse
// it; tapping "I'm interested" posts to the listing so the reseller's My-resells
// view sees it live (real cross-tab). Self-fetches + polls so a freshly-listed
// item from another tab appears. Rendered as the BuyerStore "Flash deals" tab.
export default function FlashDeals({ persona }) {
  const [listings, setListings] = useState(null);
  const [interested, setInterested] = useState({}); // listing_id -> true (this tab)

  useEffect(() => {
    let alive = true;
    async function tick() {
      try {
        const { listings } = await api.listings();
        if (alive) setListings(listings);
      } catch { /* keep last good */ }
    }
    tick();
    const t = setInterval(tick, 4000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  async function express(l) {
    setInterested((m) => ({ ...m, [l.listing_id]: true }));
    try {
      await api.addInterest(l.listing_id);
    } catch {
      setInterested((m) => ({ ...m, [l.listing_id]: false }));
    }
  }

  if (listings === null) return <Center><Spinner /></Center>;
  if (!listings.length) {
    return (
      <div className="rounded-2xl bg-white ring-1 ring-sl-line shadow-card p-10 text-center anim-fade-up max-w-xl">
        <p className="text-[15px] font-700 text-sl-ink">No resells nearby yet</p>
        <p className="text-[13px] text-sl-muted mt-1">When neighbours list, their deals show up here.</p>
      </div>
    );
  }

  return (
    <div className="anim-fade-up">
      <div className="flex items-center gap-2 mb-3">
        <SLBadge />
        <p className="text-[12px] font-700 uppercase tracking-wider text-sl-muted">Resold by neighbours · near you</p>
      </div>
      <div className="grid gap-3 grid-cols-2 sm:grid-cols-3 lg:grid-cols-4">
        {listings.map((l, i) => {
          const mine = interested[l.listing_id];
          const own = persona && l.owner === persona; // your own listing
          const sold = l.status === "sold";
          return (
            <div
              key={l.listing_id}
              className="rounded-2xl bg-white ring-1 ring-sl-line shadow-card p-3 flex flex-col"
              style={{ animationDelay: `${i * 30}ms` }}
            >
              <div className="relative">
                <Thumb src={l.thumb} alt={l.title} category={l.category || "electronics"} className={`w-full aspect-square rounded-xl ${sold ? "opacity-60" : ""}`} />
                {sold && (
                  <span className="absolute top-2 left-2 rounded-full bg-az-navy text-white text-[10px] font-800 px-2 py-0.5 tracking-wide">SOLD</span>
                )}
              </div>
              <h3 className="mt-2.5 font-600 text-[12.5px] leading-tight text-sl-ink line-clamp-2 min-h-[34px]">{l.title}</h3>
              <div className="mt-1 flex items-center justify-between">
                <span className="font-display font-800 text-[16px] tnum text-sl-ink">{inr(l.ask_price)}</span>
                <span className="text-[10px] text-sl-muted">{l.range_km} km</span>
              </div>
              <p className="text-[10.5px] text-sl-muted mt-0.5">by {l.owner} · {l.interests?.length || 0} interested</p>
              {sold ? (
                <span className="mt-2 h-9 rounded-lg text-[12px] font-700 bg-sl-paper text-sl-muted ring-1 ring-sl-line grid place-items-center">
                  Sold nearby
                </span>
              ) : own ? (
                <span className="mt-2 h-9 rounded-lg text-[12px] font-700 bg-sl-paper text-sl-muted ring-1 ring-sl-line grid place-items-center">
                  Your listing
                </span>
              ) : (
                <button
                  onClick={() => express(l)}
                  disabled={mine}
                  className={`mt-2 h-9 rounded-lg text-[12px] font-800 transition active:scale-[0.98] ${
                    mine ? "bg-sl-mint text-sl-green-deep" : "bg-sl-green text-white hover:bg-sl-green-deep"
                  }`}
                >
                  {mine ? "Interested ✓ · seller notified" : "I’m interested"}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Center({ children }) {
  return <div className="grid place-items-center py-16 text-sl-muted">{children}</div>;
}
