import { useEffect, useRef, useState } from "react";

const nf = new Intl.NumberFormat("en-IN");

export const inr = (n) => "₹" + nf.format(Math.round(n ?? 0));

// signed with a true minus glyph so red/green columns read cleanly
export const signedInr = (n) => {
  const v = Math.round(n ?? 0);
  if (v < 0) return "−₹" + nf.format(Math.abs(v));
  return "+₹" + nf.format(v);
};

export const num = (n) => nf.format(Math.round(n ?? 0));

const GRADE_COLOR = {
  A: "var(--color-grade-a)",
  B: "var(--color-grade-b)",
  C: "var(--color-grade-c)",
  D: "var(--color-grade-d)",
  F: "var(--color-grade-f)",
};
export const gradeColor = (g) => GRADE_COLOR[g] || "var(--color-sl-muted)";

const GRADE_LABEL = {
  A: "Like new",
  B: "Lightly used",
  C: "Used — good",
  D: "Heavily used",
  F: "Heavy wear",
};
export const gradeLabel = (g) => GRADE_LABEL[g] || "Graded";

// requestAnimationFrame count-up for the money moment
export function useCountUp(target, duration = 900) {
  const [val, setVal] = useState(0);
  const target0 = useRef(target);
  useEffect(() => {
    let raf;
    let start = null;
    const from = 0;
    const to = target ?? 0;
    const step = (t) => {
      if (start == null) start = t;
      const p = Math.min(1, (t - start) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      setVal(from + (to - from) * eased);
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);
  return val;
}
