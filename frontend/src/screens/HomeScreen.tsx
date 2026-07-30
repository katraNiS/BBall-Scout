import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api";
import { useMeta } from "../MetaContext";
import type { Prospect, SearchHistoryEntry } from "../types";
import { deriveAge, prospectFullName } from "../prospectUtils";
import type { FromSearchRestore } from "./SearchScreen";

function timeAgo(iso: string): string {
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "μόλις τώρα";
  if (mins < 60) return `πριν ${mins} λεπτά`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `πριν ${hours} ώρες`;
  const days = Math.floor(hours / 24);
  return `πριν ${days} μέρες`;
}

export default function HomeScreen() {
  const { stats } = useMeta();

  const [health, setHealth] = useState<{ status: string; players: number; rows: number } | null>(
    null
  );
  const [healthError, setHealthError] = useState<string | null>(null);

  const [prospects, setProspects] = useState<Prospect[] | null>(null);
  const [prospectsError, setProspectsError] = useState<string | null>(null);

  const [searches, setSearches] = useState<SearchHistoryEntry[] | null>(null);
  const [searchesError, setSearchesError] = useState<string | null>(null);

  // Παράλληλα fetches — κάθε περιοχή αποτυγχάνει ανεξάρτητα, ώστε π.χ. ένα down
  // search-history endpoint να μην αδειάζει και τη λίστα prospects.
  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch((e) => setHealthError(e instanceof ApiError ? e.message : String(e)));
    api.prospects
      .list()
      .then(setProspects)
      .catch((e) => setProspectsError(e instanceof ApiError ? e.message : String(e)));
    api.searches
      .list()
      .then(setSearches)
      .catch((e) => setSearchesError(e instanceof ApiError ? e.message : String(e)));
  }, []);

  const statLabel = (key: string) => stats.find((s) => s.key === key)?.label ?? key;

  const recentProspects = prospects ? prospects.slice(0, 6) : []; // ήδη newest-updated-first
  const recentSearches = searches ? searches.slice(0, 5) : [];

  const toRestoreState = (entry: SearchHistoryEntry): { fromSearch: FromSearchRestore } => ({
    fromSearch: {
      stats: entry.query.stats,
      weights: entry.query.weights,
      season_range: entry.query.season_range,
      active_traits: entry.query.active_traits,
      top_n: entry.top_n,
    },
  });

  return (
    <main className="main home-screen">
      <header className="home-header">
        <h2>🏀 ProspectMatch</h2>
        <p className="lede">
          Scouting εργαλείο NBA — όρισε ένα player profile και βρες τους πιο όμοιους πραγματικούς
          παίκτες, ή κράτα τα δικά σου prospects.
        </p>
        <div className="status-line">
          {healthError ? (
            <>
              <span className="status-dot down" /> Backend offline
            </>
          ) : health ? (
            <>
              <span className="status-dot ok" /> {health.players} παίκτες · {health.rows} rows
            </>
          ) : (
            "Φόρτωση..."
          )}
        </div>
      </header>

      <div className="home-quick-actions">
        <Link to="/search" className="quick-action-card">
          <div className="quick-action-icon">🔍</div>
          <div className="quick-action-title">Νέα αναζήτηση</div>
          <div className="quick-action-body">
            Όρισε stats + βάρη και βρες τους πιο όμοιους παίκτες της NBA.
          </div>
        </Link>
        <Link to="/prospects/new" className="quick-action-card">
          <div className="quick-action-icon">➕</div>
          <div className="quick-action-title">Πρόσθεσε prospect</div>
          <div className="quick-action-body">Καταχώρησε έναν παίκτη που παρακολουθείς.</div>
        </Link>
      </div>

      <section className="home-section">
        <div className="home-section-head">
          <h3>Οι prospects σου{prospects && prospects.length > 0 ? ` (${prospects.length})` : ""}</h3>
          {prospects && prospects.length > 0 && <Link to="/prospects">Δες όλους →</Link>}
        </div>

        {prospectsError ? (
          <div className="error-box">{prospectsError}</div>
        ) : !prospects ? (
          <div className="state-msg small">
            <span className="spinner" /> &nbsp;Φόρτωση...
          </div>
        ) : prospects.length === 0 ? (
          <div className="empty-state home-empty">
            <div className="empty-state-title">Δεν έχεις προσθέσει κανέναν prospect ακόμα</div>
            <p className="empty-state-body">
              Ένα prospect είναι ένας παίκτης που παρακολουθείς χειροκίνητα — physicals, ομάδα,
              σημειώσεις.
            </p>
            <Link className="run-btn empty-state-cta" to="/prospects/new">
              + Πρόσθεσε τον πρώτο prospect
            </Link>
          </div>
        ) : (
          <div className="home-prospect-grid">
            {recentProspects.map((p) => {
              const age = deriveAge(p);
              return (
                <Link className="home-prospect-card" to={`/prospects/${p.id}/edit`} key={p.id}>
                  <div className="prospect-name">{prospectFullName(p)}</div>
                  <div className="prospect-card-meta">
                    {p.position ?? "—"}
                    {age != null ? ` · ${age} ετών` : ""}
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </section>

      <section className="home-section">
        <div className="home-section-head">
          <h3>Πρόσφατες αναζητήσεις</h3>
        </div>

        {searchesError ? (
          <div className="error-box">{searchesError}</div>
        ) : !searches ? (
          <div className="state-msg small">
            <span className="spinner" /> &nbsp;Φόρτωση...
          </div>
        ) : searches.length === 0 ? (
          <div className="empty-state home-empty">
            <div className="empty-state-title">Δεν έχεις τρέξει καμία αναζήτηση ακόμα</div>
            <p className="empty-state-body">
              Κάθε search που τρέχεις εμφανίζεται εδώ, με τα stats που ζήτησες και τα top matches,
              για γρήγορη επαναφορά.
            </p>
            <Link className="run-btn empty-state-cta" to="/search">
              🔍 Ξεκίνα μια αναζήτηση
            </Link>
          </div>
        ) : (
          <div className="home-search-list">
            {recentSearches.map((entry) => (
              <Link
                className="home-search-card"
                to="/search"
                state={toRestoreState(entry)}
                key={entry.id}
              >
                <div className="home-search-top">
                  <span className="comp-date">{timeAgo(entry.created_at)}</span>
                </div>
                <div className="comp-query">
                  {Object.entries(entry.query.stats).map(([k, v], i) => (
                    <span key={k}>
                      {i > 0 && " · "}
                      <b>{statLabel(k)}</b>: {v}
                    </span>
                  ))}
                </div>
                {entry.top_results.length > 0 && (
                  <div className="home-search-results">
                    {entry.top_results
                      .map((r) => `${r.player_name} (${Math.round(r.similarity * 100)}%)`)
                      .join(" · ")}
                  </div>
                )}
              </Link>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
