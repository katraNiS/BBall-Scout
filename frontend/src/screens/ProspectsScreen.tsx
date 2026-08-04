import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import type { Prospect } from "../types";
import { deriveAge, prospectFullName, toFromProspectPrefill } from "../prospectUtils";

type SortKey = "name" | "position" | "height" | "weight" | "comps" | "updated";

// Ίδια σειρά θέσεων με το ALL_POSITIONS στο src/archetypes.py — ώστε το sort
// "κατά θέση" να βγάζει νόημα (G πριν F πριν C) αντί αλφαβητικά.
const POSITION_ORDER = ["G", "G-F", "F", "F-C", "C"];

// Πόσα κελιά δείχνει η στήλη "comp sets". Το store κόβει στα 20, αλλά μια
// γραμμή 44px χωράει 5 — αρκετά για να διαβάσεις "έχει δουλευτεί ή όχι".
const SET_CELLS = 5;

function initialsOf(p: Prospect): string {
  return `${p.first_name[0] ?? ""}${p.last_name[0] ?? ""}`.toUpperCase() || "—";
}

function relTime(iso: string): string {
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (days < 1) return "σήμερα";
  if (days === 1) return "χθες";
  if (days < 7) return `πριν ${days} μέρες`;
  if (days < 60) return `πριν ${Math.floor(days / 7)} εβδ`;
  return `πριν ${Math.floor(days / 30)} μήνες`;
}

export default function ProspectsScreen() {
  const navigate = useNavigate();
  const [prospects, setProspects] = useState<Prospect[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("updated");
  const [filter, setFilter] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      try {
        setProspects(await api.prospects.list());
      } catch (e) {
        setError(e instanceof ApiError ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const rows = useMemo(() => {
    if (!prospects) return [];
    const q = filter.trim().toLowerCase();
    const list = prospects.filter(
      (p) =>
        !q ||
        `${prospectFullName(p)} ${p.position ?? ""} ${p.team ?? ""} ${p.league ?? ""}`
          .toLowerCase()
          .includes(q)
    );

    const sorted = [...list];
    switch (sortKey) {
      case "name":
        sorted.sort((a, b) => a.last_name.localeCompare(b.last_name, "el"));
        break;
      case "position":
        sorted.sort(
          (a, b) =>
            POSITION_ORDER.indexOf(a.position ?? "") - POSITION_ORDER.indexOf(b.position ?? "")
        );
        break;
      case "height":
        sorted.sort((a, b) => (b.height_cm ?? 0) - (a.height_cm ?? 0));
        break;
      case "weight":
        sorted.sort((a, b) => (b.weight_kg ?? 0) - (a.weight_kg ?? 0));
        break;
      case "comps":
        sorted.sort((a, b) => b.comps.length - a.comps.length);
        break;
      // "updated" — ήδη ταξινομημένο newest-first από το backend
    }
    return sorted;
  }, [prospects, sortKey, filter]);

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

  const totalComps = prospects?.reduce((t, p) => t + p.comps.length, 0) ?? 0;

  const SortHeader = ({ k, children, className }: { k: SortKey; children: string; className?: string }) => (
    <span className={className}>
      <button
        type="button"
        className={`ptable-sort${sortKey === k ? " on" : ""}`}
        onClick={() => setSortKey(k)}
      >
        {children}
        {sortKey === k && (
          <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2">
            <path d="M6 15l6-6 6 6" />
          </svg>
        )}
      </button>
    </span>
  );

  return (
    <div className="screen">
      <div className="plist-head">
        <div>
          <h3 className="h-screen">Prospects</h3>
          <div className="sub">
            {prospects
              ? `${prospects.length} χειρόγραφες εγγραφές · ${totalComps} αποθηκευμένα comp sets`
              : "Παίκτες που παρακολουθείς — ανεξάρτητοι από το NBA dataset."}
          </div>
        </div>
        <div className="plist-tools">
          <input
            className="input"
            style={{ width: 230, height: 32 }}
            placeholder="Φίλτρο: όνομα, θέση, ομάδα"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
          <Link to="/prospects/new" className="btn btn-primary">
            Νέο prospect
          </Link>
        </div>
      </div>

      {error && (
        <div className="notice">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#c58e4a" strokeWidth="1.5">
            <path d="M12 9v4m0 4h.01M10.3 3.9 2.4 17.5A1.9 1.9 0 0 0 4 20.4h16a1.9 1.9 0 0 0 1.6-2.9L13.7 3.9a1.9 1.9 0 0 0-3.4 0Z" />
          </svg>
          <span>{error}</span>
        </div>
      )}

      <div className="screen-scroll">
        <div className="plist-body">
          {loading ? (
            <div className="loading">
              <span className="spinner" /> Φόρτωση…
            </div>
          ) : !prospects || prospects.length === 0 ? (
            <div className="empty" style={{ marginTop: 20 }}>
              <div className="empty-title">Δεν υπάρχουν prospects ακόμα</div>
              <div className="empty-body">
                Ένα prospect είναι ένας παίκτης που παρακολουθείς χειροκίνητα — physicals, ομάδα,
                σημειώσεις. Από την καρτέλα του τρέχεις comp search με prefill τα physicals του.
              </div>
              <Link to="/prospects/new" className="btn">
                Πρόσθεσε τον πρώτο
              </Link>
            </div>
          ) : (
            <>
              <div className="ptable-head">
                <SortHeader k="name" className="prow-name">
                  Name
                </SortHeader>
                <SortHeader k="position" className="pcol-pos">
                  Pos
                </SortHeader>
                <SortHeader k="height" className="pcol-num">
                  Height
                </SortHeader>
                <SortHeader k="weight" className="pcol-num">
                  Weight
                </SortHeader>
                <span className="pcol-num">Age</span>
                <SortHeader k="comps" className="pcol-sets">
                  Comp sets
                </SortHeader>
                <SortHeader k="updated" className="pcol-upd">
                  Updated
                </SortHeader>
                <span className="pcol-act" />
              </div>

              {rows.length === 0 ? (
                <div className="loading">Κανένα prospect δεν ταιριάζει στο «{filter}».</div>
              ) : (
                rows.map((p) => {
                  const age = deriveAge(p);
                  return (
                    <div className="prow" key={p.id}>
                      <span className="prow-name">
                        <span className="initials sm">{initialsOf(p)}</span>
                        <Link to={`/prospects/${p.id}/edit`}>{prospectFullName(p)}</Link>
                        <span className="prow-org">
                          {[p.team, p.league, p.nationality].filter(Boolean).join(" · ")}
                        </span>
                      </span>
                      <span className={`pcol-pos prow-cell${p.position ? "" : " dim"}`}>
                        {p.position ?? "—"}
                      </span>
                      <span className={`pcol-num prow-cell${p.height_cm ? "" : " dim"}`}>
                        {p.height_cm ? `${p.height_cm.toFixed(0)} cm` : "—"}
                      </span>
                      <span className={`pcol-num prow-cell${p.weight_kg ? "" : " dim"}`}>
                        {p.weight_kg ? `${p.weight_kg.toFixed(0)} kg` : "—"}
                      </span>
                      <span className={`pcol-num prow-cell${age != null ? "" : " dim"}`}>
                        {age != null ? age : "—"}
                      </span>
                      <span className="pcol-sets">
                        <span className="setcells">
                          {Array.from({ length: SET_CELLS }, (_, i) => (
                            <span key={i} className={i < Math.min(SET_CELLS, p.comps.length) ? "on" : undefined} />
                          ))}
                        </span>
                        <span className="prow-cell" style={{ color: "var(--text-4)" }}>
                          {p.comps.length}
                        </span>
                      </span>
                      <span className="pcol-upd prow-cell dim">{relTime(p.updated_at)}</span>
                      <span className="pcol-act prow-actions">
                        <button
                          type="button"
                          className="iconbtn"
                          title="Βρες NBA comps με prefill τα physicals"
                          onClick={() =>
                            navigate("/search", { state: { fromProspect: toFromProspectPrefill(p) } })
                          }
                        >
                          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
                            <circle cx="11" cy="11" r="6" />
                            <path d="M20 20l-4.5-4.5" />
                          </svg>
                        </button>
                        <button
                          type="button"
                          className="iconbtn danger"
                          title="Διαγραφή"
                          disabled={deletingId === p.id}
                          onClick={() => handleDelete(p)}
                        >
                          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                            <path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" />
                          </svg>
                        </button>
                      </span>
                    </div>
                  );
                })
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
