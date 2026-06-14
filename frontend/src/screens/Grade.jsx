import { useEffect, useState } from "react";
import TopBar from "../components/TopBar";
import Thumb from "../components/Thumb";
import { FooterAction, SourceTag } from "../components/ui";
import { gradeColor, gradeLabel } from "../lib/format";

const SEV = {
  minor: { cls: "bg-slate-100 text-slate-600", dot: "#94a3b8" },
  moderate: { cls: "bg-amber-50 text-amber-700", dot: "var(--color-warn)" },
  major: { cls: "bg-red-50 text-red-700", dot: "var(--color-neg)" },
};

export default function Grade({ item, grade, previews, routing, onRoute, onBack }) {
  const id = item.item_id;
  const conf = Math.round((grade.confidence ?? 0) * 100);
  const su = grade.same_unit || {};
  // NEW 6 — the NOW tile shows the photo the agent uploaded, not a seeded file.
  const nowSrc = (previews && previews[0]) || `/items/${id}/current_1.jpg`;

  return (
    <div className="screen-scroll bg-sl-paper">
      <TopBar
        title="Delta-grade report"
        subtitle={item.title}
        onBack={onBack}
        right={<SourceTag source={grade.source} model={grade.model} latency={grade.latency_ms} />}
      />

      {/* grade headline */}
      <div className="px-4 pt-4">
        <div className="rounded-2xl bg-white shadow-card ring-1 ring-sl-line p-4 flex items-center gap-4 anim-fade-up">
          <GradeMedal grade={grade.grade} />
          <div className="flex-1 min-w-0">
            <p className="text-[11px] font-700 uppercase tracking-wider text-sl-muted">Condition grade</p>
            <p className="font-display font-800 text-[20px] leading-tight" style={{ color: gradeColor(grade.grade) }}>
              {gradeLabel(grade.grade)}
            </p>
            <p className="text-[12px] text-sl-muted mt-0.5">
              {grade.usage_detected ? "Usage detected" : "No usage detected"} · {grade.defects?.length || 0} defect
              {(grade.defects?.length || 0) === 1 ? "" : "s"} found
            </p>
          </div>
          <ConfidenceRing value={conf} />
        </div>
      </div>

      {/* fault attribution (NEW 10) + same-unit verdict */}
      <div className="px-4 pt-3 space-y-2">
        <FaultBanner fault={grade.fault_attribution} returnable={grade.returnable} />
        <SameUnit verified={su.verified} confidence={su.confidence} />
      </div>

      {/* before / after */}
      <div className="px-4 pt-3">
        <p className="text-[11px] font-700 uppercase tracking-wider text-sl-muted mb-2">Day-0 vs now</p>
        <div className="grid grid-cols-2 gap-2">
          <CompareTile src={`/items/${id}/day0_1.jpg`} cat={item.category} tag="DAY 0" tone="neutral" />
          <CompareTile src={nowSrc} cat={item.category} tag="NOW · UPLOADED" tone="alert" />
        </div>
      </div>

      {/* defects */}
      <div className="px-4 pt-4">
        <p className="text-[11px] font-700 uppercase tracking-wider text-sl-muted mb-2">What changed</p>
        <div className="space-y-2">
          {(grade.defects || []).map((d, i) => {
            const sev = SEV[d.severity] || SEV.minor;
            return (
              <div
                key={i}
                className="rounded-xl bg-white ring-1 ring-sl-line p-3 flex gap-3 anim-fade-up"
                style={{ animationDelay: `${i * 70}ms` }}
              >
                <span className="mt-1 w-2 h-2 rounded-full shrink-0" style={{ background: sev.dot }} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-700 text-[13px] text-sl-ink capitalize">{d.area}</span>
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-700 capitalize ${sev.cls}`}>
                      {d.severity}
                    </span>
                  </div>
                  <p className="text-[12.5px] text-sl-muted leading-snug mt-0.5">{d.description}</p>
                </div>
              </div>
            );
          })}
          {(!grade.defects || grade.defects.length === 0) && (
            <p className="text-[13px] text-sl-muted">No defects detected — grades as like-new.</p>
          )}
        </div>
      </div>

      {/* completeness */}
      {grade.completeness?.length > 0 && (
        <div className="px-4 pt-4">
          <p className="text-[11px] font-700 uppercase tracking-wider text-sl-muted mb-2">In the box</p>
          <div className="rounded-xl bg-white ring-1 ring-sl-line p-3 grid grid-cols-2 gap-2">
            {grade.completeness.map((c, i) => (
              <div key={i} className="flex items-center gap-2 text-[12.5px]">
                {c.present ? <Tick ok /> : <Tick />}
                <span className={c.present ? "text-sl-ink" : "text-sl-muted line-through"}>{c.item}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* justification */}
      <div className="px-4 pt-4 pb-2">
        <div className="rounded-xl bg-sl-mint/60 ring-1 ring-sl-mint-deep p-3">
          <p className="text-[11px] font-700 text-sl-green-deep mb-1">AI assessment</p>
          <p className="text-[13px] text-sl-ink leading-relaxed">“{grade.justification}”</p>
        </div>
        {grade.needs_human_review && (
          <p className="mt-2 text-[12px] text-warn font-600">
            ⚑ {grade.review_reason || "Flagged for human review."}
          </p>
        )}
      </div>

      <FooterAction onClick={onRoute} loading={routing} hint="Money math is deterministic — not the LLM">
        See best recovery path
        <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none">
          <path d="M9 5l7 7-7 7" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </FooterAction>
    </div>
  );
}

function GradeMedal({ grade }) {
  const c = gradeColor(grade);
  return (
    <div className="relative shrink-0 anim-pop">
      <div
        className="w-16 h-16 rounded-2xl grid place-items-center font-display font-800 text-4xl text-white"
        style={{ background: c, boxShadow: `0 10px 24px -10px ${c}` }}
      >
        {grade}
      </div>
    </div>
  );
}

function ConfidenceRing({ value }) {
  const [v, setV] = useState(0);
  useEffect(() => {
    const t = setTimeout(() => setV(value), 60);
    return () => clearTimeout(t);
  }, [value]);
  const r = 22;
  const circ = 2 * Math.PI * r;
  return (
    <div className="flex flex-col items-center shrink-0 w-[72px]">
      <div className="relative w-[60px] h-[60px]">
        <svg viewBox="0 0 60 60" className="w-full h-full -rotate-90">
          <circle cx="30" cy="30" r={r} fill="none" stroke="var(--color-sl-line)" strokeWidth="6" />
          <circle
            cx="30"
            cy="30"
            r={r}
            fill="none"
            stroke="var(--color-sl-green)"
            strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray={circ}
            strokeDashoffset={circ - (circ * v) / 100}
            style={{ transition: "stroke-dashoffset 1s cubic-bezier(0.22,1,0.36,1)" }}
          />
        </svg>
        <div className="absolute inset-0 grid place-items-center">
          <span className="font-display font-700 text-[15px] tnum text-sl-ink">{value}%</span>
        </div>
      </div>
      <span className="mt-1 text-center text-[9px] font-600 text-sl-muted leading-tight">Prediction<br />confidence</span>
    </div>
  );
}

// NEW 10 — fault attribution banner. Seller fault = catalog ≠ day-0 (buyer can still
// return); customer fault = the returned unit ≠ what was delivered (not returnable).
function FaultBanner({ fault, returnable }) {
  if (fault === "seller") {
    return (
      <div className="rounded-xl bg-amber-50 ring-1 ring-amber-200 px-3 py-2.5 flex items-start gap-2.5">
        <span className="text-amber-500 text-lg leading-none">⚑</span>
        <p className="text-[12.5px] text-amber-800 font-600">
          Seller’s fault — the catalog photo doesn’t match the unit that was delivered. Return accepted; flagged to the seller.
        </p>
      </div>
    );
  }
  if (fault === "customer") {
    return (
      <div className="rounded-xl bg-red-50 ring-1 ring-red-200 px-3 py-2.5 flex items-start gap-2.5">
        <span className="text-red-500 text-lg leading-none">⛔</span>
        <p className="text-[12.5px] text-red-700 font-600">
          Customer’s fault — this isn’t the unit that was delivered.{" "}
          {returnable === false && "Not eligible for return — "}flagged for human review.
        </p>
      </div>
    );
  }
  return null;
}

function SameUnit({ verified, confidence }) {
  const pct = Math.round((confidence ?? 0) * 100);
  if (verified) {
    return (
      <div className="rounded-xl bg-sl-mint ring-1 ring-sl-mint-deep px-3 py-2.5 flex items-center gap-2.5">
        <ShieldCheck />
        <p className="text-[12.5px] text-sl-green-deep font-600">
          Same physical unit verified — matches day-0 photos ({pct}% sure)
        </p>
      </div>
    );
  }
  return (
    <div className="rounded-xl bg-amber-50 ring-1 ring-amber-200 px-3 py-2.5 flex items-center gap-2.5">
      <span className="text-amber-500 text-lg leading-none">⚑</span>
      <p className="text-[12.5px] text-amber-800 font-600">
        Same-unit match inconclusive — routed with a human-review flag
      </p>
    </div>
  );
}

function CompareTile({ src, cat, tag, tone }) {
  return (
    <div className="relative rounded-xl overflow-hidden ring-1 ring-sl-line">
      <Thumb src={src} alt={tag} category={cat} className="w-full h-32" glyphScale={2.4} />
      <span
        className="absolute left-2 top-2 rounded-md px-2 py-0.5 text-[10px] font-700 text-white"
        style={{ background: tone === "alert" ? "rgba(200,85,61,0.92)" : "rgba(27,33,31,0.7)" }}
      >
        {tag}
      </span>
    </div>
  );
}

function Tick({ ok }) {
  return ok ? (
    <svg viewBox="0 0 24 24" className="w-4 h-4 text-sl-green shrink-0" fill="none">
      <path d="M5 12l4.5 4.5L19 7" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ) : (
    <svg viewBox="0 0 24 24" className="w-4 h-4 text-sl-muted shrink-0" fill="none">
      <path d="M7 7l10 10M17 7L7 17" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function ShieldCheck() {
  return (
    <svg viewBox="0 0 24 24" className="w-5 h-5 text-sl-green-deep shrink-0" fill="none">
      <path d="M12 3l7 3v5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3Z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
      <path d="M9 12l2 2 4-4" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
