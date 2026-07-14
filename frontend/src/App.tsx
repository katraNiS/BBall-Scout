import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "./api";
import type { StatMeta, MatchResult } from "./types";
import StatBuilder, { type Controls } from "./components/StatBuilder";
import ResultCard from "./components/ResultCard";

export default function App() {
  const [stats, setStats] = useState<StatMeta[]>([]);
  const [traits, setTraits] = useState<string[]>([]);
  const [traitLabels, setTraitLabels] = useState<Record<string, string>>({});
  const [controls, setControls] = useState<Controls>({});

  const [selectedTraits, setSelectedTraits] = useState<string[]>([]);
  const [yearRange, setYearRange] = useState<[number, number]>([2010, 2025]);
  const [topN, setTopN] = useState(10);

  const [results, setResults] = useState<MatchResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [metaError, setMetaError] = useState<string | null>(null);
  const [backendOk, setBackendOk] = useState<boolean | null>(null);

  // ── Load metadata στο mount ────────────────────────────────────────────────
  useEffect(() => {
    (async () => {
      try {
        const meta = await api.statsMeta();
        setStats(meta.stats);
        setTraits(meta.traits);
        setTraitLabels(meta.trait_labels);
        const init: Controls = {};
        for (const s of meta.stats) {
          init[s.key] = { enabled: false, value: s.default, weight: 1 };
        }
        setControls(init);
        setBackendOk(true);
      } catch (e) {
        setMetaError(e instanceof ApiError ? e.message : String(e));
        setBackendOk(false);
      }
    })();
  }, []);

  const enabledKeys = useMemo(
    () => stats.map((s) => s.key).filter((k) => controls[k]?.enabled),
    [stats, controls]
  );

  const patchControl = (key: string, patch: Partial<Controls[string]>) =>
    setControls((prev) => ({ ...prev, [key]: { ...prev[key], ...patch } }));

  // ── Run search ─────────────────────────────────────────────────────────────
  const runSearch = async () => {
    const statsPayload: Record<string, number> = {};
    const weightsPayload: Record<string, number> = {};
    for (const key of enabledKeys) {
      const c = controls[key];
      statsPayload[key] = c.value;
      if (c.weight !== 1) weightsPayload[key] = c.weight;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await api.similar({
        stats: statsPayload,
        weights: Object.keys(weightsPayload).length ? weightsPayload : undefined,
        top_n: topN,
        active_traits: selectedTraits.length ? selectedTraits : undefined,
        season_range: `${yearRange[0]}-${yearRange[1]}`,
      });
      setResults(res.results);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
      setResults(null);
    } finally {
      setLoading(false);
    }
  };

  const statByKey = useMemo(() => {
    const m: Record<string, StatMeta> = {};
    for (const s of stats) m[s.key] = s;
    return m;
  }, [stats]);

  const showRadar = enabledKeys.length >= 3;

  // ── Metadata load failure ────────────────────────────────────────────────────
  if (metaError) {
    return (
      <div className="state-msg">
        <div className="error-box" style={{ maxWidth: 480, margin: "80px auto" }}>
          <b>Αποτυχία σύνδεσης με τον backend.</b>
          <div style={{ marginTop: 8 }}>{metaError}</div>
          <div style={{ marginTop: 10, color: "var(--text-dim2)" }}>
            Ξεκίνα τον server: <code>uvicorn main:app</code> στο <code>backend/</code>.
          </div>
        </div>
      </div>
    );
  }

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
                <h3 className="results-head">Top {results.length} matches</h3>
                {results.map((r) => (
                  <ResultCard key={`${r.player_name}-${r.season}`} r={r} showRadar={showRadar} />
                ))}
              </>
            )}
          </>
        )}
      </main>
    </div>
  );
}
