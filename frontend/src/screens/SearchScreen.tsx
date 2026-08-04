import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api, ApiError } from "../api";
import type { MatchResult, StatMeta } from "../types";
import { useMeta } from "../MetaContext";
import StatBuilder, { type Controls } from "../components/StatBuilder";
import ResultRow from "../components/ResultRow";
import { kgToLbs, roundToStep } from "../units";
import { compactCount, shortLabel } from "../statFormat";
import type { FromProspectPrefill } from "../prospectUtils";
import { matchResultsToCsv, downloadCsv } from "../csv";

// Ίδιο vocabulary με το position_group / ALL_POSITIONS στο src/archetypes.py.
const POSITION_FILTERS = ["G", "G-F", "F", "F-C", "C"];

// Restore μιας παλιότερης αναζήτησης από το home screen (Phase 4) — ίδιο router
// state + apply-once-on-mount μηχανισμό με το FromProspectPrefill, διαφορετικό
// shape (πλήρες query αντί για physicals μόνο).
export interface FromSearchRestore {
  stats: Record<string, number>;
  weights?: Record<string, number>;
  season_range?: string | null;
  active_traits?: string[];
  top_n?: number;
}

function parseSeasonRange(range: string | null | undefined): [number, number] | null {
  const m = range?.match(/^(\d{4})-(\d{4})$/);
  return m ? [parseInt(m[1], 10), parseInt(m[2], 10)] : null;
}

export default function SearchScreen() {
  const { stats, traits, traitLabels } = useMeta();
  const location = useLocation();
  const [controls, setControls] = useState<Controls>({});

  const [selectedTraits, setSelectedTraits] = useState<string[]>([]);
  const [yearRange, setYearRange] = useState<[number, number]>([2010, 2025]);
  const [topN, setTopN] = useState(10);

  const [results, setResults] = useState<MatchResult[] | null>(null);
  // Το query που παρήγαγε τα `results` — κρατιέται ξεχωριστά από τα ζωντανά
  // controls, ώστε το coverage/breakdown να περιγράφει την αναζήτηση που
  // *έτρεξε*, όχι αυτή που ο χρήστης άρχισε να πληκτρολογεί μετά.
  const [ranQuery, setRanQuery] = useState<{ keys: string[]; weights: Record<string, number> } | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [positionFilter, setPositionFilter] = useState("");
  const [requireFullCoverage, setRequireFullCoverage] = useState(false);

  // Prefill source: παραμένει ζωντανό ακόμα κι αν κρύψει ο χρήστης το banner, ώστε
  // το "Αποθήκευση comps" να μένει διαθέσιμο ανεξάρτητα από το banner.
  const [prefillSource, setPrefillSource] = useState<{ id: string; name: string } | null>(null);
  const [restoredFromHistory, setRestoredFromHistory] = useState(false);
  const [bannerDismissed, setBannerDismissed] = useState(false);
  const [savingComps, setSavingComps] = useState(false);
  const [saveCompsMsg, setSaveCompsMsg] = useState<string | null>(null);
  const appliedPrefillRef = useRef(false);

  // ── Αρχικοποίησε τα controls όταν φτάσουν τα stats από το context ──────────
  useEffect(() => {
    if (!stats.length) return;
    setControls((prev) => {
      if (Object.keys(prev).length) return prev; // ήδη αρχικοποιημένα
      const init: Controls = {};
      for (const s of stats) {
        init[s.key] = { enabled: false, value: s.default, weight: 1 };
      }
      return init;
    });
  }, [stats]);

  const controlsReady = Object.keys(controls).length > 0;

  // ── Prefill από prospect (Phase 3) ή restore από search history (Phase 4) ──
  // Τρέχει μόνο μία φορά (appliedPrefillRef) ώστε να μη σβήνει τις αλλαγές του
  // χρήστη σε επόμενα re-renders. Περιμένει τα controls να έχουν αρχικοποιηθεί
  // από τα stats πριν τα πατσάρει — αλλιώς θα έλειπε το `weight` από το Control.
  useEffect(() => {
    if (appliedPrefillRef.current || !controlsReady) return;
    const state = location.state as
      | { fromProspect?: FromProspectPrefill; fromSearch?: FromSearchRestore }
      | null;

    const fs = state?.fromSearch;
    if (fs) {
      appliedPrefillRef.current = true;
      setControls((prev) => {
        const next = { ...prev };
        for (const [key, value] of Object.entries(fs.stats)) {
          if (next[key]) {
            next[key] = { ...next[key], enabled: true, value, weight: fs.weights?.[key] ?? 1 };
          }
        }
        return next;
      });
      if (fs.active_traits) setSelectedTraits(fs.active_traits);
      const parsedRange = parseSeasonRange(fs.season_range);
      if (parsedRange) setYearRange(parsedRange);
      if (fs.top_n) setTopN(fs.top_n);
      setRestoredFromHistory(true);
      return;
    }

    const fp = state?.fromProspect;
    if (!fp) return;
    appliedPrefillRef.current = true;

    setControls((prev) => {
      const next = { ...prev };
      if (fp.height_cm != null && next.height_cm) {
        next.height_cm = { ...next.height_cm, enabled: true, value: fp.height_cm };
      }
      if (fp.weight_kg != null && next.weight_lbs) {
        const meta = stats.find((s) => s.key === "weight_lbs");
        const lbs = kgToLbs(fp.weight_kg);
        const value = meta ? roundToStep(lbs, meta.step, meta.min, meta.max) : lbs;
        next.weight_lbs = { ...next.weight_lbs, enabled: true, value };
      }
      return next;
    });
    setPrefillSource({ id: fp.id, name: fp.name });
  }, [controlsReady, location.state, stats]);

  const enabledKeys = useMemo(
    () => stats.map((s) => s.key).filter((k) => controls[k]?.enabled),
    [stats, controls]
  );

  const statByKey = useMemo(() => {
    const m: Record<string, StatMeta> = {};
    for (const s of stats) m[s.key] = s;
    return m;
  }, [stats]);

  const patchControl = (key: string, patch: Partial<Controls[string]>) =>
    setControls((prev) => ({ ...prev, [key]: { ...prev[key], ...patch } }));

  const buildQuery = () => {
    const statsPayload: Record<string, number> = {};
    const weightsPayload: Record<string, number> = {};
    for (const key of enabledKeys) {
      const c = controls[key];
      statsPayload[key] = c.value;
      if (c.weight !== 1) weightsPayload[key] = c.weight;
    }
    return {
      stats: statsPayload,
      weights: Object.keys(weightsPayload).length ? weightsPayload : undefined,
      season_range: `${yearRange[0]}-${yearRange[1]}`,
      active_traits: selectedTraits.length ? selectedTraits : undefined,
    };
  };

  // ── Run search ─────────────────────────────────────────────────────────────
  const runSearch = async () => {
    setLoading(true);
    setError(null);
    setSaveCompsMsg(null);
    const query = buildQuery();
    try {
      const res = await api.similar({
        ...query,
        top_n: topN,
        prospect_id: prefillSource?.id ?? null,
      });
      setResults(res.results);
      setRanQuery({
        keys: Object.keys(query.stats),
        weights: Object.fromEntries(Object.keys(query.stats).map((k) => [k, controls[k].weight])),
      });
      setExpanded(res.results[0] ? rowKey(res.results[0]) : null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
      setResults(null);
      setRanQuery(null);
    } finally {
      setLoading(false);
    }
  };

  const resetBuilder = () => {
    setControls((prev) => {
      const next: Controls = {};
      for (const [key, c] of Object.entries(prev)) next[key] = { ...c, enabled: false, weight: 1 };
      return next;
    });
    setSelectedTraits([]);
    setResults(null);
    setRanQuery(null);
    setError(null);
  };

  // "Χρήση ως νέο target": φορτώνει τις τιμές ενός παίκτη πίσω στον builder ώστε
  // ο χρήστης να ψάξει "ποιος άλλος μοιάζει με αυτόν" χωρίς να ξαναχτίσει προφίλ.
  const useAsTarget = (values: Record<string, number>) => {
    setControls((prev) => {
      const next = { ...prev };
      for (const [key, value] of Object.entries(values)) {
        const meta = statByKey[key];
        if (!next[key] || !meta) continue;
        next[key] = {
          ...next[key],
          enabled: true,
          value: roundToStep(value, meta.step, meta.min, meta.max),
        };
      }
      return next;
    });
  };

  // ── Save comps στον prospect που ξεκίνησε αυτό το search ───────────────────
  // Σώζει τα visibleResults (ό,τι βλέπει ο χρήστης) όχι το ωμό results — αν έχει
  // φιλτράρει, το comp set πρέπει να αντανακλά αυτό που κοιτάει.
  const handleSaveComps = async () => {
    if (!prefillSource || !visibleResults?.length) return;
    setSavingComps(true);
    setSaveCompsMsg(null);
    try {
      await api.prospects.addComp(prefillSource.id, {
        label: null,
        query: buildQuery(),
        results: visibleResults.map((r) => ({
          player_name: r.player_name,
          season: r.season,
          similarity: r.similarity,
          compound_archetype: r.compound_archetype,
          position_group: r.position_group,
        })),
      });
      setSaveCompsMsg("Αποθηκεύτηκε.");
    } catch (e) {
      setSaveCompsMsg(e instanceof ApiError ? e.message : String(e));
    } finally {
      setSavingComps(false);
    }
  };

  // ── Client-side φίλτρα (τα δεδομένα ήδη υπάρχουν) ──────────────────────────
  const visibleResults = useMemo(() => {
    if (!results) return null;
    let out = results;
    if (positionFilter) out = out.filter((r) => r.position_group === positionFilter);
    if (requireFullCoverage) out = out.filter((r) => r.coverage > 0.999);
    return out;
  }, [results, positionFilter, requireFullCoverage]);

  // Το coverage strip εμφανίζεται μόνο όταν έχει κάτι να πει: κάποιο match
  // κρίθηκε σε λιγότερες διαστάσεις από όσες ζητήθηκαν.
  const coverageSummary = useMemo(() => {
    if (!visibleResults?.length) return null;
    const partial = visibleResults.filter((r) => r.coverage < 0.999);
    if (!partial.length) return null;
    const mean = visibleResults.reduce((t, r) => t + r.coverage, 0) / visibleResults.length;
    return { partial: partial.length, total: visibleResults.length, mean };
  }, [visibleResults]);

  const handleExportCsv = () => {
    if (!visibleResults?.length) return;
    const dateStr = new Date().toISOString().slice(0, 10);
    downloadCsv(`prospectmatch-results-${dateStr}.csv`, matchResultsToCsv(visibleResults));
  };

  const requested = ranQuery?.keys.length ?? enabledKeys.length;

  return (
    <div className="screen">
      {(prefillSource || restoredFromHistory) && !bannerDismissed && (
        <div className="banner">
          {prefillSource ? (
            <>
              Prefilled από <Link to={`/prospects/${prefillSource.id}/edit`}>{prefillSource.name}</Link>
            </>
          ) : (
            "Επαναφορά προηγούμενης αναζήτησης"
          )}
          <button type="button" className="linkbtn muted push" onClick={() => setBannerDismissed(true)}>
            Κλείσιμο
          </button>
        </div>
      )}

      <div className="search-layout">
        {/* ── Stat builder rail ── */}
        <aside className="builder">
          <StatBuilder stats={stats} controls={controls} onChange={patchControl} />

          <div className="builder-foot">
            <div className="label">Archetype traits — προαιρετικά</div>
            <div className="builder-traits">
              {traits.map((t) => (
                <button
                  key={t}
                  type="button"
                  className={`traitchip${selectedTraits.includes(t) ? " on" : ""}`}
                  title="Μικρό bonus στο score — δεν αποκλείει κανέναν παίκτη"
                  onClick={() =>
                    setSelectedTraits((prev) =>
                      prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]
                    )
                  }
                >
                  {traitLabels[t] ?? t}
                </button>
              ))}
            </div>

            <div className="builder-foot-grid">
              <div>
                <div className="label" style={{ marginBottom: 5 }}>
                  Season range
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <input
                    className="input mono"
                    type="number"
                    min={1996}
                    max={2025}
                    value={yearRange[0]}
                    aria-label="Από σεζόν"
                    onChange={(e) =>
                      setYearRange([Math.min(+e.target.value || 1996, yearRange[1]), yearRange[1]])
                    }
                  />
                  <span className="sub-mono">→</span>
                  <input
                    className="input mono"
                    type="number"
                    min={1996}
                    max={2025}
                    value={yearRange[1]}
                    aria-label="Έως σεζόν"
                    onChange={(e) =>
                      setYearRange([yearRange[0], Math.max(+e.target.value || 2025, yearRange[0])])
                    }
                  />
                </div>
              </div>
              <div>
                <div className="label" style={{ marginBottom: 5 }}>
                  Αποτελέσματα
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <input
                    type="range"
                    min={5}
                    max={20}
                    value={topN}
                    aria-label="Πλήθος αποτελεσμάτων"
                    style={{ flex: 1 }}
                    onChange={(e) => setTopN(+e.target.value)}
                  />
                  <span className="mono" style={{ fontSize: 13, color: "var(--text)" }}>
                    {topN}
                  </span>
                </div>
              </div>
            </div>

            <div className="builder-run">
              <button
                type="button"
                className="btn btn-primary btn-lg"
                style={{ flex: 1 }}
                disabled={enabledKeys.length === 0 || loading}
                onClick={runSearch}
              >
                {loading ? (
                  <>
                    <span className="spinner" /> Αναζήτηση
                  </>
                ) : enabledKeys.length === 0 ? (
                  "Άναψε ένα stat"
                ) : (
                  `Run match — ${enabledKeys.length} stats`
                )}
              </button>
              <button type="button" className="btn btn-lg" onClick={resetBuilder} disabled={loading}>
                Reset
              </button>
            </div>
          </div>
        </aside>

        {/* ── Matches ── */}
        <section className="matches">
          <div className="matches-head">
            <div>
              <h4 className="h-pane">Matches</h4>
              <div className="sub-mono">
                {results
                  ? `${visibleResults?.length ?? 0} από ${results.length} · weighted RMS σε z-scores`
                  : "Όρισε ένα προφίλ και τρέξε το matching"}
              </div>
            </div>

            <div className="push">
              <span className="label">Θέση</span>
              <div className="seg">
                <button
                  type="button"
                  className={`seg-opt${positionFilter === "" ? " on" : ""}`}
                  onClick={() => setPositionFilter("")}
                >
                  ALL
                </button>
                {POSITION_FILTERS.map((p) => (
                  <button
                    key={p}
                    type="button"
                    className={`seg-opt${positionFilter === p ? " on" : ""}`}
                    onClick={() => setPositionFilter(p)}
                  >
                    {p}
                  </button>
                ))}
              </div>
              {prefillSource && (
                <button
                  type="button"
                  className="btn btn-sm"
                  disabled={savingComps || !visibleResults?.length}
                  onClick={handleSaveComps}
                  title={`Αποθήκευση comp set στον/στην ${prefillSource.name}`}
                >
                  {savingComps ? "Αποθήκευση…" : "Save comps"}
                </button>
              )}
              <button
                type="button"
                className="btn btn-sm"
                disabled={!visibleResults?.length}
                onClick={handleExportCsv}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M12 3v12m0 0 4-4m-4 4-4-4M4 19h16" />
                </svg>
                Export CSV
              </button>
            </div>
          </div>

          {saveCompsMsg && (
            <div className="banner">
              {saveCompsMsg}
              <button type="button" className="linkbtn muted push" onClick={() => setSaveCompsMsg(null)}>
                Κλείσιμο
              </button>
            </div>
          )}

          {coverageSummary && (
            <div className="notice">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#c58e4a" strokeWidth="1.5">
                <path d="M12 9v4m0 4h.01M10.3 3.9 2.4 17.5A1.9 1.9 0 0 0 4 20.4h16a1.9 1.9 0 0 0 1.6-2.9L13.7 3.9a1.9 1.9 0 0 0-3.4 0Z" />
              </svg>
              <span>
                Μέση κάλυψη <code>{Math.round(coverageSummary.mean * 100)}%</code> —{" "}
                {coverageSummary.partial} από {coverageSummary.total} σεζόν δεν έχουν όλα τα stats που
                ζήτησες (tracking data ξεκινά το 2016-17, defensive matchups το 2013-14). Το score τους
                έχει ήδη μειωθεί ανάλογα.
              </span>
              <button
                type="button"
                className="linkbtn push"
                style={{ color: "var(--warn)" }}
                onClick={() => setRequireFullCoverage((v) => !v)}
              >
                {requireFullCoverage ? "Δείξε ξανά όλα" : "Μόνο πλήρη κάλυψη"}
              </button>
            </div>
          )}

          {error && (
            <div className="notice">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#c58e4a" strokeWidth="1.5">
                <path d="M12 9v4m0 4h.01M10.3 3.9 2.4 17.5A1.9 1.9 0 0 0 4 20.4h16a1.9 1.9 0 0 0 1.6-2.9L13.7 3.9a1.9 1.9 0 0 0-3.4 0Z" />
              </svg>
              <span>{error}</span>
              <button type="button" className="linkbtn push" style={{ color: "var(--warn)" }} onClick={runSearch}>
                Επανάληψη
              </button>
            </div>
          )}

          <div className="matches-cols">
            <span className="col-rank">#</span>
            <span className="col-name">Player / season</span>
            <span className="col-arch">Archetype</span>
            <span className="col-cov">Coverage</span>
            <span className="col-radar" style={{ textAlign: "center" }}>
              Profile fit
            </span>
            <span className="col-sim">Similarity</span>
            <span className="col-caret" />
          </div>

          <div className="matches-body">
            {loading && (
              <div className="loading">
                <span className="spinner" /> Υπολογισμός αποστάσεων σε {enabledKeys.length} διαστάσεις…
              </div>
            )}

            {!loading && !results && (
              <div className="empty" style={{ border: 0, padding: "72px 24px" }}>
                <div className="empty-title">Κανένα query ακόμα</div>
                <div className="empty-body">
                  Πρόσθεσε stats στα αριστερά, δώσε τιμές και βάρη, και πάτα <b>Run match</b>. Η
                  απόσταση υπολογίζεται μόνο πάνω στις διαστάσεις που όρισες.
                </div>
              </div>
            )}

            {!loading && results && results.length === 0 && (
              <div className="empty" style={{ border: 0, padding: "72px 24px" }}>
                <div className="empty-title">0 season-rows ταιριάζουν</div>
                <div className="empty-body">
                  Το εύρος {yearRange[0]}–{yearRange[1]} δεν αφήνει τίποτα. Χαλάρωσε ένα περιορισμό —
                  διεύρυνε τις σεζόν ή αφαίρεσε ένα ακραίο stat.
                </div>
              </div>
            )}

            {!loading && visibleResults && results && results.length > 0 && visibleResults.length === 0 && (
              <div className="empty" style={{ border: 0, padding: "72px 24px" }}>
                <div className="empty-title">Τα φίλτρα έκοψαν όλα τα αποτελέσματα</div>
                <div className="empty-body">
                  {compactCount(results.length)} matches υπάρχουν, αλλά κανένα δεν περνά τα ενεργά
                  φίλτρα{positionFilter && ` (θέση ${positionFilter})`}
                  {requireFullCoverage && " (πλήρης κάλυψη)"}.
                </div>
                {/* Το coverage notice — που κρατά το toggle — εξαφανίζεται όταν
                    δεν μένει κανένα ορατό row, οπότε χωρίς αυτά τα κουμπιά ο
                    χρήστης κλειδώνεται σε ένα φίλτρο που δεν μπορεί να λύσει. */}
                <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
                  {requireFullCoverage && (
                    <button type="button" className="btn btn-sm" onClick={() => setRequireFullCoverage(false)}>
                      Δείξε και τα μερικά
                    </button>
                  )}
                  {positionFilter && (
                    <button type="button" className="btn btn-sm" onClick={() => setPositionFilter("")}>
                      Καθάρισε τη θέση
                    </button>
                  )}
                </div>
              </div>
            )}

            {!loading &&
              visibleResults?.map((r) => {
                const key = rowKey(r);
                return (
                  <ResultRow
                    key={key}
                    r={r}
                    requested={requested}
                    weights={ranQuery?.weights ?? {}}
                    statByKey={statByKey}
                    open={expanded === key}
                    onToggle={() => setExpanded((prev) => (prev === key ? null : key))}
                    onUseAsTarget={useAsTarget}
                    onSaveComp={prefillSource ? handleSaveComps : undefined}
                  />
                );
              })}
          </div>

          {ranQuery && visibleResults && visibleResults.length > 0 && (
            <div className="statusstrip" style={{ borderTop: "1px solid var(--line-soft)", borderBottom: 0 }}>
              <span>
                {ranQuery.keys.map((k) => (statByKey[k] ? shortLabel(statByKey[k]) : k)).join(" · ")}
              </span>
              <span className="push">
                {yearRange[0]}–{yearRange[1]}
              </span>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function rowKey(r: MatchResult): string {
  return `${r.player_name}::${r.season}`;
}
