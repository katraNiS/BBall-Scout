import { useMemo } from "react";
import type { ExplainEntry, MatchResult, StatMeta } from "../types";
import RadarChart from "./RadarChart";
import CoverageCells, { coverageClass } from "./Coverage";
import { decimalsFor, shortLabel } from "../statFormat";

interface Props {
  r: MatchResult;
  /** Πόσα stats ζήτησε ο χρήστης — ο παρονομαστής του coverage indicator. */
  requested: number;
  /** Τα βάρη του query, ώστε το breakdown να δείχνει τι βάρυνε πόσο. */
  weights: Record<string, number>;
  statByKey: Record<string, StatMeta>;
  open: boolean;
  onToggle: () => void;
  onUseAsTarget: (values: Record<string, number>) => void;
  onSaveComp?: () => void;
}

// Το similarity παίρνει accent μόνο όταν είναι πραγματικά ψηλό· αλλιώς μένει
// ουδέτερο ώστε η στήλη να μη μοιάζει ομοιόμορφα "καλή".
function simColor(similarity: number): string {
  return similarity >= 0.6 ? "var(--accent)" : similarity >= 0.4 ? "#b7c6d4" : "var(--text-3)";
}

export default function ResultRow({
  r,
  requested,
  weights,
  statByKey,
  open,
  onToggle,
  onUseAsTarget,
  onSaveComp,
}: Props) {
  const simPct = Math.round(r.similarity * 100);
  const covPct = Math.round(r.coverage * 100);
  const covCells = Math.max(requested, 1);
  const covFilled = Math.round(r.coverage * covCells);

  // matching + diverging είναι δύο όψεις της ίδιας λίστας — στο breakdown τα
  // ενώνουμε και τα ταξινομούμε κατά συνεισφορά, γιατί η ερώτηση του scout είναι
  // "τι κράτησε αυτόν τον παίκτη ψηλά", όχι "ποιο bucket τα έβαλε το backend".
  const breakdown = useMemo(() => {
    // Dedupe κατά feature: το API τα φιλτράρει ήδη, αλλά διπλότυπο feature εδώ
    // σημαίνει διπλότυπο React key — σιωπηλή ζημιά σε κάθε re-render.
    const byFeature = new Map<string, ExplainEntry>();
    for (const e of [...r.matching, ...r.diverging]) {
      if (!byFeature.has(e.feature)) byFeature.set(e.feature, e);
    }
    const rows = [...byFeature.values()].map((e) => {
      const meta = statByKey[e.feature];
      const weight = weights[e.feature] ?? 1;
      // Fit: πόσο κοντά είναι σε percentile όρους, ζυγισμένο με το βάρος που
      // δήλωσε ο χρήστης. Percentiles (όχι raw units) γιατί μόνο έτσι είναι
      // συγκρίσιμα ανάμεσα σε features με τελείως διαφορετικές κλίμακες.
      // Μη διαθέσιμο stat → fit 0: δεν συνεισέφερε τίποτα στο distance.
      const closeness = 1 - Math.abs(e.user_pct - e.player_pct) / 100;
      const available = e.available !== false;
      return { e, meta, weight, available, fit: available ? Math.max(0, closeness) * weight : 0 };
    });
    // Τα μη διαθέσιμα πέφτουν τελευταία, ώστε το βλέμμα να πιάνει πρώτα ό,τι
    // πραγματικά μέτρησε.
    rows.sort((a, b) => Number(b.available) - Number(a.available) || b.fit - a.fit);
    return rows;
  }, [r.matching, r.diverging, statByKey, weights]);

  const maxFit = Math.max(1, ...breakdown.map((b) => b.weight));

  // Οι άξονες του radar είναι πλήρη labels — τα κόβουμε για να χωρέσουν γύρω
  // από το πολύγωνο.
  const radarLabels = useMemo(
    () => r.radar.keys.map((k) => (statByKey[k] ? shortLabel(statByKey[k]) : k)),
    [r.radar.keys, statByKey]
  );

  const useAsTarget = () => {
    const values: Record<string, number> = {};
    for (const { e } of breakdown) values[e.feature] = e.player_value;
    onUseAsTarget(values);
  };

  return (
    <div className={`mrow${open ? " open" : ""}`}>
      <button type="button" className="mrow-main" onClick={onToggle} aria-expanded={open}>
        <span className="col-rank mrow-rank">{String(r.rank).padStart(2, "0")}</span>

        <span className="col-name mrow-player">
          <span className="mrow-avatar">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="12" cy="8" r="3.6" />
              <path d="M4.5 20.5c0-4 3.4-6.4 7.5-6.4s7.5 2.4 7.5 6.4" />
            </svg>
          </span>
          <span style={{ minWidth: 0 }}>
            <span className="mrow-name" style={{ display: "block" }}>
              {r.player_name}
            </span>
            <span className="mrow-meta">
              {r.season} · {r.position_group}
              {r.height_cm ? ` · ${r.height_cm.toFixed(0)}cm` : ""}
              {r.weight_lbs ? ` · ${r.weight_lbs.toFixed(0)}lb` : ""}
            </span>
          </span>
        </span>

        <span className="col-arch">
          <span className="tag">{r.compound_archetype}</span>
        </span>

        <span className="col-cov">
          <span className="cov-top">
            <span className={`cov-pct ${coverageClass(r.coverage)}`}>{covPct}%</span>
            <span className="cov-ratio">
              {covFilled}/{covCells} stats
            </span>
          </span>
          <CoverageCells coverage={r.coverage} requested={requested} />
        </span>

        <span className="col-radar mrow-radar">
          <RadarChart radar={r.radar} size={84} playerName={r.player_name} />
        </span>

        <span className="col-sim">
          <span className="mrow-sim-val" style={{ color: simColor(r.similarity), display: "block" }}>
            {simPct}
          </span>
          <span className="mrow-sim-label">SIMILARITY</span>
        </span>

        <span className="col-caret mrow-caret">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
            <path d="M6 9l6 6 6-6" />
          </svg>
        </span>
      </button>

      {open && (
        <div className="mrow-expand">
          <div>
            <div className="bd-title">
              <span className="label label-lg">Τι οδήγησε σε αυτό το match</span>
              <span className="bd-formula">fit = weight × (1 − |Δ percentile| / 100)</span>
            </div>

            <div className="bd-head">
              <span className="bd-stat">Stat</span>
              <span className="bd-num">Target</span>
              <span className="bd-num">Player</span>
              <span className="bd-delta">Δ</span>
              <span className="bd-fit" style={{ paddingLeft: 14 }}>
                Fit
              </span>
            </div>

            {breakdown.map(({ e, meta, weight, available, fit }) => (
              <BreakdownRow
                key={e.feature}
                entry={e}
                meta={meta}
                weight={weight}
                available={available}
                fit={fit}
                maxFit={maxFit}
              />
            ))}

            <div className="bd-actions">
              {onSaveComp && (
                <button type="button" className="btn btn-sm" onClick={onSaveComp}>
                  Αποθήκευση στα comps
                </button>
              )}
              <button type="button" className="btn btn-sm" onClick={useAsTarget}>
                Χρήση ως νέο target
              </button>
              {r.active_traits.length > 0 && (
                <span className="sub-mono" style={{ alignSelf: "center" }}>
                  traits: {r.active_traits.join(", ")}
                  {r.boost > 0 && ` · boost +${r.boost.toFixed(3)}`}
                </span>
              )}
            </div>
          </div>

          <div>
            <div className="label label-lg" style={{ marginBottom: 9 }}>
              Profile overlay
            </div>
            <RadarChart
              radar={r.radar}
              size={252}
              detailed
              labels={radarLabels}
              playerName={r.player_name}
            />
            <div className="overlay-legend">
              <span>
                <span className="legend-user" />
                Το target σου
              </span>
              <span>
                <span className="legend-player" />
                {r.player_name}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function BreakdownRow({
  entry,
  meta,
  weight,
  available,
  fit,
  maxFit,
}: {
  entry: ExplainEntry;
  meta: StatMeta | undefined;
  weight: number;
  available: boolean;
  fit: number;
  maxFit: number;
}) {
  // Το πρόσημο μπαίνει χειροκίνητα (όχι μέσω formatValue) γιατί εδώ γράφουμε
  // μέγεθος μεταβολής: το formatValue θα πρόσθετε δικό του "+" στα features με
  // signed template και θα έβγαζε "−+5.0".
  const delta = entry.player_value - entry.user_value;
  const deltaText = meta
    ? `${delta >= 0 ? "+" : "−"}${Math.abs(delta).toFixed(decimalsFor(meta))}`
    : delta.toFixed(2);

  return (
    <div className="bd-row">
      <span
        className={`bd-stat${available ? "" : " missing"}`}
        title={available ? entry.label : `${entry.label} — δεν καταγραφόταν αυτή τη σεζόν`}
      >
        {meta ? shortLabel(meta) : entry.label}
        {!available && " ▨"}
      </span>
      <span className="bd-num">{entry.user_display}</span>
      <span className={`bd-num player${available ? "" : " missing"}`}>
        {available ? entry.player_display : "—"}
      </span>
      <span className={`bd-delta ${available ? `q-${entry.quality}` : "q-none"}`}>
        {available ? deltaText : "no data"}
      </span>
      <span className="bd-fit">
        <span className="bd-fit-track">
          <span
            className={available && entry.quality === "match" ? "strong" : undefined}
            style={{ display: "block", width: `${Math.min(100, (fit / maxFit) * 100)}%` }}
          />
        </span>
        <span className="bd-fit-val">
          {available ? `×${weight} · ${fit.toFixed(2)}` : "εκτός"}
        </span>
      </span>
    </div>
  );
}
