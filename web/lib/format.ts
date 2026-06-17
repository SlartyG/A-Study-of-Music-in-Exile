/** Format a number for display, using Russian decimal comma */
export function fmt(value: number | null | undefined, decimals = 3): string {
  if (value == null) return "—";
  return value.toFixed(decimals).replace(".", ",");
}

/** Format delta with sign, e.g. "+0,021" or "−0,008" */
export function fmtDelta(value: number | null | undefined, decimals = 3): string {
  if (value == null) return "—";
  const abs = Math.abs(value).toFixed(decimals).replace(".", ",");
  return value >= 0 ? `+${abs}` : `−${abs}`;
}

/** Format p-value with significance label */
export function fmtP(p: number | null | undefined): string {
  if (p == null) return "н/д";
  if (p < 0.001) return "< 0,001";
  return p.toFixed(3).replace(".", ",");
}

/** Significance label: "n.s." or "*" */
export function sigLabel(significant: boolean, p: number | null | undefined): string {
  if (significant) return "*";
  return "n.s.";
}

/** Short significance note for display */
export function sigNote(significant: boolean): string {
  return significant ? "" : " n.s.";
}

/** Color for delta value */
export function deltaColor(delta: number | null | undefined): string {
  if (delta == null) return "#8A8A8A";
  if (Math.abs(delta) < 0.001) return "#8A8A8A";
  return delta < 0 ? "#C1272D" : "#4A7FA5";
}
