import TopBar from "../components/TopBar";
import Thumb from "../components/Thumb";
import { SLBadge } from "../components/ui";
import { inr } from "../lib/format";

const STATUS = {
  return_initiated: { label: "Return started", cls: "bg-amber-50 text-amber-700 ring-amber-200" },
  idle: { label: "Idle · unused", cls: "bg-slate-100 text-slate-600 ring-slate-200" },
  rto_in_transit: { label: "RTO in transit", cls: "bg-sky-50 text-sky-700 ring-sky-200" },
};

function StageToggle({ value, onChange }) {
  return (
    <div className="flex items-center rounded-full bg-white ring-1 ring-sl-line p-0.5 text-[10px] font-700 leading-none">
      <button
        onClick={() => onChange(false)}
        className={`px-2.5 py-1 rounded-full transition ${!value ? "bg-sl-green text-white" : "text-sl-muted"}`}
      >
        LIVE
      </button>
      <button
        onClick={() => onChange(true)}
        className={`px-2.5 py-1 rounded-full transition ${value ? "bg-az-orange text-az-navy" : "text-sl-muted"}`}
      >
        CACHED
      </button>
    </div>
  );
}

// Ops returns desk (MT10 Fix 2). Two sections only — Returns to process and
// COD refused / RTO. The idle/radar (SL-002) and seller-diagnose (SL-003) lanes
// moved out to the Buyer/Seller views, de-mixing the desk. The SL-001 hero is the
// live-gradeable spine; other return rows (incl. buyer-initiated ones from
// /returns) are display-only "queued for grading".
export default function Inbox({ items, returns, metrics, loading, forceCached, onForceCached, onOpen, onOpenReturn, onShowMetrics, onBack }) {
  const hero = items.find((i) => i.item_id === "SL-001");
  const returnItems = items.filter((i) => i.status === "return_initiated" && i.item_id !== "SL-001");
  const rto = items.filter((i) => i.status === "rto_in_transit");
  const dyn = returns || [];
  const returnsCount = (hero ? 1 : 0) + returnItems.length + dyn.length;

  return (
    <div className="screen-scroll bg-sl-paper">
      <TopBar
        title="Second Life"
        subtitle="Returns desk"
        onBack={onBack}
        right={<StageToggle value={forceCached} onChange={onForceCached} />}
      />

      {/* dormant-value banner → batch impact */}
      <div className="px-4 pt-4">
        <button
          onClick={onShowMetrics}
          className="group relative w-full text-left overflow-hidden rounded-2xl bg-az-slate text-white p-4 shadow-card transition active:scale-[0.99]"
        >
          <div className="absolute -right-6 -top-8 w-28 h-28 rounded-full bg-sl-green/25 blur-2xl" />
          <p className="text-white/55 text-[11px] font-600 uppercase tracking-wider">
            Products without a second chance
          </p>
          <div className="mt-1 flex items-end gap-2">
            <span className="font-display font-800 text-4xl leading-none tnum">{returnsCount || "—"}</span>
            <span className="text-white/70 text-[13px] mb-0.5">items awaiting a second life</span>
          </div>
          {metrics && (
            <p className="mt-2 text-[12px] text-sl-green-soft font-600">
              {inr(metrics.rupees_recovered)} recovered this session ·{" "}
              <span className="text-white/60 font-500">{metrics.warehouse_bypass_pct}% skipped the warehouse</span>
            </p>
          )}
          <span className="mt-2 inline-flex items-center gap-1 text-[11px] font-700 text-az-orange">
            View batch impact
            <svg viewBox="0 0 24 24" className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition" fill="none">
              <path d="M9 5l7 7-7 7" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
        </button>
      </div>

      {/* Section 1 — returns to process */}
      <p className="px-5 pt-5 pb-2 text-[11px] font-700 uppercase tracking-wider text-sl-muted">
        Returns to process
      </p>

      <div className="px-4 space-y-2.5">
        {loading && [0, 1, 2].map((i) => <RowSkeleton key={i} />)}

        {hero && (
          <button
            onClick={() => onOpen(hero)}
            className="group w-full text-left rounded-2xl bg-white ring-1 ring-sl-green/40 shadow-card p-3 flex gap-3 transition hover:ring-sl-green hover:shadow-pop active:scale-[0.99] anim-fade-up"
          >
            <Thumb src={hero.thumb} alt={hero.title} category={hero.category} className="w-[72px] h-[72px] rounded-xl shrink-0" />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5 mb-0.5">
                <SLBadge />
                <span className="text-[10px] font-700 text-az-orange-deep">START HERE</span>
              </div>
              <h3 className="font-600 text-[14px] leading-tight text-sl-ink truncate">{hero.title}</h3>
              <p className="text-[11.5px] text-sl-muted mt-0.5">
                Priya · returned — “{hero.return_reason}”
              </p>
              <div className="mt-1.5 flex items-center gap-2">
                <StatusChip status={hero.status} />
                <span className="text-[11px] text-sl-muted">Paid {inr(hero.order?.price_paid ?? hero.mrp)}</span>
              </div>
            </div>
            <Chevron />
          </button>
        )}

        {/* static return-class items (display-only, queued for grading) */}
        {returnItems.map((it, idx) => (
          <QueuedReturn
            key={it.item_id}
            title={it.title}
            category={it.category}
            thumb={it.thumb}
            reason={it.return_reason}
            price={it.order?.price_paid ?? it.mrp}
            delay={60 + idx * 50}
          />
        ))}

        {/* dynamic returns from /returns (seeded extras + buyer-initiated). Rows that
            resolve to a catalog item (item_id) are inspectable → tap to grade. */}
        {dyn.map((r, idx) =>
          r.item_id && onOpenReturn ? (
            <GradeableReturn
              key={r.return_id}
              row={r}
              onOpen={() => onOpenReturn(r)}
              delay={120 + idx * 45}
            />
          ) : (
            <QueuedReturn
              key={r.return_id}
              title={r.title}
              category={r.category}
              thumb={r.thumb}
              reason={r.return_reason}
              price={r.price_paid}
              buyer={r.source === "buyer"}
              delay={120 + idx * 45}
            />
          )
        )}

        {!loading && returnsCount === 0 && (
          <p className="text-[12.5px] text-sl-muted px-1 py-4">No returns waiting.</p>
        )}
      </div>

      {/* Section 2 — COD refused / RTO */}
      {rto.length > 0 && (
        <>
          <p className="px-5 pt-6 pb-2 text-[11px] font-700 uppercase tracking-wider text-sl-muted">
            COD refused / RTO
          </p>
          <div className="px-4 space-y-2.5 pb-8">
            {rto.map((it, idx) => (
              <button
                key={it.item_id}
                onClick={() => onOpen(it)}
                className="group w-full text-left rounded-2xl bg-white ring-1 ring-sl-line shadow-card p-3 flex gap-3 transition hover:ring-emerald-300 hover:shadow-pop active:scale-[0.99] anim-fade-up"
                style={{ animationDelay: `${idx * 50}ms` }}
              >
                <Thumb src={it.thumb} alt={it.title} category={it.category} className="w-[60px] h-[60px] rounded-xl shrink-0" />
                <div className="min-w-0 flex-1">
                  <span className="inline-block rounded-full px-2 py-0.5 text-[9.5px] font-800 tracking-wide ring-1 bg-emerald-50 text-emerald-700 ring-emerald-200">
                    RTO · SEALED
                  </span>
                  <h3 className="font-600 text-[13.5px] leading-tight text-sl-ink truncate mt-1">{it.title}</h3>
                  <p className="text-[11px] text-sl-muted mt-0.5 leading-snug truncate">
                    {it.return_reason || "delivery refused"} · sealed box — re-offer locally, no scan
                  </p>
                </div>
                <Chevron />
              </button>
            ))}
          </div>
        </>
      )}

      <div className="pb-8" />
    </div>
  );
}

// A display-only return row (not live-gradeable) — keeps the desk bulletproof on
// photoless items. Buyer-initiated rows get a distinguishing chip.
function QueuedReturn({ title, category, thumb, reason, price, buyer, delay }) {
  return (
    <div
      className="rounded-2xl bg-white/80 ring-1 ring-sl-line p-3 flex gap-3 anim-fade-up"
      style={{ animationDelay: `${delay}ms` }}
    >
      <Thumb src={thumb} alt={title} category={category} className="w-14 h-14 rounded-xl shrink-0 opacity-95" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          {buyer && (
            <span className="inline-block rounded-full px-2 py-0.5 text-[9px] font-800 tracking-wide ring-1 bg-sl-mint text-sl-green-deep ring-sl-green/30">
              BUYER RETURN
            </span>
          )}
          <h3 className="font-600 text-[13px] leading-tight text-sl-ink/85 truncate">{title}</h3>
        </div>
        {reason && <p className="text-[11px] text-sl-muted mt-0.5 truncate">“{reason}”</p>}
        {price != null && <p className="text-[11px] text-sl-muted mt-0.5">Paid {inr(price)}</p>}
      </div>
      <span className="self-center text-[10px] font-700 text-sl-muted bg-sl-paper rounded-full px-2 py-1 ring-1 ring-sl-line shrink-0">
        QUEUED
      </span>
    </div>
  );
}

// A buyer-initiated return that resolves to a catalog item → tappable into the
// grading spine (inspect → grade → route → Health Card), like the hero.
function GradeableReturn({ row, onOpen, delay }) {
  return (
    <button
      onClick={onOpen}
      className="group w-full text-left rounded-2xl bg-white ring-1 ring-sl-green/40 shadow-card p-3 flex gap-3 transition hover:ring-sl-green hover:shadow-pop active:scale-[0.99] anim-fade-up"
      style={{ animationDelay: `${delay}ms` }}
    >
      <Thumb src={row.thumb} alt={row.title} category={row.category} className="w-[60px] h-[60px] rounded-xl shrink-0" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          {row.source === "buyer" && (
            <span className="inline-block rounded-full px-2 py-0.5 text-[9px] font-800 tracking-wide ring-1 bg-sl-mint text-sl-green-deep ring-sl-green/30">
              BUYER RETURN
            </span>
          )}
          <h3 className="font-600 text-[13px] leading-tight text-sl-ink truncate">{row.title}</h3>
        </div>
        {row.return_reason && <p className="text-[11px] text-sl-muted mt-0.5 truncate">“{row.return_reason}”</p>}
        <span className="mt-1 inline-flex items-center gap-1 text-[10.5px] font-700 text-sl-green-deep">
          Inspect &amp; grade
          <svg viewBox="0 0 24 24" className="w-3 h-3 group-hover:translate-x-0.5 transition" fill="none">
            <path d="M9 5l7 7-7 7" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
      </div>
      <Chevron />
    </button>
  );
}

function Chevron() {
  return (
    <svg viewBox="0 0 24 24" className="w-5 h-5 text-sl-muted self-center shrink-0 group-hover:translate-x-0.5 transition" fill="none">
      <path d="M9 5l7 7-7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function StatusChip({ status }) {
  const s = STATUS[status] || { label: status, cls: "bg-slate-100 text-slate-600 ring-slate-200" };
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-700 ring-1 ${s.cls}`}>
      {s.label}
    </span>
  );
}

function RowSkeleton() {
  return (
    <div className="rounded-2xl bg-white p-3 flex gap-3 ring-1 ring-sl-line">
      <div className="skel w-[72px] h-[72px] rounded-xl" />
      <div className="flex-1 space-y-2 py-1">
        <div className="skel h-3 w-3/4 rounded" />
        <div className="skel h-2.5 w-1/2 rounded" />
        <div className="skel h-2.5 w-1/3 rounded" />
      </div>
    </div>
  );
}
