import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../api";
import type { Prospect, ProspectCreate, ProspectPosition } from "../types";
import { deriveAge, toFromProspectPrefill } from "../prospectUtils";
import { useMeta } from "../MetaContext";

const POSITIONS: ProspectPosition[] = ["G", "G-F", "F", "F-C", "C"];

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

// Client-side validation — καθρεφτίζει τα bounds του backend (schemas.py) ώστε
// ο χρήστης να πάρει inline μήνυμα αντί για 422 μετά το submit.
function validate(form: FormState): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!form.first_name.trim()) errors.first_name = "Υποχρεωτικό.";
  if (!form.last_name.trim()) errors.last_name = "Υποχρεωτικό.";

  if (form.age_manual.trim() !== "") {
    const age = parseOptionalInt(form.age_manual);
    if (age == null || age < 14 || age > 50) errors.age_manual = "Ηλικία 14–50.";
  }
  if (form.height_cm.trim() !== "") {
    const h = parseOptionalFloat(form.height_cm);
    if (h == null || h < 150 || h > 250) errors.height_cm = "Ύψος 150–250 cm.";
  }
  if (form.weight_kg.trim() !== "") {
    const w = parseOptionalFloat(form.weight_kg);
    if (w == null || w < 50 || w > 180) errors.weight_kg = "Βάρος 50–180 kg.";
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
  const { stats: statsMeta } = useMeta();

  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  // Το πλήρες record (χρειάζεται για "Find NBA comps" + τα saved comps) — ξεχωριστό
  // από το FormState, που κρατά μόνο τα πεδία επεξεργάσιμα ως controlled inputs.
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

  const statLabel = (key: string) => statsMeta.find((s) => s.key === key)?.label ?? key;

  const handleDeleteComp = async (compId: string) => {
    if (!prospect) return;
    if (!window.confirm("Διαγραφή αυτού του comp set; Δεν αναιρείται.")) return;
    try {
      await api.prospects.removeComp(prospect.id, compId);
      setProspect((prev) => (prev ? { ...prev, comps: prev.comps.filter((c) => c.id !== compId) } : prev));
    } catch (e) {
      setServerError(e instanceof ApiError ? e.message : String(e));
    }
  };

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

  const liveAge = deriveAge({
    birth_date: form.birth_date || null,
    age_manual: parseOptionalInt(form.age_manual),
  });

  if (loading) {
    return (
      <main className="main">
        <div className="state-msg">
          <span className="spinner" /> &nbsp;Φόρτωση...
        </div>
      </main>
    );
  }

  if (notFound) {
    return (
      <main className="main">
        <div className="not-found-card">
          <div className="empty-state-title">Ο prospect δεν βρέθηκε</div>
          <p className="empty-state-body">Ίσως διαγράφηκε ήδη.</p>
          <Link className="run-btn empty-state-cta" to="/prospects">
            ← Πίσω στη λίστα
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="main">
      <header>
        <h2>{isEdit ? "Επεξεργασία prospect" : "Νέος prospect"}</h2>
        <p className="lede">
          Μόνο το όνομα και το επώνυμο είναι υποχρεωτικά — συμπλήρωσε τα υπόλοιπα όποτε τα μάθεις.
        </p>
      </header>

      {isEdit && prospect && (
        <button
          type="button"
          className="run-btn find-comps-btn"
          onClick={() =>
            navigate("/search", { state: { fromProspect: toFromProspectPrefill(prospect) } })
          }
        >
          🔍 Βρες NBA comps
        </button>
      )}

      <hr className="divider" />

      {serverError && <div className="error-box">{serverError}</div>}

      {/* noValidate: τα δικά μας inline μηνύματα (fieldErrors) πρέπει να είναι η
          μόνη πηγή αλήθειας — χωρίς αυτό, το native constraint validation του
          browser (λόγω min/max στα number inputs) μπλοκάρει σιωπηλά το submit
          ΠΡΙΝ καν τρέξει το validate() μας, χωρίς κανένα ορατό μήνυμα. */}
      <form className="prospect-form" onSubmit={handleSubmit} noValidate>
        <div className="form-row">
          <label>
            Όνομα *
            <input
              type="text"
              value={form.first_name}
              onChange={(e) => patch({ first_name: e.target.value })}
            />
            {fieldErrors.first_name && <div className="field-error">{fieldErrors.first_name}</div>}
          </label>
          <label>
            Επώνυμο *
            <input
              type="text"
              value={form.last_name}
              onChange={(e) => patch({ last_name: e.target.value })}
            />
            {fieldErrors.last_name && <div className="field-error">{fieldErrors.last_name}</div>}
          </label>
        </div>

        <div className="form-row">
          <label>
            Ημ/νία γέννησης
            <input
              type="date"
              value={form.birth_date}
              onChange={(e) => patch({ birth_date: e.target.value })}
            />
            {liveAge != null && <div className="field-hint">Ηλικία: {liveAge} ετών</div>}
          </label>
          <label>
            Ηλικία (αν δεν ξέρεις την ημ/νία)
            <input
              type="number"
              min={14}
              max={50}
              value={form.age_manual}
              onChange={(e) => patch({ age_manual: e.target.value })}
              disabled={!!form.birth_date}
            />
            {fieldErrors.age_manual && <div className="field-error">{fieldErrors.age_manual}</div>}
          </label>
        </div>

        <div className="form-row">
          <label>
            Ύψος (cm)
            <input
              type="number"
              min={150}
              max={250}
              value={form.height_cm}
              onChange={(e) => patch({ height_cm: e.target.value })}
            />
            {fieldErrors.height_cm && <div className="field-error">{fieldErrors.height_cm}</div>}
          </label>
          <label>
            Βάρος (kg)
            <input
              type="number"
              min={50}
              max={180}
              value={form.weight_kg}
              onChange={(e) => patch({ weight_kg: e.target.value })}
            />
            {fieldErrors.weight_kg && <div className="field-error">{fieldErrors.weight_kg}</div>}
          </label>
        </div>

        <div className="form-row">
          <label>
            Θέση
            <select
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
          </label>
          <label>
            Εθνικότητα
            <input
              type="text"
              value={form.nationality}
              onChange={(e) => patch({ nationality: e.target.value })}
            />
          </label>
        </div>

        <div className="form-row">
          <label>
            Ομάδα
            <input type="text" value={form.team} onChange={(e) => patch({ team: e.target.value })} />
          </label>
          <label>
            League
            <input
              type="text"
              value={form.league}
              onChange={(e) => patch({ league: e.target.value })}
            />
          </label>
        </div>

        <label className="form-row-full">
          Σημειώσεις
          <textarea
            rows={5}
            maxLength={2000}
            value={form.notes}
            onChange={(e) => patch({ notes: e.target.value })}
          />
        </label>

        <div className="form-actions">
          <button className="run-btn" type="submit" disabled={saving}>
            {saving ? "Αποθήκευση..." : isEdit ? "Αποθήκευση αλλαγών" : "Δημιουργία prospect"}
          </button>
          <Link className="link-btn" to="/prospects">
            Ακύρωση
          </Link>
        </div>
      </form>

      {isEdit && prospect && (
        <section className="comps-section">
          <hr className="divider" />
          <h3>Αποθηκευμένα NBA comps</h3>
          {prospect.comps.length === 0 ? (
            <div className="state-msg small">
              Δεν έχουν αποθηκευτεί comps ακόμα. Πάτησε "Βρες NBA comps" παραπάνω, τρέξε ένα search
              και αποθήκευσέ το.
            </div>
          ) : (
            prospect.comps.map((c) => (
              <div className="comp-card" key={c.id}>
                <div className="comp-card-top">
                  <span className="comp-date">{new Date(c.created_at).toLocaleString("el-GR")}</span>
                  <button className="link-btn danger" onClick={() => handleDeleteComp(c.id)}>
                    Διαγραφή
                  </button>
                </div>
                <div className="comp-query">
                  {Object.entries(c.query.stats).map(([k, v], i) => (
                    <span key={k}>
                      {i > 0 && " · "}
                      <b>{statLabel(k)}</b>: {v}
                    </span>
                  ))}
                  {c.query.season_range && <span className="comp-query-range"> ({c.query.season_range})</span>}
                </div>
                <ol className="comp-results">
                  {c.results.slice(0, 5).map((r) => (
                    <li key={`${r.player_name}-${r.season}`}>
                      {r.player_name} ({r.season}) — {Math.round(r.similarity * 100)}%{" "}
                      <span className="comp-arch">{r.compound_archetype}</span>
                    </li>
                  ))}
                </ol>
              </div>
            ))
          )}
        </section>
      )}
    </main>
  );
}
