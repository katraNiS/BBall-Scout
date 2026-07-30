import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api, ApiError } from "../api";
import type { MatchResult, StatMeta } from "../types";
import { useMeta } from "../MetaContext";
import StatBuilder, { type Controls } from "../components/StatBuilder";
import ResultCard from "../components/ResultCard";
import { kgToLbs, roundToStep } from "../units";
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
  const { stats, traits, traitLabels, backendOk } = useMeta();
  const location = useLocation();
  const [controls, setControls] = useState<Controls>({});

  const [selectedTraits, setSelectedTraits] = useState<string[]>([]);
  const [yearRange, setYearRange] = useState<[number, number]>([2010, 2025]);
  const [topN, setTopN] = useState(10);

  const [results, setResults] = useState<MatchResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [positionFilter, setPositionFilter] = useState("");

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
    try {
      const res = await api.similar({
        ...buildQuery(),
        top_n: topN,
        prospect_id: prefillSource?.id ?? null,
      });
      setResults(res.results);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
      setResults(null);
    } finally {
      setLoading(false);
    }
  };

  // ── Save comps στον prospect που ξεκίνησε αυτό το search (Direction 2) ─────
  // Σώζει τα filteredResults (ό,τι βλέπει ο χρήστης) όχι το ωμό results — αν έχει
  // φιλτράρει κατά θέση, το comp set πρέπει να αντανακλά αυτό που κοιτάει.
  const handleSaveComps = async () => {
    if (!prefillSource || !filteredResults?.length) return;
    setSavingComps(true);
    setSaveCompsMsg(null);
    try {
      await api.prospects.addComp(prefillSource.id, {
        label: null,
        query: buildQuery(),
        results: filteredResults.map((r) => ({
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

  const statByKey = useMemo(() => {
    const m: Record<string, StatMeta> = {};
    for (const s of stats) m[s.key] = s;
    return m;
  }, [stats]);

  const showRadar = enabledKeys.length >= 3;

  // ── Position filter + CSV export (client-side — τα δεδομένα ήδη υπάρχουν) ──
  const filteredResults = useMemo(() => {
    if (!results) return null;
    return positionFilter ? results.filter((r) => r.position_group === positionFilter) : results;
  }, [results, positionFilter]);

  const handleExportCsv = () => {
    if (!filteredResults?.length) return;
    const dateStr = new Date().toISOString().slice(0, 10);
    downloadCsv(`prospectmatch-results-${dateStr}.csv`, matchResultsToCsv(filteredResults));
  };

  return (
    <div className="layout">
      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <h1>🏀 ProspectMatch</h1>
        <div className="subtitle">NBA Player Similarity Engine</div>

        <section>
          <h3>Season Range</h3>
          <div className="range-row">
            <input
              type="range"
              min={1996}
              max={2025}
              value={yearRange[0]}
              onChange={(e) =>
                setYearRange([Math.min(+e.target.value, yearRange[1]), yearRange[1]])
              }
            />
            <input
              type="range"
              min={1996}
              max={2025}
              value={yearRange[1]}
              onChange={(e) =>
                setYearRange([yearRange[0], Math.max(+e.target.value, yearRange[0])])
              }
            />
          </div>
          <div className="range-val" style={{ textAlign: "left" }}>
            {yearRange[0]} – {yearRange[1]}
          </div>
        </section>

        <section>
          <h3>Trait Boost</h3>
          <div className="hint">Μικρό bonus για παίκτες με αυτά τα traits — δεν αποκλείει κανέναν.</div>
          <select
            multiple
            value={selectedTraits}
            onChange={(e) =>
              setSelectedTraits(Array.from(e.target.selectedOptions, (o) => o.value))
            }
          >
            {traits.map((t) => (
              <option key={t} value={t}>
                {traitLabels[t] ?? t}
              </option>
            ))}
          </select>
        </section>

        <section>
          <h3>Αριθμός αποτελεσμάτων: {topN}</h3>
          <div className="range-row">
            <input
              type="range"
              min={5}
              max={20}
              value={topN}
              onChange={(e) => setTopN(+e.target.value)}
            />
          </div>
        </section>

        <div className="status-line">
          <span className={`status-dot ${backendOk ? "ok" : "down"}`} />
          {backendOk ? `Connected — ${api.base}` : "Backend offline"}
        </div>
      </aside>

      {/* ── Main ── */}
      <main className="main">
        <header>
          <h2>ProspectMatch</h2>
          <p className="lede">
            Ορίσε το player profile που ψάχνεις — stats + βάρη — και βρες τους πιο όμοιους
            παίκτες της NBA.
          </p>
        </header>
        <hr className="divider" />

        {(prefillSource || restoredFromHistory) && !bannerDismissed && (
          <div className="prefill-banner">
            {prefillSource ? (
              <>
                Prefilled από{" "}
                <Link to={`/prospects/${prefillSource.id}/edit`}>{prefillSource.name}</Link>
              </>
            ) : (
              "Επαναφορά προηγούμενης αναζήτησης"
            )}
            <button className="link-btn" onClick={() => setBannerDismissed(true)}>
              Κλείσιμο
            </button>
          </div>
        )}

        <StatBuilder stats={stats} controls={controls} onChange={patchControl} />

        {enabledKeys.length > 0 && (
          <div className="summary-pills">
            {enabledKeys.map((k, i) => {
              const c = controls[k];
              const meta = statByKey[k];
              const dec = meta.step < 1 ? (meta.step < 0.5 ? 2 : 1) : 0;
              return (
                <span key={k}>
                  {i > 0 && " · "}
                  <b>{meta.label}</b>: {c.value.toFixed(dec)}
                  {meta.unit}
                  {c.weight !== 1 && <span className="wt"> ×{c.weight}</span>}
                </span>
              );
            })}
          </div>
        )}

        <button
          className="run-btn"
          disabled={enabledKeys.length === 0 || loading}
          onClick={runSearch}
        >
          {loading ? (
            <>
              <span className="spinner" /> &nbsp;Αναζήτηση...
            </>
          ) : enabledKeys.length === 0 ? (
            "Άναψε τουλάχιστον ένα stat"
          ) : (
            "🔍 Βρες παίκτες"
          )}
        </button>

        {error && <div className="error-box">{error}</div>}

        {results && !loading && (
          <>
            {results.length === 0 ? (
              <div className="state-msg">
                Δεν βρέθηκαν αποτελέσματα. Δοκίμασε να διευρύνεις το season range.
              </div>
            ) : (
              <>
                <div className="results-toolbar">
                  <h3 className="results-head">
                    Top {filteredResults?.length ?? 0} matches
                    {positionFilter && <span className="results-head-filtered"> (φιλτραρισμένα)</span>}
                  </h3>
                  <label className="sort-label">
                    Θέση:&nbsp;
                    <select
                      value={positionFilter}
                      onChange={(e) => setPositionFilter(e.target.value)}
                    >
                      <option value="">Όλες</option>
                      {POSITION_FILTERS.map((p) => (
                        <option key={p} value={p}>
                          {p}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    className="link-btn export-csv-btn"
                    disabled={!filteredResults?.length}
                    onClick={handleExportCsv}
                  >
                    ⬇ Export CSV
                  </button>
                </div>

                {prefillSource && (
                  <div className="save-comps-row">
                    <button
                      className="run-btn save-comps-btn"
                      disabled={savingComps || !filteredResults?.length}
                      onClick={handleSaveComps}
                    >
                      {savingComps
                        ? "Αποθήκευση..."
                        : `💾 Αποθήκευση αυτών των comps στον/στην ${prefillSource.name}`}
                    </button>
                    {saveCompsMsg && <span className="save-comps-msg">{saveCompsMsg}</span>}
                  </div>
                )}

                {filteredResults?.length === 0 ? (
                  <div className="state-msg">Καμία θέση "{positionFilter}" στα αποτελέσματα.</div>
                ) : (
                  filteredResults?.map((r) => (
                    <ResultCard key={`${r.player_name}-${r.season}`} r={r} showRadar={showRadar} />
                  ))
                )}
              </>
            )}
          </>
        )}
      </main>
    </div>
  );
}
