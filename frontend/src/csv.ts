// Client-side CSV export των search results — δεν χρειάζεται backend endpoint,
// τα δεδομένα υπάρχουν ήδη στο MatchResult[] που έχει φέρει το /similar.

import type { MatchResult } from "./types";

function escapeCsvField(value: string | number): string {
  const s = String(value);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

const HEADERS = [
  "rank",
  "player_name",
  "season",
  "position_group",
  "compound_archetype",
  "height_cm",
  "weight_lbs",
  "similarity_pct",
  // Χωρίς αυτό το export αφαιρεί ακριβώς το σήμα που το UI βάζει σε κάθε γραμμή:
  // ένα 84% με κάλυψη 50% δεν είναι το ίδιο νούμερο με ένα 84% με κάλυψη 100%,
  // και σε ένα spreadsheet δεν υπάρχει τίποτα να το θυμίσει.
  "coverage_pct",
  "final_score",
  "active_traits",
];

export function matchResultsToCsv(results: MatchResult[]): string {
  const rows = results.map((r) => [
    r.rank,
    r.player_name,
    r.season,
    r.position_group,
    r.compound_archetype,
    r.height_cm ?? "",
    r.weight_lbs ?? "",
    Math.round(r.similarity * 100),
    Math.round(r.coverage * 100),
    r.final_score.toFixed(4),
    r.active_traits.join("; "),
  ]);
  return [HEADERS, ...rows].map((row) => row.map(escapeCsvField).join(",")).join("\r\n");
}

export function downloadCsv(filename: string, csvContent: string): void {
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
