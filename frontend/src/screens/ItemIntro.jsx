import { useEffect, useRef, useState } from "react";
import TopBar from "../components/TopBar";
import Thumb from "../components/Thumb";
import { FooterAction, SLBadge } from "../components/ui";
import { inr } from "../lib/format";
import { fileToGradeImage } from "../lib/image";

const SCAN_STEPS = [
  "Loading day-0 birth-certificate photos…",
  "Aligning current condition to original…",
  "Detecting wear, defects & completeness…",
  "Verifying this is the same physical unit…",
  "Scoring grade & confidence…",
];
const MAX_IMAGES = 3;

// Returns-desk scan station (MT9, two-pane web). LEFT = the day-0 baseline the AI
// compares against. RIGHT = the agent uploads the unit's CURRENT photos (graded live)
// — or, with no upload, the photos on file are used. The downstream grade→route→card
// →radar spine is unchanged.
export default function ItemIntro({ item, scanning, onScan, onBack }) {
  const id = item.item_id;
  const day0 = [`/items/${id}/day0_1.jpg`, `/items/${id}/day0_2.jpg`];
  const ord = item.order || {};

  const [images, setImages] = useState([]); // [{ b64, preview }]
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

  const hasUpload = images.length > 0;
  const heroPreview = hasUpload ? images[0].preview : null;

  return (
    <div className="screen-page">
      <TopBar title="Returns desk · scan station" subtitle={item.title} onBack={onBack} right={<SLBadge />} />

      <p className="text-[13px] text-sl-muted leading-relaxed mb-4 max-w-2xl">
        The returns agent scans the unit at handoff. <span className="text-sl-ink font-600">Upload its
        current condition</span> on the right — the AI grades those photos against the{" "}
        <span className="text-sl-ink font-600">day-0 baseline the seller clicked at listing</span>, so the
        score is about <span className="text-sl-ink font-600">this exact unit</span>, not a generic
        catalog photo.
      </p>

      <div className="grid gap-4 md:grid-cols-2 items-start">
        {/* LEFT — day-0 baseline + provenance */}
        <div className="space-y-3">
          <div className="rounded-2xl bg-white shadow-card ring-1 ring-sl-line p-4">
            <div className="flex items-center justify-between mb-2.5">
              <div className="flex items-center gap-1.5">
                <SLBadge />
                <span className="text-[12px] font-700 text-sl-ink">Day-0 birth certificate</span>
              </div>
              <span className="text-[10px] font-700 text-sl-green-deep bg-sl-mint rounded-full px-2 py-0.5">ON FILE</span>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <Thumb src={`/items/${id}/catalog.jpg`} alt="Catalog photo" category={item.category} className="h-24 rounded-lg ring-1 ring-sl-line" />
              {day0.map((src, i) => (
                <Thumb key={i} src={src} alt={`Day-0 photo ${i + 1}`} category={item.category} className="h-24 rounded-lg ring-1 ring-sl-line" />
              ))}
            </div>
            <p className="mt-2.5 text-[12px] text-sl-muted leading-relaxed">
              Catalog + the photos <span className="text-sl-ink font-600">clicked by the seller</span> at
              listing. The AI grades wear <span className="text-sl-ink font-600">against these</span>.
            </p>
          </div>

          <div className="rounded-2xl bg-white shadow-card ring-1 ring-sl-line divide-y divide-sl-line">
            <Row label="Order" value={ord.order_id || "—"} mono />
            <Row label="Purchased" value={fmtDate(ord.purchase_date)} />
            <Row label="Paid" value={inr(ord.price_paid ?? item.mrp)} />
            <Row
              label="Invoice"
              value={<span className="inline-flex items-center gap-1 text-sl-green-deep font-700"><Check /> Verified · single owner</span>}
            />
            <Row label="Warranty on record" value={`${item.warranty_months ?? 0} months`} />
          </div>

          {item.return_reason && (
            <div className="rounded-xl bg-amber-50 ring-1 ring-amber-200 px-3 py-2.5 flex items-start gap-2">
              <span className="text-amber-500 mt-0.5">⤺</span>
              <p className="text-[12.5px] text-amber-800">
                Returned by buyer — <span className="font-700">“{item.return_reason}”</span>
              </p>
            </div>
          )}
        </div>

        {/* RIGHT — current condition capture (upload) */}
        <div className="space-y-3">
          <div className="relative rounded-2xl overflow-hidden bg-az-navy shadow-card">
            {heroPreview ? (
              <img src={heroPreview} alt="Uploaded current condition" className="w-full h-64 object-cover" />
            ) : (
              <div className="w-full h-64 grid place-items-center text-center px-6">
                <div className="text-white/70">
                  <div className="mx-auto mb-2 w-10 h-10 rounded-full bg-white/10 grid place-items-center"><UploadIcon /></div>
                  <p className="text-[13px] font-700 text-white/90">Upload the unit’s current photos</p>
                  <p className="text-[11.5px] text-white/55 mt-0.5">The AI grades what you upload — nothing on file is used.</p>
                </div>
              </div>
            )}
            <Corners />
            {scanning && <ScanSweep />}
            <div className="absolute left-3 top-3">
              <span className="rounded-md bg-black/55 backdrop-blur text-white text-[10px] font-700 px-2 py-1 tracking-wide">
                CURRENT CONDITION {hasUpload ? "· UPLOADED" : "· AWAITING UPLOAD"}
              </span>
            </div>
            {scanning && <ScanCaptions />}
          </div>

          {/* dropzone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => { e.preventDefault(); setDragOver(false); addFiles(e.dataTransfer.files); }}
            className={`rounded-2xl border-2 border-dashed p-4 transition ${dragOver ? "border-sl-green bg-sl-mint/40" : "border-sl-line bg-white"}`}
          >
            <div className="flex items-center gap-3">
              <button
                onClick={() => inputRef.current?.click()}
                disabled={images.length >= MAX_IMAGES || busyFiles || scanning}
                className="shrink-0 h-10 px-4 rounded-lg bg-az-slate text-white text-[13px] font-700 hover:bg-az-navy transition active:scale-[0.98] disabled:opacity-50 flex items-center gap-2"
              >
                <UploadIcon />
                {busyFiles ? "Reading…" : "Upload photos"}
              </button>
              <p className="text-[12px] text-sl-muted leading-snug">
                Drag &amp; drop or pick the unit’s photos.{" "}
                <span className="text-sl-ink font-600">{images.length}/{MAX_IMAGES}</span> added.
              </p>
            </div>
            <input
              ref={inputRef}
              type="file"
              accept="image/*"
              multiple
              className="hidden"
              onChange={(e) => { addFiles(e.target.files); e.target.value = ""; }}
            />

            {images.length > 0 && (
              <div className="mt-3 flex gap-2">
                {images.map((im, i) => (
                  <div key={i} className="relative">
                    <img src={im.preview} alt={`Upload ${i + 1}`} className="w-16 h-16 rounded-lg object-cover ring-1 ring-sl-line" />
                    <button
                      onClick={() => setImages((prev) => prev.filter((_, j) => j !== i))}
                      disabled={scanning}
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

          <p className="text-[11.5px] text-sl-muted leading-relaxed px-1">
            {hasUpload
              ? "Grading your uploaded photos live against the day-0 baseline."
              : "Upload at least one current photo to grade this unit."}
          </p>
        </div>
      </div>

      <FooterAction
        variant="green"
        onClick={() => onScan(images.map((im) => im.b64), images.map((im) => im.preview))}
        disabled={!hasUpload}
        loading={scanning}
        hint={scanning ? undefined : hasUpload ? "Nova-2 multimodal · grades your photos in ~2s" : "Upload a photo to enable grading"}
      >
        {scanning ? "Scanning…" : hasUpload ? "Run AI grade on uploaded photos" : "Upload to grade"}
      </FooterAction>
    </div>
  );
}

function Row({ label, value, mono }) {
  return (
    <div className="flex items-center justify-between px-4 py-2.5">
      <span className="text-[12px] text-sl-muted">{label}</span>
      <span className={`text-[12.5px] font-600 text-sl-ink text-right ${mono ? "tnum" : ""}`}>{value}</span>
    </div>
  );
}

function Corners() {
  const c = "absolute w-6 h-6 border-sl-green-soft";
  return (
    <>
      <span className={`${c} border-t-2 border-l-2 rounded-tl-lg left-3 top-3`} />
      <span className={`${c} border-t-2 border-r-2 rounded-tr-lg right-3 top-3`} />
      <span className={`${c} border-b-2 border-l-2 rounded-bl-lg left-3 bottom-3`} />
      <span className={`${c} border-b-2 border-r-2 rounded-br-lg right-3 bottom-3`} />
    </>
  );
}

function ScanSweep() {
  return (
    <span
      className="absolute left-0 right-0 h-16 pointer-events-none"
      style={{
        background: "linear-gradient(180deg, transparent, rgba(52,199,154,0.35), transparent)",
        boxShadow: "0 0 22px 4px rgba(52,199,154,0.5)",
        animation: "scanSweep 1.4s ease-in-out infinite",
      }}
    />
  );
}

function ScanCaptions() {
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setI((v) => (v + 1) % SCAN_STEPS.length), 850);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/75 to-transparent px-3 pt-8 pb-3">
      <p key={i} className="text-white text-[12px] font-600 anim-fade-in flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-sl-green-soft animate-pulse" />
        {SCAN_STEPS[i]}
      </p>
    </div>
  );
}

function UploadIcon() {
  return (
    <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none">
      <path d="M12 16V5m0 0L8 9m4-4l4 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M5 19h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function Check() {
  return (
    <svg viewBox="0 0 24 24" className="w-3.5 h-3.5" fill="none">
      <path d="M5 12l4.5 4.5L19 7" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
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
