import { useRef, useState } from "react";
import TopBar from "../components/TopBar";
import Thumb from "../components/Thumb";
import { FooterAction, SLBadge } from "../components/ui";
import { inr } from "../lib/format";
import { fileToGradeImage } from "../lib/image";

const MAX_IMAGES = 3;

// Resell step 1 (MT10 Fix 4) — confirm the purchase details, then upload current
// photos. The AI grades the uploaded photos (reusing /grade current_images); that
// grade drives the suggested resale price on the next screen. Two stages in one
// screen: "details" → "photos".
export default function ResellConfirm({ order, item, busy, quotePreview, onGrade, onBack }) {
  const [stage, setStage] = useState("details");
  const [images, setImages] = useState([]);
  const [dragOver, setDragOver] = useState(false);
  const [busyFiles, setBusyFiles] = useState(false);
  const [uploadErr, setUploadErr] = useState(null);
  const inputRef = useRef(null);

  async function addFiles(fileList) {
    setUploadErr(null);
    const files = Array.from(fileList).filter((f) => f.type.startsWith("image/"));
    if (!files.length) return;
    setBusyFiles(true);
    try {
      const room = MAX_IMAGES - images.length;
      const next = [];
      for (const f of files.slice(0, room)) next.push(await fileToGradeImage(f));
      setImages((prev) => [...prev, ...next].slice(0, MAX_IMAGES));
    } catch (e) {
      setUploadErr(e.message || "Could not read that image.");
    } finally {
      setBusyFiles(false);
    }
  }

  const est = quotePreview?.ai_suggested;

  return (
    <div className="screen-scroll bg-sl-paper">
      <TopBar title="Resell on Second Life" subtitle={item.title} onBack={onBack} right={<SLBadge />} />

      {/* the purchase, as we have it on record */}
      <div className="px-4 pt-4">
        <div className="rounded-2xl bg-white shadow-card ring-1 ring-sl-line p-4 anim-fade-up">
          <div className="flex gap-3">
            <Thumb src={item.thumb} alt={item.title} category={item.category} className="w-16 h-16 rounded-xl shrink-0" />
            <div className="min-w-0 flex-1">
              <h2 className="font-600 text-[14px] leading-tight text-sl-ink">{item.title}</h2>
              <p className="text-[11px] text-sl-muted mt-0.5 capitalize">{item.category}</p>
            </div>
          </div>
          <div className="mt-3 divide-y divide-sl-line">
            <Row label="You paid" value={inr(order?.price_paid ?? item.mrp)} />
            <Row label="Bought on" value={fmtDate(order?.purchase_date)} />
            <Row label="Warranty on record" value={`${item.warranty_months ?? 0} months`} />
            {est != null && (
              <Row
                label="Estimated resale"
                value={<span className="text-sl-green-deep font-800">~{inr(est)}</span>}
              />
            )}
          </div>
          <p className="mt-3 text-[11.5px] text-sl-muted leading-snug">
            We’ll confirm the real price from photos of the unit’s current condition — buyers pay for
            what they can see.
          </p>
        </div>
      </div>

      {stage === "photos" && (
        <div className="px-4 pt-4">
          <p className="text-[11px] font-700 uppercase tracking-wider text-sl-muted mb-2">Photograph the unit</p>
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => { e.preventDefault(); setDragOver(false); addFiles(e.dataTransfer.files); }}
            className={`rounded-2xl border-2 border-dashed p-4 transition ${dragOver ? "border-sl-green bg-sl-mint/40" : "border-sl-line bg-white"}`}
          >
            <div className="flex items-center gap-3">
              <button
                onClick={() => inputRef.current?.click()}
                disabled={images.length >= MAX_IMAGES || busyFiles || busy}
                className="shrink-0 h-10 px-4 rounded-lg bg-az-slate text-white text-[13px] font-700 hover:bg-az-navy transition active:scale-[0.98] disabled:opacity-50"
              >
                {busyFiles ? "Reading…" : "Upload photos"}
              </button>
              <p className="text-[12px] text-sl-muted leading-snug">
                Drag &amp; drop or pick the unit’s photos.{" "}
                <span className="text-sl-ink font-600">{images.length}/{MAX_IMAGES}</span> added.
              </p>
            </div>
            <input ref={inputRef} type="file" accept="image/*" multiple className="hidden"
              onChange={(e) => { addFiles(e.target.files); e.target.value = ""; }} />
            {images.length > 0 && (
              <div className="mt-3 flex gap-2">
                {images.map((im, i) => (
                  <div key={i} className="relative">
                    <img src={im.preview} alt={`Upload ${i + 1}`} className="w-16 h-16 rounded-lg object-cover ring-1 ring-sl-line" />
                    <button
                      onClick={() => setImages((prev) => prev.filter((_, j) => j !== i))}
                      disabled={busy}
                      aria-label="Remove"
                      className="absolute -top-1.5 -right-1.5 w-5 h-5 grid place-items-center rounded-full bg-white ring-1 ring-sl-line text-sl-muted hover:text-neg transition disabled:opacity-50"
                    >
                      <svg viewBox="0 0 24 24" className="w-3 h-3" fill="none"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" /></svg>
                    </button>
                  </div>
                ))}
              </div>
            )}
            {uploadErr && <p className="mt-2 text-[12px] text-neg font-600">{uploadErr}</p>}
          </div>
          <p className="mt-2 text-[11.5px] text-sl-muted leading-relaxed px-1">
            {images.length
              ? "Nova-2 grades your photos live → a fair resale price. We verify it’s the item you bought."
              : "Upload at least one photo of the actual unit — we grade it and confirm it matches your order."}
          </p>
        </div>
      )}

      {stage === "details" ? (
        <FooterAction variant="green" onClick={() => setStage("photos")}>
          Continue to photos
        </FooterAction>
      ) : (
        <FooterAction
          variant="green"
          onClick={() => onGrade(images.map((im) => im.b64))}
          disabled={images.length === 0}
          loading={busy}
          hint={busy ? undefined : images.length ? "AI sets the price from the condition" : "Upload a photo to continue"}
        >
          {busy ? "Pricing…" : images.length ? "Get AI price" : "Upload to continue"}
        </FooterAction>
      )}
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex items-center justify-between py-2.5">
      <span className="text-[12px] text-sl-muted">{label}</span>
      <span className="text-[13px] font-600 text-sl-ink text-right">{value}</span>
    </div>
  );
}

function fmtDate(d) {
  if (!d) return "—";
  try {
    return new Date(d).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
  } catch {
    return d;
  }
}
