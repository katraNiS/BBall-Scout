import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import { useMeta } from "../MetaContext";
import type { Prospect, SearchHistoryEntry, StatMeta } from "../types";
import { deriveAge, prospectFullName } from "../prospectUtils";
import { compactCount, formatWithUnit, shortLabel } from "../statFormat";
import type { FromSearchRestore } from "./SearchScreen";

function initialsOf(p: Prospect): string {
  return `${p.first_name[0] ?? ""}${p.last_name[0] ?? ""}`.toUpperCase() || "—";
}

// Σύντομος χρόνος για πυκνή στήλη 62px: ώρα αν είναι σήμερα, αλλιώς μέρες/εβδομάδες.
function shortTime(iso: string): string {
  const then = new Date(iso);
  const mins = Math.floor((Date.now() - then.getTime()) / 60000);
  if (mins < 60 * 12) return then.toLocaleTimeString("el-GR", { hour: "2-digit", minute: "2-digit" });
  const days = Math.floor(mins / 1440);
  if (days < 1) return "χθες";
  if (days < 7) return `${days}μ`;
  if (days < 60) return `${Math.floor(days / 7)}εβδ`;
  return `${Math.floor(days / 30)}μήν`;
}

export default function HomeScreen() {
  const { stats } = useMeta();
  const navigate = useNavigate();

  const [health, setHealth] = useState<{ status: string; players: number; rows: number } | null>(null);
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

  const statByKey = useMemo(() => {
    const m: Record<string, StatMeta> = {};
    for (const s of stats) m[s.key] = s;
    return m;
  }, [stats]);

  // Ένα query σε μία γραμμή monospace: "PTS 26.4 ×3 · TS% 60.5 · AST% 28.4 +2"
  const summarizeQuery = (entry: SearchHistoryEntry): string => {
    const parts = Object.entries(entry.query.stats).map(([k, v]) => {
      const meta = statByKey[k];
      const w = entry.query.weights?.[k];
      const label = meta ? shortLabel(meta) : k;
      const value = meta ? formatWithUnit(meta, v) : String(v);
      return `${label} ${value}${w && w !== 1 ? ` ×${w}` : ""}`;
    });
    if (parts.length <= 3) return parts.join(" · ");
    return `${parts.slice(0, 3).join(" · ")} +${parts.length - 3}`;
  };

  const totalComps = prospects?.reduce((t, p) => t + p.comps.length, 0) ?? 0;
  const recentProspects = prospects ? prospects.slice(0, 6) : []; // ήδη newest-updated-first
  const recentSearches = searches ? searches.slice(0, 10) : [];

  const restoreSearch = (entry: SearchHistoryEntry) => {
    const state: { fromSearch: FromSearchRestore } = {
      fromSearch: {
        stats: entry.query.stats,
        weights: entry.query.weights,
        season_range: entry.query.season_range,
        active_traits: entry.query.active_traits,
        top_n: entry.top_n,
      },
    };
    navigate("/search", { state });
  };

  const tiles = [
    {
      label: "Season rows",
      value: health ? compactCount(health.rows) : "—",
      sub: "μετά το tiered MPG filter",
    },
    {
      label: "Distinct players",
      value: health ? compactCount(health.players) : "—",
      sub: health && health.players ? `~${(health.rows / health.players).toFixed(1)} σεζόν ανά παίκτη` : "—",
    },
    {
      label: "Features indexed",
      value: stats.length ? String(stats.length) : "—",
      sub: `${new Set(stats.map((s) => s.group)).size} κατηγορίες · z-scored`,
    },
    {
      label: "Prospects / comps",
      value: prospects ? `${prospects.length}` : "—",
      sub: `${totalComps} αποθηκευμένα comp sets`,
    },
  ];

  return (
    <div className="screen">
      <div className="screen-scroll">
        <div className="workspace">
          <div className="ws-head">
            <div>
              <h3 className="h-screen">Workspace</h3>
              <div className="sub">
                {healthError
                  ? "Ο backend δεν απαντά — τα νούμερα παρακάτω είναι κενά."
                  : "Το dataset φορτώνεται μία φορά στο startup και μένει in-memory."}
              </div>
            </div>
            <div className="ws-actions">
              <Link to="/search" className="btn btn-primary">
                Νέα αναζήτηση
              </Link>
              <Link to="/prospects/new" className="btn">
                Νέο prospect
              </Link>
            </div>
          </div>

          <div className="ws-tiles">
            {tiles.map((t) => (
              <div className="ws-tile" key={t.label}>
                <div className="label" style={{ marginBottom: 6 }}>
                  {t.label}
                </div>
                <div className="ws-tile-value">{t.value}</div>
                <div className="ws-tile-sub">{t.sub}</div>
              </div>
            ))}
          </div>

          <div className="ws-cols">
            {/* ── Recent prospects ── */}
            <section>
              <div className="panel-head">
                <span className="panel-title">Πρόσφατα prospects</span>
                {prospects && prospects.length > 0 && (
                  <Link to="/prospects" className="linkbtn" style={{ textDecoration: "none" }}>
                    Όλα ({prospects.length})
                  </Link>
                )}
              </div>

              {prospectsError ? (
                <div className="loading">{prospectsError}</div>
              ) : !prospects ? (
                <div className="loading">
                  <span className="spinner" /> Φόρτωση…
                </div>
              ) : prospects.length === 0 ? (
                <div className="empty" style={{ marginTop: 16 }}>
                  <div className="empty-title">Κανένα prospect ακόμα</div>
                  <div className="empty-body">
                    Καταχώρησε physicals και σημειώσεις ενός παίκτη, και μετά τρέξε comp search
                    κατευθείαν από την καρτέλα του.
                  </div>
                  <Link to="/prospects/new" className="btn">
                    Πρόσθεσε prospect
                  </Link>
                </div>
              ) : (
                recentProspects.map((p) => {
                  const age = deriveAge(p);
                  return (
                    <Link className="rp-row" to={`/prospects/${p.id}/edit`} key={p.id}>
                      <span className="initials">{initialsOf(p)}</span>
                      <span style={{ flex: 1, minWidth: 0 }}>
                        <span className="rp-name" style={{ display: "block" }}>
                          {prospectFullName(p)}
                        </span>
                        <span className="rp-meta">
                          {p.position ?? "—"}
                          {age != null ? ` · ${age}ε` : ""}
                          {p.height_cm ? ` · ${p.height_cm.toFixed(0)}cm` : ""}
                          {p.team ? ` · ${p.team}` : ""}
                        </span>
                      </span>
                      <span className="rp-num">{p.comps.length} sets</span>
                      <span className="rp-num" style={{ width: 64, textAlign: "right" }}>
                        {shortTime(p.updated_at)}
                      </span>
                    </Link>
                  );
                })
              )}
            </section>

            {/* ── Search history ── */}
            <section>
              <div className="panel-head">
                <span className="panel-title">Ιστορικό αναζητήσεων</span>
                <span className="sub-mono">τελευταίες 20</span>
              </div>

              {searchesError ? (
                <div className="loading">{searchesError}</div>
              ) : !searches ? (
                <div className="loading">
                  <span className="spinner" /> Φόρτωση…
                </div>
              ) : searches.length === 0 ? (
                <div className="empty" style={{ marginTop: 16 }}>
                  <div className="empty-title">Καμία αναζήτηση ακόμα</div>
                  <div className="empty-body">
                    Κάθε search καταγράφεται εδώ με τα stats που ζήτησες και τα top matches — ένα κλικ
                    το επαναφέρει ολόκληρο στον builder.
                  </div>
                  <Link to="/search" className="btn">
                    Ξεκίνα αναζήτηση
                  </Link>
                </div>
              ) : (
                recentSearches.map((entry) => {
                  const top = entry.top_results[0];
                  return (
                    <button
                      type="button"
                      className="hist-row"
                      key={entry.id}
                      title={top ? `Top: ${top.player_name} (${top.season})` : undefined}
                      onClick={() => restoreSearch(entry)}
                    >
                      <span className="hist-time">{shortTime(entry.created_at)}</span>
                      <span className="hist-query">{summarizeQuery(entry)}</span>
                      <span className="hist-n">{Object.keys(entry.query.stats).length} stats</span>
                      <span className="hist-top">
                        {top ? `${Math.round(top.similarity * 100)}%` : "—"}
                      </span>
                    </button>
                  );
                })
              )}
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}
