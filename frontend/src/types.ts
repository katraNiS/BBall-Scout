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
}

export interface ClassifyResponse {
  player_name: string;
  season: string;
  position_group: string;
  compound_archetype: string;
  active_traits: string[];
  trait_scores: Record<string, number>;
}
