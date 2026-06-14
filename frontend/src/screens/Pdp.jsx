import { useState } from "react";
import TopBar from "../components/TopBar";
import Thumb from "../components/Thumb";
import { FooterAction, SLBadge } from "../components/ui";
import { inr, gradeColor, gradeLabel } from "../lib/format";

// Buyer PDP — the PREVENT moment. Before a fit-risky buy, show how past buyers of
// this size actually fit it (GET /size-advice → fit) and the Second Life resale
// value so the buyer knows it holds worth. Every figure is a field of the response.
export default function Pdp({ advice, secondLife, onBack, onBuy, onPickSecondLife, busy }) {
  const fit = advice.fit;
  const resale = advice.resale_hint;
  const offers = secondLife?.offers || [];
  const [size, setSize] = useState(fit?.recommended_size || null);

  return (
    <div className="screen-scroll bg-sl-paper">
      <TopBar title="Product details" subtitle={advice.title} onBack={onBack} right={<SLBadge />} />

      {/* product header */}
      <div className="px-4 pt-4">
        <div className="rounded-2xl bg-white shadow-card ring-1 ring-sl-line p-3.5 flex gap-3 anim-fade-up">
          <Thumb src={advice.thumb} alt={advice.title} category={advice.category} className="w-[84px] h-[84px] rounded-xl shrink-0" />
          <div className="min-w-0 flex-1">
            <h2 className="font-600 text-[14.5px] leading-tight text-sl-ink">{advice.title}</h2>
            <p className="text-[11px] text-sl-muted mt-0.5 capitalize">{advice.category}</p>
            <p className="mt-1.5 font-display font-800 text-[22px] tnum text-sl-ink">{inr(advice.mrp)}</p>
            <div className="mt-0.5 flex items-center gap-1 text-[11px] text-az-link font-600">
              <Stars /> 4.3 · in stock
            </div>
          </div>
        </div>
      </div>

      {/* personal history note (MT10) — tied to this buyer's past purchases */}
      {advice.personal && (
        <div className="px-4 pt-4">
          <div className="rounded-2xl bg-sl-green-deep text-white p-4 shadow-card anim-fade-up">
            <div className="flex items-center gap-1.5 mb-1.5">
              <SLBadge />
              <span className="text-[10px] font-800 uppercase tracking-wider text-sl-mint">From your purchases</span>
            </div>
            <p className="text-[13.5px] leading-snug">{advice.personal.copy}</p>
          </div>
        </div>
      )}

      {/* size social proof — the prevent moment */}
      {fit && (
        <div className="px-4 pt-4">
          <div className="rounded-2xl bg-white shadow-card ring-1 ring-sl-green/40 p-4 anim-fade-up">
            <div className="flex items-center gap-1.5 mb-2">
              <SLBadge />
              <span className="text-[10px] font-800 uppercase tracking-wider text-sl-green-deep">Fit insight</span>
            </div>
            <p className="text-[14px] leading-snug text-sl-ink">
              <span className="font-display font-800 text-[19px] text-sl-green-deep">{fit.headline_pct}%</span>{" "}
              of {fit.your_size} buyers {fit.direction === "up" ? "ordered one size up" : "ordered one size down"}.
            </p>

            <FitBars dist={fit.fit_distribution} />

            <p className="mt-2.5 text-[12px] text-sl-muted leading-snug">{fit.advice}</p>

            {/* recommended size selector */}
            <div className="mt-3">
              <p className="text-[10px] font-700 uppercase tracking-wider text-sl-muted mb-1.5">Choose size</p>
              <div className="flex flex-wrap gap-1.5">
                {sizeOptions(fit).map((s) => {
                  const active = s === size;
                  const rec = s === fit.recommended_size;
                  return (
                    <button
                      key={s}
                      onClick={() => setSize(s)}
                      className={`relative px-3 py-1.5 rounded-lg text-[12.5px] font-700 ring-1 transition ${
                        active ? "bg-sl-green text-white ring-sl-green" : "bg-white text-sl-ink ring-sl-line hover:ring-sl-green/50"
                      }`}
                    >
                      {s}
                      {rec && (
                        <span className="absolute -top-1.5 -right-1.5 text-[8px] font-800 bg-az-orange text-az-navy rounded-full px-1 py-px leading-none">
                          PICK
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* second life buyback / resale hint */}
      {resale && (
        <div className="px-4 pt-4 pb-2">
          <div className="rounded-2xl bg-az-slate text-white p-4 shadow-card anim-fade-up">
            <p className="text-white/55 text-[11px] font-600 uppercase tracking-wider">Holds its value</p>
            <p className="mt-1 text-[13.5px] leading-snug">
              Resells for about{" "}
              <span className="font-display font-800 text-sl-green-soft">{inr(resale.amount)}</span> near you later
              {resale.buyers_nearby > 0 && (
                <> · <span className="font-700">{resale.buyers_nearby} buyer{resale.buyers_nearby > 1 ? "s" : ""}</span> within reach already want one.</>
              )}
            </p>
            <p className="mt-1.5 text-white/45 text-[11px]">Second Life buys it back or resells it locally — one tap, no listing.</p>
          </div>
        </div>
      )}

      {/* MT11 — buy-side: recovered units of THIS product available near you.
          The "layer, not app" twin — the buyer meets a Second Life unit on the
          normal product page. Every figure comes from /second-life/{asin}. */}
      {offers.length > 0 && (
        <div className="px-4 pt-4 pb-2">
          <div className="rounded-2xl bg-white shadow-card ring-1 ring-sl-green/40 p-4 anim-fade-up">
            <div className="flex items-center gap-1.5 mb-1">
              <SLBadge />
              <span className="text-[10px] font-800 uppercase tracking-wider text-sl-green-deep">Second Life options near you</span>
            </div>
            <p className="text-[12px] text-sl-muted leading-snug mb-2.5">
              {offers.length} recovered unit{offers.length > 1 ? "s" : ""} of this product on offer locally — verified Health Card, transferable warranty.
            </p>
            <div className="space-y-2">
              {offers.map((o, i) => (
                <button
                  key={i}
                  onClick={() => onPickSecondLife(o)}
                  className="w-full text-left rounded-xl ring-1 ring-sl-line bg-sl-paper hover:ring-sl-green/60 hover:bg-white transition active:scale-[0.99] p-3 flex items-center gap-3"
                >
                  <span
                    className="w-9 h-9 rounded-lg grid place-items-center font-display font-800 text-[15px] text-white shrink-0"
                    style={{ background: gradeColor(o.grade) }}
                  >
                    {o.grade}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="font-700 text-[13px] text-sl-ink leading-tight">
                      Grade {o.grade} · <span className="capitalize">{gradeLabel(o.grade)}</span>
                    </p>
                    <p className="text-[11.5px] text-sl-muted mt-0.5">{o.distance_km} km away · {o.eta}</p>
                  </div>
                  <span className="font-display font-800 text-[16px] tnum text-sl-green-deep self-center">{inr(o.price)}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      <FooterAction variant="primary" onClick={() => onBuy(size)} loading={busy}>
        {size ? `Add to cart · ${size}` : "Add to cart"}
      </FooterAction>
    </div>
  );
}

// Build a small size ladder around the buyer's size and the recommendation.
function sizeOptions(fit) {
  const set = [fit.your_size, fit.recommended_size].filter(Boolean);
  // numeric (UK 8 / UK 9) → show a small ladder; else just the two named sizes.
  const m = (fit.your_size || "").match(/^(\D*)(\d+)$/);
  if (m) {
    const [, prefix, nStr] = m;
    const n = Number(nStr);
    return [n - 1, n, n + 1, n + 2].map((v) => `${prefix}${v}`);
  }
  const ladder = ["S", "M", "L", "XL"];
  if (ladder.includes(fit.your_size)) {
    const i = ladder.indexOf(fit.your_size);
    return ladder.slice(Math.max(0, i - 1));
  }
  return [...new Set(set)];
}

function FitBars({ dist }) {
  const tone = ["var(--color-sl-green)", "var(--color-sl-mint-deep)", "var(--color-sl-line)"];
  return (
    <div className="mt-3">
      <div className="flex h-3 rounded-full overflow-hidden ring-1 ring-black/5">
        {dist.map((d, i) => (
          <span key={i} style={{ width: `${d.pct}%`, background: tone[i % tone.length] }} />
        ))}
      </div>
      <div className="mt-2 space-y-1">
        {dist.map((d, i) => (
          <div key={i} className="flex items-center gap-2 text-[11px]">
            <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: tone[i % tone.length] }} />
            <span className="text-sl-muted flex-1 truncate">{d.bucket}</span>
            <span className="font-700 tnum text-sl-ink">{d.pct}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Stars() {
  return (
    <svg viewBox="0 0 24 24" className="w-3.5 h-3.5 text-az-orange" fill="currentColor">
      <path d="M12 2l2.9 6.3 6.9.8-5.1 4.7 1.4 6.8L12 17.8 5.9 20.6l1.4-6.8L2.2 9.1l6.9-.8L12 2Z" />
    </svg>
  );
}
