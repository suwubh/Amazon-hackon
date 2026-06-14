import { useEffect, useState } from "react";
import { api } from "../lib/api";
import Thumb from "../components/Thumb";
import { SLBadge, Spinner } from "../components/ui";
import { inr, gradeColor } from "../lib/format";

// Flash deals near you (MT10 Fix 4) — the public resell board. Any tab can browse
// it; tapping a card opens its condition detail (photos + AI grade) before a buyer
// expresses interest (MT12 NEW 12). Graded warehouse returns appear here too, with a
// "Returned" badge (MT12 NEW 9). Self-fetches + polls so freshly-listed items appear.
export default function FlashDeals({ persona, onOpen }) {
  const [listings, setListings] = useState(null);

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
        <p className="text-[12px] font-700 uppercase tracking-wider text-sl-muted">Resold by neighbours &amp; verified returns · near you</p>
      </div>
      <div className="grid gap-3 grid-cols-2 sm:grid-cols-3 lg:grid-cols-4">
        {listings.map((l, i) => {
          const sold = l.status === "sold";
          const isReturn = l.source === "return";
          return (
            <button
              key={l.listing_id}
              onClick={() => onOpen?.(l)}
              className="text-left rounded-2xl bg-white ring-1 ring-sl-line shadow-card p-3 flex flex-col transition hover:ring-sl-green/60 hover:-translate-y-0.5"
              style={{ animationDelay: `${i * 30}ms` }}
            >
              <div className="relative">
                <Thumb src={l.thumb} alt={l.title} category={l.category || "electronics"} className={`w-full aspect-square rounded-xl ${sold ? "opacity-60" : ""}`} />
                {sold ? (
                  <span className="absolute top-2 left-2 rounded-full bg-az-navy text-white text-[10px] font-800 px-2 py-0.5 tracking-wide">SOLD</span>
                ) : l.grade ? (
                  <span
                    className="absolute top-2 left-2 rounded-full text-white text-[10px] font-800 px-2 py-0.5 tracking-wide"
                    style={{ background: gradeColor(l.grade) }}
                  >
                    {isReturn ? `RETURNED · ${l.grade}` : `GRADE ${l.grade}`}
                  </span>
                ) : null}
              </div>
              <h3 className="mt-2.5 font-600 text-[12.5px] leading-tight text-sl-ink line-clamp-2 min-h-[34px]">{l.title}</h3>
              <div className="mt-1 flex items-center justify-between">
                <span className="font-display font-800 text-[16px] tnum text-sl-ink">{inr(l.ask_price)}</span>
                <span className="text-[10px] text-sl-muted">{l.range_km} km</span>
              </div>
              <p className="text-[10.5px] text-sl-muted mt-0.5">by {l.owner} · {l.interests?.length || 0} interested</p>
              <span className={`mt-2 h-9 rounded-lg text-[12px] font-700 grid place-items-center ${
                sold ? "bg-sl-paper text-sl-muted ring-1 ring-sl-line" : "bg-sl-mint text-sl-green-deep"
              }`}>
                {sold ? "Sold nearby" : "View condition →"}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function Center({ children }) {
  return <div className="grid place-items-center py-16 text-sl-muted">{children}</div>;
}
