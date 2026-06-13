import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import Thumb from "../components/Thumb";
import { Spinner } from "../components/ui";
import { inr } from "../lib/format";

// My resells (MT10) — the reseller's live deal desk. Polls the board (~3s) and
// shows each listing this persona owns with the interested buyers as they arrive
// from the Flash-deals board in another tab (real cross-tab). Rahul picks a buyer
// and one-tap sells, or declines — the listing then flips to SOLD with his payout.
export default function MyResells({ persona, onToast }) {
  const [mine, setMine] = useState(null);
  const [busyKey, setBusyKey] = useState(null); // `${listing_id}:${interest_id}:${action}`
  const pollRef = useRef(true);

  async function refresh() {
    try {
      const { listings } = await api.listings();
      setMine(listings.filter((l) => l.owner === persona));
    } catch { /* keep last good */ }
  }

  useEffect(() => {
    pollRef.current = true;
    refresh();
    const t = setInterval(() => { if (pollRef.current) refresh(); }, 3000);
    return () => { pollRef.current = false; clearInterval(t); };
  }, [persona]);

  async function act(listing, interest, action) {
    const key = `${listing.listing_id}:${interest.interest_id}:${action}`;
    setBusyKey(key);
    pollRef.current = false; // freeze polling so it can't clobber the optimistic flip
    try {
      if (action === "sell") {
        const updated = await api.sellToInterest(listing.listing_id, interest.interest_id);
        onToast?.({
          title: "Sold on Second Life",
          message: `${listing.title} → ${interest.buyer_name}. ${inr(updated.net_earned)} credited to your Amazon balance.`,
        });
      } else {
        await api.declineInterest(listing.listing_id, interest.interest_id);
      }
      await refresh();
    } catch {
      onToast?.({ title: "Couldn't complete that", message: "Please try again." });
    } finally {
      setBusyKey(null);
      pollRef.current = true;
    }
  }

  if (mine === null) return <Center><Spinner /></Center>;
  if (!mine.length) {
    return (
      <div className="rounded-2xl bg-white ring-1 ring-sl-line shadow-card p-10 text-center anim-fade-up max-w-xl">
        <p className="text-[15px] font-700 text-sl-ink">No active resells</p>
        <p className="text-[13px] text-sl-muted mt-1">List one from <span className="font-600">Your orders</span> → Resell on Second Life.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4 max-w-2xl anim-fade-up">
      {mine.map((l) => {
        const interests = l.interests || [];
        const pending = interests.filter((i) => i.status === "pending" || i.status === undefined);
        const sold = l.status === "sold";
        return (
          <div key={l.listing_id} className="rounded-2xl bg-white ring-1 ring-sl-line shadow-card overflow-hidden">
            <div className="flex gap-3 p-4">
              <Thumb src={l.thumb} alt={l.title} category={l.category || "electronics"} className="w-16 h-16 rounded-xl shrink-0" />
              <div className="min-w-0 flex-1">
                <h3 className="font-600 text-[13.5px] leading-tight text-sl-ink">{l.title}</h3>
                <p className="text-[11.5px] text-sl-muted mt-0.5">
                  Listed at <span className="font-700 text-sl-ink">{inr(l.ask_price)}</span> · within {l.range_km} km · delivery −{inr(l.delivery_cut)}
                </p>
              </div>
              <div className="text-right shrink-0">
                {sold ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-az-navy text-white px-2.5 py-1 text-[11px] font-800">
                    SOLD
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-sl-mint text-sl-green-deep px-2.5 py-1 text-[11px] font-800">
                    <span className="w-1.5 h-1.5 rounded-full bg-sl-green animate-pulse" />
                    {pending.length} interested
                  </span>
                )}
              </div>
            </div>

            <div className="border-t border-sl-line bg-sl-paper/60">
              {sold ? (
                <div className="px-4 py-3 anim-fade-in">
                  <div className="flex items-center justify-between">
                    <div className="min-w-0">
                      <p className="text-[12.5px] font-700 text-sl-ink">Sold to {l.sold_to?.buyer_name}</p>
                      <p className="text-[11px] text-sl-muted">{l.sold_to?.distance_km} km away · pickup arranged</p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="text-[15px] font-800 tnum text-sl-green-deep">{inr(l.net_earned)}</p>
                      <p className="text-[10.5px] text-sl-muted">credited to you</p>
                    </div>
                  </div>
                </div>
              ) : interests.length === 0 ? (
                <p className="px-4 py-3 text-[12px] text-sl-muted">Waiting for buyers nearby to tap “I’m interested”…</p>
              ) : (
                <div className="divide-y divide-sl-line">
                  {interests.map((it) => {
                    const declined = it.status === "declined";
                    const net = it.offer - l.delivery_cut;
                    return (
                      <div key={it.interest_id} className={`px-4 py-3 anim-fade-in ${declined ? "opacity-50" : ""}`}>
                        <div className="flex items-center gap-3">
                          <span className="w-8 h-8 rounded-full bg-white ring-1 ring-sl-line grid place-items-center text-[11px] font-700 text-sl-muted shrink-0">
                            {initials(it.buyer_name)}
                          </span>
                          <div className="min-w-0 flex-1">
                            <p className="text-[12.5px] font-600 text-sl-ink truncate">{it.buyer_name}</p>
                            <p className="text-[11px] text-sl-muted">{it.distance_km} km away · offers {inr(it.offer)}</p>
                          </div>
                          <div className="text-right shrink-0">
                            <p className="text-[13px] font-800 tnum text-sl-green-deep">{inr(net)}</p>
                            <p className="text-[10px] text-sl-muted">you keep</p>
                          </div>
                        </div>
                        {declined ? (
                          <p className="mt-2 text-[11px] font-700 text-sl-muted">Declined</p>
                        ) : (
                          <div className="mt-2.5 flex gap-2">
                            <button
                              onClick={() => act(l, it, "sell")}
                              disabled={!!busyKey}
                              className="flex-1 h-9 rounded-lg text-[12.5px] font-800 bg-sl-green text-white hover:bg-sl-green-deep transition active:scale-[0.98] disabled:opacity-60 flex items-center justify-center gap-1.5"
                            >
                              {busyKey === `${l.listing_id}:${it.interest_id}:sell` && <Spinner className="w-3.5 h-3.5" />}
                              Sell to {it.buyer_name.split(" ")[0]}
                            </button>
                            <button
                              onClick={() => act(l, it, "decline")}
                              disabled={!!busyKey}
                              className="h-9 px-4 rounded-lg text-[12.5px] font-700 bg-white text-sl-muted ring-1 ring-sl-line hover:bg-sl-paper transition active:scale-[0.98] disabled:opacity-60"
                            >
                              Decline
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function initials(name) {
  return (name || "?").split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
}

function Center({ children }) {
  return <div className="grid place-items-center py-16 text-sl-muted">{children}</div>;
}
