import { Fragment, useEffect, useState } from "react";
import TopBar from "../components/TopBar";
import { FooterAction } from "../components/ui";
import { inr, signedInr, useCountUp } from "../lib/format";

const META = {
  local_p2p: { label: "Local peer-to-peer", glyph: "📍" },
  warehouse_relist: { label: "Amazon warehouse relist", glyph: "🏭" },
  refurbish: { label: "Refurbish & certify", glyph: "🛠️" },
  donate: { label: "Donate · CSR credit", glyph: "🤝" },
  liquidate: { label: "Bulk liquidation", glyph: "📦" },
  rto_relist: { label: "RTO sealed relist", glyph: "📮" },
};

const prettyKey = (k) =>
  k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()).replace("Csr", "CSR").replace("Fc", "FC");

export default function RouteScreen({ route, cascade, building, onHealthCard, onBack, nextLabel = "Generate Product Health Card", nextHint = "Every figure above sums from a deterministic ledger" }) {
  const paths = [...route.paths].sort((a, b) => b.recovery - a.recovery);
  const winner = route.paths.find((p) => p.winner) || paths[0];
  const warehouse = route.paths.find((p) => p.path === "warehouse_relist");
  const swing = warehouse ? winner.recovery - warehouse.recovery : null;
  const maxAbs = Math.max(...route.paths.map((p) => Math.abs(p.recovery)), 1);

  return (
    <div className="screen-scroll bg-sl-paper">
      <TopBar title="Value Recovery Score" subtitle="6 paths · highest rupee wins" onBack={onBack} />

      {/* winner hero */}
      <div className="px-4 pt-4">
        <WinnerCard winner={winner} />
      </div>

      {/* defeat banner */}
      {warehouse && (
        <div className="px-4 pt-3">
          <div className="rounded-xl bg-az-slate text-white px-3.5 py-2.5 flex items-center gap-2.5 anim-fade-up" style={{ animationDelay: "120ms" }}>
            <span className="text-lg">⚔️</span>
            <p className="text-[12.5px] leading-snug">
              The warehouse route <span className="font-700 text-[#ff9b8a]">{signedInr(warehouse.recovery)}</span> — beaten by a{" "}
              <span className="font-700 text-sl-green-soft">{inr(Math.abs(swing))} swing</span> per item.
            </p>
          </div>
        </div>
      )}

      {/* all six routes */}
      <div className="px-4 pt-5">
        <p className="text-[11px] font-700 uppercase tracking-wider text-sl-muted mb-2.5">All six routes, ranked</p>
        <div className="space-y-2.5">
          {paths.map((p, i) => (
            <PathRow key={p.path} p={p} maxAbs={maxAbs} delay={i * 80} defaultOpen={p.winner} />
          ))}
        </div>
      </div>

      {/* MT8 — derived terminal-state cascade */}
      <CascadeStrip cascade={cascade} />

      {/* impact */}
      <div className="px-4 pt-5 pb-2">
        <div className="grid grid-cols-2 gap-2.5">
          <Impact value={`${route.co2_saved_kg} kg`} label="CO₂ saved vs warehouse" glyph="🌱" />
          <Impact value={`${route.km_saved} km`} label="reverse-logistics avoided" glyph="🚚" />
        </div>
      </div>

      <FooterAction onClick={onHealthCard} loading={building} hint={nextHint}>
        {nextLabel}
        <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none">
          <path d="M9 5l7 7-7 7" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </FooterAction>
    </div>
  );
}

function WinnerCard({ winner }) {
  const v = Math.round(useCountUp(winner.recovery));
  const m = META[winner.path] || { label: winner.path, glyph: "•" };
  return (
    <div className="relative rounded-2xl bg-white p-4 anim-winner overflow-hidden">
      <span className="absolute right-0 top-0 bg-sl-green text-white text-[10px] font-800 tracking-wider px-3 py-1 rounded-bl-xl">
        WINNER
      </span>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xl">{m.glyph}</span>
        <span className="font-700 text-[14px] text-sl-ink">{m.label}</span>
      </div>
      <div className="flex items-end gap-2">
        <span className="font-display font-800 text-[40px] leading-none tnum text-sl-green-deep">
          {signedInr(v)}
        </span>
        <span className="text-[12px] text-sl-muted mb-1.5">recovered</span>
      </div>
      {winner.note && (
        <p className="mt-1.5 text-[12.5px] text-sl-green-deep font-600">
          {winner.note}
          {winner.distance_km != null && ` · nearest ${winner.distance_km} km`}
        </p>
      )}
      {winner.dark_store && (
        <div className="mt-2.5 inline-flex items-center gap-2 rounded-lg bg-sl-mint/60 ring-1 ring-sl-green/30 px-2.5 py-1.5">
          <span className="text-[14px]">🏪</span>
          <span className="text-[12px] leading-tight text-sl-green-deep">
            Lists open-box at <span className="font-700">{winner.dark_store.name}</span>
            <span className="text-sl-green-deep/70"> · {winner.dark_store.distance_km} km</span>
          </span>
        </div>
      )}
      {winner.breakdown && <Breakdown breakdown={winner.breakdown} total={winner.recovery} />}
    </div>
  );
}

function PathRow({ p, maxAbs, delay, defaultOpen }) {
  const [open, setOpen] = useState(!!defaultOpen);
  const [grown, setGrown] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setGrown(true), delay + 120);
    return () => clearTimeout(t);
  }, [delay]);

  const pct = (Math.abs(p.recovery) / maxAbs) * 50; // half-track
  const pos = p.recovery >= 0;
  const m = META[p.path] || { label: p.path, glyph: "•" };
  const hasBreak = p.breakdown && Object.keys(p.breakdown).length > 0;

  return (
    <div
      className={`rounded-xl ring-1 p-3 anim-fade-up ${
        p.winner ? "bg-sl-mint/50 ring-sl-green/50" : p.eligible ? "bg-white ring-sl-line" : "bg-white/60 ring-sl-line"
      }`}
      style={{ animationDelay: `${delay}ms` }}
    >
      <button
        className="w-full flex items-center gap-2.5 text-left"
        onClick={() => hasBreak && setOpen((o) => !o)}
        disabled={!hasBreak}
      >
        <span className={`text-base ${!p.eligible && "opacity-40"}`}>{m.glyph}</span>
        <span className={`flex-1 min-w-0 text-[13px] font-600 truncate ${p.eligible ? "text-sl-ink" : "text-sl-muted"}`}>
          {m.label}
          {p.winner && <span className="ml-1.5 text-[10px] font-800 text-sl-green-deep">★</span>}
        </span>
        <span
          className="text-[13.5px] font-700 tnum tabular-nums shrink-0"
          style={{ color: !p.eligible ? "var(--color-sl-muted)" : pos ? "var(--color-pos)" : "var(--color-neg)" }}
        >
          {p.eligible ? signedInr(p.recovery) : "—"}
        </span>
        {hasBreak && (
          <svg viewBox="0 0 24 24" className={`w-4 h-4 text-sl-muted shrink-0 transition ${open ? "rotate-180" : ""}`} fill="none">
            <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
      </button>

      {/* diverging bar */}
      <div className="relative h-2.5 mt-2 rounded-full bg-sl-paper overflow-hidden">
        <span className="absolute left-1/2 top-0 bottom-0 w-px bg-sl-line" />
        {p.eligible && (
          <span
            className="absolute top-0 bottom-0 rounded-full transition-[width] duration-700 ease-out"
            style={{
              width: grown ? `${pct}%` : "0%",
              [pos ? "left" : "right"]: "50%",
              background: pos ? "var(--color-pos)" : "var(--color-neg)",
            }}
          />
        )}
      </div>

      {!p.eligible && p.note && <p className="text-[11px] text-sl-muted mt-1.5 italic">{p.note}</p>}

      {open && hasBreak && <Breakdown breakdown={p.breakdown} total={p.recovery} compact />}
    </div>
  );
}

function Breakdown({ breakdown, total, compact }) {
  const entries = Object.entries(breakdown);
  return (
    <div className={`mt-3 rounded-lg ${compact ? "bg-sl-paper" : "bg-sl-paper/70 ring-1 ring-sl-line"} p-2.5`}>
      {entries.map(([k, v]) => (
        <div key={k} className="flex items-center justify-between py-0.5 text-[12px]">
          <span className="text-sl-muted">{prettyKey(k)}</span>
          <span className="tnum font-600" style={{ color: v >= 0 ? "var(--color-pos)" : "var(--color-neg)" }}>
            {signedInr(v)}
          </span>
        </div>
      ))}
      <div className="mt-1 pt-1.5 border-t border-sl-line flex items-center justify-between text-[12.5px]">
        <span className="font-700 text-sl-ink">Net recovery</span>
        <span className="tnum font-800" style={{ color: total >= 0 ? "var(--color-pos)" : "var(--color-neg)" }}>
          {signedInr(total)}
        </span>
      </div>
    </div>
  );
}

// The derived value cascade: the same VRS argmax re-run week-by-week as the price
// decays. Each tier is where the money math sends the item next — the visible answer
// to "what happens to items that don't sell at the local open-box node?"
function CascadeStrip({ cascade }) {
  if (!cascade || !cascade.tiers || cascade.tiers.length === 0) return null;
  return (
    <div className="px-4 pt-6">
      <p className="text-[11px] font-700 uppercase tracking-wider text-sl-muted mb-1">
        If it doesn't sell locally — the value cascade
      </p>
      <p className="text-[11.5px] text-sl-muted mb-3 leading-snug">
        Derived live: the engine re-runs the same argmax each week as the price decays{" "}
        {cascade.decay_pct_per_week}%/wk. No fixed timeline — each step is where the math sends it next.
      </p>
      <div className="flex items-stretch gap-1.5 overflow-x-auto pb-1 -mx-1 px-1">
        {cascade.tiers.map((t, i) => (
          <Fragment key={t.week}>
            {i > 0 && (
              <span className="self-center shrink-0 text-sl-muted">
                <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none">
                  <path d="M9 5l7 7-7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </span>
            )}
            <TierCard t={t} delay={i * 90} />
          </Fragment>
        ))}
      </div>
    </div>
  );
}

function TierCard({ t, delay }) {
  const terminal = !!t.terminal;
  return (
    <div
      className={`shrink-0 min-w-[148px] rounded-xl ring-1 p-2.5 anim-fade-up ${
        terminal ? "bg-sl-mint/50 ring-sl-green/45" : "bg-white ring-sl-line"
      }`}
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-800 tracking-wide text-sl-muted">WEEK {t.week}</span>
        {terminal && <span className="text-[9px] font-800 text-sl-green-deep tracking-wide">TERMINAL</span>}
      </div>
      <p className="mt-1 text-[12px] font-700 text-sl-ink leading-tight">{t.label}</p>
      <div className="mt-1.5 flex items-baseline gap-1.5">
        <span className="font-display font-800 text-[16px] tnum text-sl-green-deep">{signedInr(t.net)}</span>
        {t.price > 0 && <span className="text-[10.5px] text-sl-muted">at {inr(t.price)}</span>}
      </div>
    </div>
  );
}

function Impact({ value, label, glyph }) {
  return (
    <div className="rounded-xl bg-white ring-1 ring-sl-line p-3">
      <div className="flex items-center gap-1.5">
        <span>{glyph}</span>
        <span className="font-display font-800 text-[17px] tnum text-sl-green-deep">{value}</span>
      </div>
      <p className="text-[11px] text-sl-muted mt-0.5 leading-tight">{label}</p>
    </div>
  );
}
