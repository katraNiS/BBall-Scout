import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../api";
import type { Prospect, ProspectCreate, ProspectPosition, StatMeta } from "../types";
import { deriveAge, prospectFullName, toFromProspectPrefill } from "../prospectUtils";
import { useMeta } from "../MetaContext";
import { formatWithUnit, shortLabel } from "../statFormat";

const POSITIONS: ProspectPosition[] = ["G", "G-F", "F", "F-C", "C"];

// Bounds — καθρεφτίζουν το backend/schemas.py ώστε ο χρήστης να παίρνει inline
// μήνυμα αντί για 422 μετά το submit.
const BOUNDS = {
  age: [14, 50],
  height: [150, 250],
  weight: [50, 180],
} as const;

interface FormState {
  first_name: string;
  last_name: string;
  birth_date: string;
  age_manual: string;
  height_cm: string;
  weight_kg: string;
  nationality: string;
  team: string;
  league: string;
  position: ProspectPosition | "";
  notes: string;
}

const EMPTY_FORM: FormState = {
  first_name: "",
  last_name: "",
  birth_date: "",
  age_manual: "",
  height_cm: "",
  weight_kg: "",
  nationality: "",
  team: "",
  league: "",
  position: "",
  notes: "",
};

function toFormState(p: Prospect): FormState {
  return {
    first_name: p.first_name,
    last_name: p.last_name,
    birth_date: p.birth_date ?? "",
    age_manual: p.age_manual != null ? String(p.age_manual) : "",
    height_cm: p.height_cm != null ? String(p.height_cm) : "",
    weight_kg: p.weight_kg != null ? String(p.weight_kg) : "",
    nationality: p.nationality ?? "",
    team: p.team ?? "",
    league: p.league ?? "",
    position: p.position ?? "",
    notes: p.notes ?? "",
  };
}

function parseOptionalFloat(s: string): number | null {
  if (s.trim() === "") return null;
  const n = parseFloat(s);
  return Number.isNaN(n) ? null : n;
}

function parseOptionalInt(s: string): number | null {
  if (s.trim() === "") return null;
  const n = parseInt(s, 10);
  return Number.isNaN(n) ? null : n;
}

function validate(form: FormState): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!form.first_name.trim()) errors.first_name = "Υποχρεωτικό.";
  if (!form.last_name.trim()) errors.last_name = "Υποχρεωτικό.";

  if (form.age_manual.trim() !== "") {
    const age = parseOptionalInt(form.age_manual);
    if (age == null || age < BOUNDS.age[0] || age > BOUNDS.age[1])
      errors.age_manual = `Ηλικία ${BOUNDS.age[0]}–${BOUNDS.age[1]}.`;
  }
  if (form.height_cm.trim() !== "") {
    const h = parseOptionalFloat(form.height_cm);
    if (h == null || h < BOUNDS.height[0] || h > BOUNDS.height[1])
      errors.height_cm = `Ύψος ${BOUNDS.height[0]}–${BOUNDS.height[1]} cm.`;
  }
  if (form.weight_kg.trim() !== "") {
    const w = parseOptionalFloat(form.weight_kg);
    if (w == null || w < BOUNDS.weight[0] || w > BOUNDS.weight[1])
      errors.weight_kg = `Βάρος ${BOUNDS.weight[0]}–${BOUNDS.weight[1]} kg.`;
  }
  return errors;
}

function toPayload(form: FormState): ProspectCreate {
  return {
    first_name: form.first_name.trim(),
    last_name: form.last_name.trim(),
    birth_date: form.birth_date || null,
    age_manual: parseOptionalInt(form.age_manual),
    height_cm: parseOptionalFloat(form.height_cm),
    weight_kg: parseOptionalFloat(form.weight_kg),
    nationality: form.nationality.trim() || null,
    team: form.team.trim() || null,
    league: form.league.trim() || null,
    position: form.position || null,
    notes: form.notes.trim() || null,
  };
}

export default function ProspectFormScreen() {
  const { id } = useParams<{ id: string }>();
  const isEdit = id !== undefined;
  const navigate = useNavigate();
  const { stats } = useMeta();

  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  // Το πλήρες record (χρειάζεται για "Prefill comp search" + τα saved comps) —
  // ξεχωριστό από το FormState, που κρατά μόνο τα controlled inputs.
  const [prospect, setProspect] = useState<Prospect | null>(null);
  const [loading, setLoading] = useState(isEdit);
  const [notFound, setNotFound] = useState(false);
  const [saving, setSaving] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState<string | null>(null);

  useEffect(() => {
    if (!isEdit) return;
    (async () => {
      try {
        const p = await api.prospects.get(id!);
        setForm(toFormState(p));
        setProspect(p);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) setNotFound(true);
        else setServerError(e instanceof ApiError ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    })();
  }, [id, isEdit]);

  const statByKey = useMemo(() => {
    const m: Record<string, StatMeta> = {};
    for (const s of stats) m[s.key] = s;
    return m;
  }, [stats]);

  const patch = (p: Partial<FormState>) => setForm((prev) => ({ ...prev, ...p }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errors = validate(form);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setSaving(true);
    setServerError(null);
    try {
      const payload = toPayload(form);
      if (isEdit) await api.prospects.update(id!, payload);
      else await api.prospects.create(payload);
      navigate("/prospects");
    } catch (e) {
      setServerError(e instanceof ApiError ? e.message : String(e));
      setSaving(false);
    }
  };

  const handleDeleteComp = async (compId: string) => {
    if (!prospect) return;
    if (!window.confirm("Διαγραφή αυτού του comp set; Δεν αναιρείται.")) return;
    try {
      await api.prospects.removeComp(prospect.id, compId);
      setProspect((prev) =>
        prev ? { ...prev, comps: prev.comps.filter((c) => c.id !== compId) } : prev
      );
    } catch (e) {
      setServerError(e instanceof ApiError ? e.message : String(e));
    }
  };

  const liveAge = deriveAge({
    birth_date: form.birth_date || null,
    age_manual: parseOptionalInt(form.age_manual),
  });

  if (loading) {
    return (
      <div className="screen">
        <div className="loading" style={{ padding: "60px 26px" }}>
          <span className="spinner" /> Φόρτωση…
        </div>
      </div>
    );
  }

  if (notFound) {
    return (
      <div className="screen">
        <div className="empty" style={{ margin: "60px auto", maxWidth: 480 }}>
          <div className="empty-title">Ο prospect δεν βρέθηκε</div>
          <div className="empty-body">Ίσως διαγράφηκε ήδη.</div>
          <Link to="/prospects" className="btn">
            Πίσω στη λίστα
          </Link>
        </div>
      </div>
    );
  }

  // Meter fill: πού πέφτει η τιμή μέσα στα επιτρεπτά bounds — μια οπτική
  // επιβεβαίωση ότι το νούμερο που πληκτρολογήθηκε είναι εύλογο, όχι percentile.
  const meterPct = (value: string, [lo, hi]: readonly [number, number]) => {
    const n = parseOptionalFloat(value);
    if (n == null) return 0;
    return Math.max(0, Math.min(1, (n - lo) / (hi - lo))) * 100;
  };

  const title = isEdit ? prospectFullName(prospect ?? ({} as Prospect)) || "Prospect" : "Νέος prospect";

  return (
    <div className="screen">
      <div className="detail-head">
        <button type="button" className="detail-crumb" onClick={() => navigate("/prospects")}>
          Prospects /
        </button>
        <h3 className="h-screen" style={{ fontSize: 24 }}>
          {title}
        </h3>
        {form.position && <span className="tag">{form.position}</span>}
        {isEdit && prospect && (
          <span className="sub-mono">
            ενημερώθηκε {new Date(prospect.updated_at).toLocaleDateString("el-GR")}
          </span>
        )}

        <div className="push">
          {isEdit && prospect && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() =>
                navigate("/search", { state: { fromProspect: toFromProspectPrefill(prospect) } })
              }
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                <path d="M4 12h10m0 0-4-4m4 4-4 4M17 5v14" />
              </svg>
              Prefill comp search
            </button>
          )}
          <button type="button" className="btn" onClick={handleSubmit} disabled={saving}>
            {saving ? "Αποθήκευση…" : isEdit ? "Αποθήκευση" : "Δημιουργία"}
          </button>
        </div>
      </div>

      {serverError && (
        <div className="notice">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#c58e4a" strokeWidth="1.5">
            <path d="M12 9v4m0 4h.01M10.3 3.9 2.4 17.5A1.9 1.9 0 0 0 4 20.4h16a1.9 1.9 0 0 0 1.6-2.9L13.7 3.9a1.9 1.9 0 0 0-3.4 0Z" />
          </svg>
          <span>{serverError}</span>
        </div>
      )}

      <div className="detail-grid">
        {/* ── Main: identity / physicals / notes ── */}
        <div className="detail-main">
          {/* noValidate: τα δικά μας inline μηνύματα πρέπει να είναι η μόνη πηγή
              αλήθειας — αλλιώς το native constraint validation (λόγω min/max στα
              number inputs) μπλοκάρει σιωπηλά το submit ΠΡΙΝ τρέξει το validate(). */}
          <form id="prospect-form" onSubmit={handleSubmit} noValidate>
            <div className="section-rule">
              <span className="label">Identity</span>
            </div>
            <div className="fieldgrid" style={{ marginBottom: 24 }}>
              <div>
                <label className="field-label" htmlFor="f-first">
                  Όνομα *
                </label>
                <input
                  id="f-first"
                  className={`input${fieldErrors.first_name ? " invalid" : ""}`}
                  value={form.first_name}
                  onChange={(e) => patch({ first_name: e.target.value })}
                />
                {fieldErrors.first_name && <div className="field-hint bad">{fieldErrors.first_name}</div>}
              </div>
              <div>
                <label className="field-label" htmlFor="f-last">
                  Επώνυμο *
                </label>
                <input
                  id="f-last"
                  className={`input${fieldErrors.last_name ? " invalid" : ""}`}
                  value={form.last_name}
                  onChange={(e) => patch({ last_name: e.target.value })}
                />
                {fieldErrors.last_name && <div className="field-hint bad">{fieldErrors.last_name}</div>}
              </div>
              <div>
                <label className="field-label" htmlFor="f-pos">
                  Θέση
                </label>
                <select
                  id="f-pos"
                  className="input"
                  value={form.position}
                  onChange={(e) => patch({ position: e.target.value as ProspectPosition | "" })}
                >
                  <option value="">—</option>
                  {POSITIONS.map((pos) => (
                    <option key={pos} value={pos}>
                      {pos}
                    </option>
                  ))}
                </select>
                <div className="field-hint">ίδιο vocabulary με το engine</div>
              </div>
              <div>
                <label className="field-label" htmlFor="f-dob">
                  Ημ/νία γέννησης
                </label>
                <input
                  id="f-dob"
                  className="input mono"
                  type="date"
                  value={form.birth_date}
                  onChange={(e) => patch({ birth_date: e.target.value })}
                />
                {liveAge != null && <div className="field-hint good">ηλικία {liveAge}</div>}
              </div>
              <div>
                <label className="field-label" htmlFor="f-age">
                  Ηλικία (αν λείπει η ημ/νία)
                </label>
                <input
                  id="f-age"
                  className={`input mono${fieldErrors.age_manual ? " invalid" : ""}`}
                  type="number"
                  min={BOUNDS.age[0]}
                  max={BOUNDS.age[1]}
                  value={form.age_manual}
                  disabled={!!form.birth_date}
                  onChange={(e) => patch({ age_manual: e.target.value })}
                />
                {fieldErrors.age_manual && <div className="field-hint bad">{fieldErrors.age_manual}</div>}
              </div>
              <div>
                <label className="field-label" htmlFor="f-nat">
                  Εθνικότητα
                </label>
                <input
                  id="f-nat"
                  className="input"
                  value={form.nationality}
                  onChange={(e) => patch({ nationality: e.target.value })}
                />
              </div>
              <div>
                <label className="field-label" htmlFor="f-team">
                  Ομάδα
                </label>
                <input
                  id="f-team"
                  className="input"
                  value={form.team}
                  onChange={(e) => patch({ team: e.target.value })}
                />
              </div>
              <div>
                <label className="field-label" htmlFor="f-league">
                  League
                </label>
                <input
                  id="f-league"
                  className="input"
                  value={form.league}
                  onChange={(e) => patch({ league: e.target.value })}
                />
              </div>
            </div>

            <div className="section-rule">
              <span className="label">Physicals — τροφοδοτούν το comp search</span>
            </div>
            <div className="fieldgrid">
              <div>
                <label className="field-label" htmlFor="f-height">
                  Ύψος
                </label>
                <div className="field-wrap">
                  <input
                    id="f-height"
                    className={`input mono${fieldErrors.height_cm ? " invalid" : ""}`}
                    type="number"
                    min={BOUNDS.height[0]}
                    max={BOUNDS.height[1]}
                    value={form.height_cm}
                    onChange={(e) => patch({ height_cm: e.target.value })}
                  />
                  <span className="field-unit">cm</span>
                </div>
                <div className="field-meter">
                  <div style={{ width: `${meterPct(form.height_cm, BOUNDS.height)}%` }} />
                </div>
                <div className={`field-hint${fieldErrors.height_cm ? " bad" : ""}`}>
                  {fieldErrors.height_cm ?? `επιτρεπτό ${BOUNDS.height[0]}–${BOUNDS.height[1]}`}
                </div>
              </div>
              <div>
                <label className="field-label" htmlFor="f-weight">
                  Βάρος
                </label>
                <div className="field-wrap">
                  <input
                    id="f-weight"
                    className={`input mono${fieldErrors.weight_kg ? " invalid" : ""}`}
                    type="number"
                    min={BOUNDS.weight[0]}
                    max={BOUNDS.weight[1]}
                    value={form.weight_kg}
                    onChange={(e) => patch({ weight_kg: e.target.value })}
                  />
                  <span className="field-unit">kg</span>
                </div>
                <div className="field-meter">
                  <div style={{ width: `${meterPct(form.weight_kg, BOUNDS.weight)}%` }} />
                </div>
                <div className={`field-hint${fieldErrors.weight_kg ? " bad" : ""}`}>
                  {fieldErrors.weight_kg ?? "μετατρέπεται σε lbs για το engine"}
                </div>
              </div>
            </div>

            <div className="section-rule" style={{ marginTop: 26 }}>
              <span className="label">Scouting notes</span>
            </div>
            <textarea
              className="input"
              rows={5}
              maxLength={2000}
              value={form.notes}
              placeholder="Τι είδες, τι πρέπει να αποδείξει, ποια stats πρέπει να βαρύνουν στο comp search."
              onChange={(e) => patch({ notes: e.target.value })}
            />
            <div className="field-hint">{form.notes.length}/2000</div>

            <div style={{ display: "flex", gap: 12, alignItems: "center", marginTop: 20 }}>
              <button type="submit" className="btn btn-primary btn-lg" disabled={saving}>
                {saving ? "Αποθήκευση…" : isEdit ? "Αποθήκευση αλλαγών" : "Δημιουργία prospect"}
              </button>
              <Link to="/prospects" className="linkbtn muted">
                Ακύρωση
              </Link>
            </div>
          </form>
        </div>

        {/* ── Rail: saved comp sets ── */}
        <aside className="detail-rail">
          <div className="panel-head" style={{ marginBottom: 12 }}>
            <span className="panel-title">Αποθηκευμένα comp sets</span>
            <span className="sub-mono">{prospect ? `${prospect.comps.length} / 20` : "—"}</span>
          </div>

          {!isEdit ? (
            <div className="empty" style={{ border: 0, padding: "32px 8px" }}>
              <div className="empty-body">
                Αποθήκευσε πρώτα τον prospect. Μετά, από το comp search, μπορείς να κρατάς σύνολα
                NBA comps πάνω στην καρτέλα του.
              </div>
            </div>
          ) : !prospect || prospect.comps.length === 0 ? (
            <div className="empty" style={{ border: 0, padding: "32px 8px" }}>
              <div className="empty-title">Κανένα comp set</div>
              <div className="empty-body">
                Πάτα «Prefill comp search», τρέξε ένα matching και αποθήκευσε τα αποτελέσματα εδώ.
              </div>
            </div>
          ) : (
            prospect.comps.map((c) => (
              <div className="compset" key={c.id}>
                <div className="compset-top">
                  <span className="compset-title">
                    {c.label ??
                      Object.keys(c.query.stats)
                        .slice(0, 3)
                        .map((k) => (statByKey[k] ? shortLabel(statByKey[k]) : k))
                        .join(" · ")}
                  </span>
                  <span className="compset-date">
                    {new Date(c.created_at).toLocaleDateString("el-GR")}
                  </span>
                </div>

                <div className="sub-mono" style={{ marginBottom: 7, fontSize: 10 }}>
                  {Object.entries(c.query.stats)
                    .map(([k, v]) => {
                      const meta = statByKey[k];
                      return `${meta ? shortLabel(meta) : k} ${meta ? formatWithUnit(meta, v) : v}`;
                    })
                    .join(" · ")}
                  {c.query.season_range && ` · ${c.query.season_range}`}
                </div>

                <div className="compset-rows">
                  {c.results.slice(0, 4).map((r) => (
                    <div className="compset-row" key={`${r.player_name}-${r.season}`}>
                      <span className="compset-name" title={r.compound_archetype}>
                        {r.player_name} · {r.season}
                      </span>
                      <span className="compset-bar">
                        <span style={{ width: `${Math.min(100, r.similarity * 100)}%` }} />
                      </span>
                      <span className="compset-sim">{Math.round(r.similarity * 100)}</span>
                    </div>
                  ))}
                  {c.results.length > 4 && (
                    <div className="sub-mono" style={{ fontSize: 10 }}>
                      +{c.results.length - 4} ακόμα
                    </div>
                  )}
                </div>

                <div className="compset-actions">
                  <button
                    type="button"
                    className="linkbtn"
                    onClick={() =>
                      navigate("/search", {
                        state: {
                          fromSearch: {
                            stats: c.query.stats,
                            weights: c.query.weights,
                            season_range: c.query.season_range,
                            active_traits: c.query.active_traits,
                          },
                        },
                      })
                    }
                  >
                    Άνοιγμα ξανά
                  </button>
                  <button type="button" className="linkbtn danger" onClick={() => handleDeleteComp(c.id)}>
                    Διαγραφή
                  </button>
                </div>
              </div>
            ))
          )}
        </aside>
      </div>
    </div>
  );
}
