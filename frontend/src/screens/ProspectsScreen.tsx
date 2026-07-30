import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import type { Prospect } from "../types";
import { deriveAge, prospectFullName, toFromProspectPrefill } from "../prospectUtils";

type SortMode = "updated" | "last_name" | "position";

// Ίδια σειρά θέσεων με το ALL_POSITIONS στο src/archetypes.py — χρησιμοποιείται
// για να ταξινομήσουμε "κατά θέση" με νόημα (G πριν F πριν C) αντί αλφαβητικά.
const POSITION_ORDER = ["G", "G-F", "F", "F-C", "C"];

export default function ProspectsScreen() {
  const navigate = useNavigate();
  const [prospects, setProspects] = useState<Prospect[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortMode, setSortMode] = useState<SortMode>("updated");
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setProspects(await api.prospects.list());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const sorted = useMemo(() => {
    if (!prospects) return [];
    const list = [...prospects];
    if (sortMode === "last_name") {
      list.sort((a, b) => a.last_name.localeCompare(b.last_name));
    } else if (sortMode === "position") {
      list.sort(
        (a, b) =>
          POSITION_ORDER.indexOf(a.position ?? "") - POSITION_ORDER.indexOf(b.position ?? "")
      );
    }
    // "updated" — ήδη ταξινομημένο newest-first από το backend
    return list;
  }, [prospects, sortMode]);

  const handleDelete = async (p: Prospect) => {
    if (!window.confirm(`Διαγραφή του ${prospectFullName(p)}; Δεν αναιρείται.`)) return;
    setDeletingId(p.id);
    try {
      await api.prospects.remove(p.id);
      setProspects((prev) => (prev ? prev.filter((x) => x.id !== p.id) : prev));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <main className="main">
      <header>
        <h2>Prospects</h2>
        <p className="lede">Οι παίκτες που παρακολουθείς — χειρόγραφες εγγραφές, ανεξάρτητες από το NBA dataset.</p>
      </header>
      <hr className="divider" />

      {error && <div className="error-box">{error}</div>}

      {loading ? (
        <div className="state-msg">
          <span className="spinner" /> &nbsp;Φόρτωση...
        </div>
      ) : !prospects || prospects.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-title">Δεν υπάρχουν prospects ακόμα</div>
          <p className="empty-state-body">
            Ένα prospect είναι ένας παίκτης που παρακολουθείς χειροκίνητα — physicals, ομάδα,
            σημειώσεις. Πρόσθεσε τον πρώτο για να ξεκινήσεις.
          </p>
          <Link className="run-btn empty-state-cta" to="/prospects/new">
            + Πρόσθεσε τον πρώτο prospect
          </Link>
        </div>
      ) : (
        <>
          <div className="prospects-toolbar">
            <Link className="run-btn prospects-add-btn" to="/prospects/new">
              + Νέο prospect
            </Link>
            <label className="sort-label">
              Ταξινόμηση:&nbsp;
              <select value={sortMode} onChange={(e) => setSortMode(e.target.value as SortMode)}>
                <option value="updated">Πρόσφατη ενημέρωση</option>
                <option value="last_name">Επώνυμο</option>
                <option value="position">Θέση</option>
              </select>
            </label>
          </div>

          <div className="prospect-grid">
            {sorted.map((p) => {
              const age = deriveAge(p);
              return (
                <div className="prospect-card" key={p.id}>
                  <div className="prospect-card-top">
                    <Link className="prospect-name" to={`/prospects/${p.id}/edit`}>
                      {prospectFullName(p)}
                    </Link>
                    {p.position && <span className="badge badge-pos">{p.position}</span>}
                  </div>
                  <div className="prospect-card-meta">
                    {age != null ? `${age} ετών` : "Άγνωστη ηλικία"}
                    {" · "}
                    {p.height_cm ? `${p.height_cm.toFixed(0)} cm` : "— cm"}
                    {" / "}
                    {p.weight_kg ? `${p.weight_kg.toFixed(0)} kg` : "— kg"}
                  </div>
                  <div className="prospect-card-meta">
                    {p.team || "—"} {p.league ? `· ${p.league}` : ""}
                  </div>
                  {p.nationality && <div className="prospect-card-nat">{p.nationality}</div>}

                  <div className="prospect-card-actions">
                    <Link to={`/prospects/${p.id}/edit`}>Επεξεργασία</Link>
                    <button
                      className="link-btn"
                      onClick={() =>
                        navigate("/search", { state: { fromProspect: toFromProspectPrefill(p) } })
                      }
                    >
                      Βρες NBA comps
                    </button>
                    <button
                      className="link-btn danger"
                      disabled={deletingId === p.id}
                      onClick={() => handleDelete(p)}
                    >
                      {deletingId === p.id ? "Διαγραφή..." : "Διαγραφή"}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </main>
  );
}
