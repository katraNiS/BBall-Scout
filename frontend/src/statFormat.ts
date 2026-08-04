// Μορφοποίηση & percentile lookup για τα features — ένα σημείο, ώστε το stat
// builder, τα result rows και το CSV export να μιλάνε ακριβώς την ίδια γλώσσα.

import type { StatMeta } from "./types";

// Πόσα δεκαδικά "αξίζει" ένα stat. Πρώτη πηγή αλήθειας είναι το python format
// template που στέλνει το backend ("{:.2f}") — το ίδιο που χρησιμοποιεί το
// engine όταν σερβίρει τα player_display, ώστε ο builder και το breakdown να μη
// δείχνουν την ίδια ποσότητα με διαφορετική ακρίβεια. Fallback στο step.
export function decimalsFor(meta: StatMeta): number {
  const m = meta.format?.match(/\.(\d+)f/);
  if (m) return parseInt(m[1], 10);
  if (meta.step >= 1) return 0;
  if (meta.step >= 0.1) return 1;
  return 2;
}

/**
 * Αριθμός χωρίς μονάδα — για στήλες πίνακα που έχουν δικό τους header.
 *
 * Το `+` flag του format template ("{:+.1f}") τηρείται: για τα net_rating και
 * d_*_diff το πρόσημο ΕΙΝΑΙ η πληροφορία (αρνητικό d_fg3_diff = καλή άμυνα), και
 * ένα σκέτο "5.0" δίπλα σε ένα "-5.0" διαβάζεται λάθος.
 */
export function formatValue(meta: StatMeta, value: number): string {
  const text = value.toFixed(decimalsFor(meta));
  const signed = meta.format?.includes("+") && value >= 0;
  return signed ? `+${text}` : text;
}

/** Αριθμός + μονάδα ("26.4 PPG", "60.5%") — για standalone εμφάνιση. */
export function formatWithUnit(meta: StatMeta, value: number): string {
  return `${formatValue(meta, value)}${meta.unit}`;
}

// Σύντομο key για πυκνούς πίνακες. Έρχεται από τα SHORT_LABELS του backend —
// το `label` είναι φτιαγμένο για ανάγνωση ("Defensive Rating (lower = better)")
// και κάθε προσπάθεια να συντομευτεί client-side με regex βγάζει σκουπίδια
// ("Height (cm)" → "cm"). Fallback μόνο για παλιό backend χωρίς το πεδίο.
export function shortLabel(meta: StatMeta): string {
  return meta.short ?? meta.label.replace(/\s*\(lower = better\)\s*/, "").trim();
}

/** Θέση της τιμής μέσα στο [min, max] ως 0–1 — για slider markers και meters. */
export function normalize(meta: StatMeta, value: number): number {
  const span = meta.max - meta.min;
  if (span <= 0) return 0;
  return Math.max(0, Math.min(1, (value - meta.min) / span));
}

/**
 * Percentile της τιμής μέσα στο πραγματικό league distribution.
 *
 * Τα `pcts` είναι 101 quantiles σε αύξουσα σειρά, οπότε το percentile βρίσκεται
 * με binary search + γραμμική παρεμβολή μέσα στο bucket. Χωρίς `pcts` (backend
 * χωρίς φορτωμένο dataset) επιστρέφει null — ο caller κρύβει το readout αντί να
 * δείξει εικασία.
 */
export function percentileOf(meta: StatMeta, value: number): number | null {
  const q = meta.pcts;
  if (!q || q.length < 2) return null;
  if (value <= q[0]) return 0;
  if (value >= q[q.length - 1]) return 100;

  let lo = 0;
  let hi = q.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (q[mid] <= value) lo = mid;
    else hi = mid;
  }
  const span = q[hi] - q[lo];
  const frac = span > 0 ? (value - q[lo]) / span : 0;
  return Math.round(lo + frac);
}

const COMPACT = new Intl.NumberFormat("en-US");

export function compactCount(n: number): string {
  return COMPACT.format(n);
}
