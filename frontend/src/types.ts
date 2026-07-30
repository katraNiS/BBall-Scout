// TS interfaces που καθρεφτίζουν τα API responses του FastAPI backend.

export interface StatMeta {
  key: string;
  label: string;
  group: string;
  min: number;
  max: number;
  step: number;
  default: number;
  is_pct: boolean;
  unit: string;
  format: string;
}

export interface StatsMetaResponse {
  stats: StatMeta[];
  traits: string[];
  groups: string[];
  trait_labels: Record<string, string>;
}

export interface Archetype {
  name: string;
  traits: string[];
  positions: string[];
}

export interface ArchetypesResponse {
  count: number;
  archetypes: Archetype[];
}

export interface ExplainEntry {
  feature: string;
  label: string;
  user_value: number;
  player_value: number;
  user_display: string;
  player_display: string;
  user_pct: number;
  player_pct: number;
  diff: number;
  quality: "match" | "close" | "far";
}

export interface RadarData {
  axes: string[];
  keys: string[];
  user: number[];
  player: number[];
}

export interface MatchResult {
  rank: number;
  player_name: string;
  season: string;
  position_group: string;
  compound_archetype: string;
  height_cm: number | null;
  weight_lbs: number | null;
  similarity: number;
  boost: number;
  final_score: number;
  active_traits: string[];
  matching: ExplainEntry[];
  diverging: ExplainEntry[];
  radar: RadarData;
}

export interface SimilarResponse {
  count: number;
  results: MatchResult[];
  requested_stats: string[];
}

// Request payload — stats/weights σε display units (backend μετατρέπει).
export interface SimilarRequest {
  stats: Record<string, number>;
  weights?: Record<string, number>;
  top_n?: number;
  active_traits?: string[];
  season_range?: string;
  // Tag πάνω στην καταγραφή search history (Phase 4) — δεν επηρεάζει το matching.
  prospect_id?: string | null;
}

export interface ClassifyResponse {
  player_name: string;
  season: string;
  position_group: string;
  compound_archetype: string;
  active_traits: string[];
  trait_scores: Record<string, number>;
}

// ── Prospects ─────────────────────────────────────────────────────────────────
// Ίδιο vocabulary με το position_group του engine (src/archetypes.py ALL_POSITIONS) —
// όχι PG/SG/SF/PF/C.
export type ProspectPosition = "G" | "G-F" | "F" | "F-C" | "C";

// Το query που παρήγαγε ένα saved comp set — αποθηκεύεται μαζί με τα results
// γιατί "Luka, 87%" δεν σημαίνει τίποτα χωρίς να ξέρεις ποια stats/βάρη ρωτήθηκαν.
export interface CompQuery {
  stats: Record<string, number>;
  weights?: Record<string, number>;
  season_range?: string | null;
  active_traits?: string[];
}

// Slim αντίγραφο ενός MatchResult — όχι το πλήρες payload (radar/explanations
// είναι derived data, δεν αποθηκεύονται).
export interface CompResultSummary {
  player_name: string;
  season: string;
  similarity: number;
  compound_archetype: string;
  position_group: string;
}

export interface ProspectComp {
  id: string;
  created_at: string; // ISO datetime
  label: string | null;
  query: CompQuery;
  results: CompResultSummary[];
}

export interface Prospect {
  id: string;
  first_name: string;
  last_name: string;
  birth_date: string | null; // ISO date "YYYY-MM-DD"
  age_manual: number | null;
  height_cm: number | null;
  weight_kg: number | null;
  nationality: string | null;
  team: string | null;
  league: string | null;
  position: ProspectPosition | null;
  notes: string | null;
  created_at: string; // ISO datetime
  updated_at: string; // ISO datetime
  comps: ProspectComp[];
}

// Request payload για POST /prospects — ίδια πεδία, χωρίς id/timestamps/comps
// (τα comps προστίθενται μόνο μέσω του δικού τους endpoint).
export type ProspectCreate = Omit<Prospect, "id" | "created_at" | "updated_at" | "comps">;

// Request payload για PATCH /prospects/{id} — όλα optional (partial update).
export type ProspectUpdate = Partial<ProspectCreate>;

// Request payload για POST /prospects/{id}/comps.
export type CompCreate = Omit<ProspectComp, "id" | "created_at">;

// ── Search history (Phase 4) ─────────────────────────────────────────────────
// Καταγράφεται αυτόματα από το backend μέσα στο POST /similar — ποτέ client-submitted.
export interface SearchTopResult {
  player_name: string;
  season: string;
  similarity: number;
}

export interface SearchHistoryEntry {
  id: string;
  created_at: string; // ISO datetime
  query: CompQuery;
  top_n: number;
  top_results: SearchTopResult[];
  prospect_id: string | null;
}
