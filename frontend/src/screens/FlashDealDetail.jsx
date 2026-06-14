import { useState } from "react";
import { api } from "../lib/api";
import TopBar from "../components/TopBar";
import Thumb from "../components/Thumb";
import { FooterAction, SLBadge } from "../components/ui";
import { inr, gradeColor, gradeLabel } from "../lib/format";

// Flash-deal condition detail (MT12 NEW 12) — before a buyer expresses interest they
// see the unit's current-condition photos and the AI grade + confidence that came
// from those photos. Works for neighbour resells AND verified warehouse returns
// (NEW 9). Photos are built from the listing's item_id (the graded unit's photos).
export default function FlashDealDetail({ listing: l, persona, onToast, onBack }) {
  const [interested, setInterested] = useState(false);
  const [busy, setBusy] = useState(false);
  const own = persona && l.owner === persona;
  const sold = l.status === "sold";
  const isReturn = l.source === "return";
  const conf = l.confidence != null ? Math.round(l.confidence * 100) : null;
  const id = l.item_id;
  const photos = id
    ? [`/items/${id}/current_1.jpg`, `/items/${id}/current_2.jpg`, `/items/${id}/day0_1.jpg`]
    : [l.thumb].filter(Boolean);

  async function express() {
    setBusy(true);
    try {
      await api.addInterest(l.listing_id);
      setInterested(true);
      onToast?.({
        title: "Interest sent",
        message: `The seller of ${l.title} has been notified. They’ll confirm the local handoff.`,
      });
    } catch {
      onToast?.({ title: "Couldn’t send interest", message: "Please try again." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="screen-scroll bg-sl-paper">
      <TopBar title="Condition report" subtitle={l.title} onBack={onBack} right={<SLBadge />} />

      {/* condition photos */}
      <div className="px-4 pt-4">
        <p className="text-[11px] font-700 uppercase tracking-wider text-sl-muted mb-2">Current condition</p>
        <div className="grid grid-cols-3 gap-2">
          {photos.map((src, i) => (
            <div key={i} className="relative rounded-xl overflow-hidden ring-1 ring-sl-line">
              <Thumb src={src} alt={`Condition ${i + 1}`} category={l.category} className="w-full h-28" glyphScale={2.2} />
              {i === photos.length - 1 && photos.length > 1 && id && (
                <span className="absolute left-1.5 top-1.5 rounded bg-black/55 text-white text-[9px] font-700 px-1.5 py-0.5">DAY 0</span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* AI grade + confidence */}
      <div className="px-4 pt-4">
        <div className="rounded-2xl bg-white shadow-card ring-1 ring-sl-line p-4 flex items-center gap-4 anim-fade-up">
          {l.grade ? (
            <span
              className="w-14 h-14 rounded-2xl grid place-items-center font-display font-800 text-3xl text-white shrink-0"
              style={{ background: gradeColor(l.grade) }}
            >
              {l.grade}
            </span>
          ) : (
            <span className="w-14 h-14 rounded-2xl grid place-items-center bg-sl-paper text-sl-muted text-[10px] font-700 text-center shrink-0">Not graded</span>
          )}
          <div className="flex-1 min-w-0">
            <p className="text-[11px] font-700 uppercase tracking-wider text-sl-muted">AI condition grade</p>
            <p className="font-display font-800 text-[18px] leading-tight" style={{ color: gradeColor(l.grade) }}>
              {l.grade ? gradeLabel(l.grade) : "Inspect on pickup"}
            </p>
            {conf != null && (
              <p className="text-[12px] text-sl-muted mt-0.5">Prediction confidence · {conf}%</p>
            )}
          </div>
        </div>
        <div className={`mt-2 rounded-xl px-3 py-2.5 ring-1 text-[12.5px] font-600 ${
          isReturn ? "bg-sl-mint ring-sl-mint-deep text-sl-green-deep" : "bg-white ring-sl-line text-sl-muted"
        }`}>
          {isReturn
            ? "Verified warehouse return — graded against the seller's day-0 photos, transferable warranty."
            : "Resold by a neighbour — graded from the photos they uploaded."}
        </div>
      </div>

      {/* price */}
      <div className="px-4 pt-4 pb-2">
        <div className="rounded-2xl bg-az-slate text-white p-4 flex items-center justify-between">
          <div>
            <p className="text-white/55 text-[11px] font-600 uppercase tracking-wider">Asking price</p>
            <p className="font-display font-800 text-[26px] tnum mt-0.5">{inr(l.ask_price)}</p>
          </div>
          <div className="text-right text-white/75 text-[12px] leading-relaxed">
            <p>by {l.owner}</p>
            <p>within {l.range_km} km</p>
          </div>
        </div>
      </div>

      {sold ? (
        <FooterAction variant="secondary" disabled>Sold nearby</FooterAction>
      ) : own ? (
        <FooterAction variant="secondary" disabled>Your listing</FooterAction>
      ) : (
        <FooterAction variant="green" onClick={express} loading={busy} disabled={interested}>
          {interested ? "Interested ✓ · seller notified" : "I’m interested"}
        </FooterAction>
      )}
    </div>
  );
}
