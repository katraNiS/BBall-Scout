import { useMemo, useRef, useState } from "react";
import type { StatMeta } from "../types";
import {
  compactCount,
  decimalsFor,
  formatWithUnit,
  normalize,
  percentileOf,
  shortLabel,
} from "../statFormat";

// Ένα control ανά feature: on/off + τιμή (display units) + βάρος.
export interface Control {
  enabled: boolean;
  value: number;
  weight: number;
}

export type Controls = Record<string, Control>;

// Διακριτά βάρη αντί για ελεύθερο number input. Το βάρος είναι δήλωση
// προτεραιότητας ("αυτό μετράει τριπλά"), όχι βαθμονομημένη ποσότητα — τρία
// σκαλιά το εκφράζουν και αφαιρούν μια ολόκληρη κατηγορία λάθους (0.7×, 4.5×)
// που το engine ούτως ή άλλως κανονικοποιεί στο Σw.
const WEIGHTS = [1, 2, 3];

interface Props {
  stats: StatMeta[];
  controls: Controls;
  onChange: (key: string, patch: Partial<Control>) => void;
}

export default function StatBuilder({ stats, controls, onChange }: Props) {
  const [query, setQuery] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);

  const active = useMemo(
    () => stats.filter((s) => controls[s.key]?.enabled),
    [stats, controls]
  );

  // Το πλήρες πλήθος rows = το μέγιστο n_rows ανάμεσα στα features (τα box-score
  // features υπάρχουν για όλη τη βάση). Έτσι το "λιγότερα δεδομένα" σημαδεύεται
  // σχετικά με το dataset, χωρίς hardcoded κατώφλι που θα σάπιζε στο επόμενο fetch.
  const fullRows = useMemo(
    () => stats.reduce((m, s) => Math.max(m, s.n_rows ?? 0), 0),
    [stats]
  );

  // Υποψήφια προς προσθήκη: ό,τι δεν είναι ήδη ενεργό, φιλτραρισμένο σε label +
  // key + group ώστε να δουλεύει και "TS", και "true shooting", και "defense".
  const candidates = useMemo(() => {
    const q = query.trim().toLowerCase();
    return stats
      .filter((s) => !controls[s.key]?.enabled)
      .filter((s) => !q || `${s.label} ${s.key} ${s.group}`.toLowerCase().includes(q))
      .slice(0, 7);
  }, [stats, controls, query]);

  const groups = useMemo(() => {
    const seen: { name: string; count: number }[] = [];
    for (const s of stats) {
      let g = seen.find((x) => x.name === s.group);
      if (!g) {
        g = { name: s.group, count: 0 };
        seen.push(g);
      }
      if (controls[s.key]?.enabled) g.count += 1;
    }
    return seen;
  }, [stats, controls]);

  const add = (meta: StatMeta) => {
    onChange(meta.key, { enabled: true, weight: controls[meta.key]?.weight ?? 1 });
    setQuery("");
    setMenuOpen(false);
    searchRef.current?.focus();
  };

  const showMenu = menuOpen && candidates.length > 0;

  return (
    <>
      <div className="builder-head">
        <div className="builder-head-top">
          <h4 className="h-pane">Stat Builder</h4>
          <span className="sub-mono">
            {active.length}/{stats.length} active
          </span>
        </div>

        <div className="builder-search">
          <input
            ref={searchRef}
            className="input"
            value={query}
            placeholder="Πρόσθεσε stat — γράψε για αναζήτηση (TS, assist, defense)"
            onChange={(e) => {
              setQuery(e.target.value);
              setMenuOpen(true);
            }}
            onFocus={() => setMenuOpen(true)}
            // Το blur καθυστερεί ώστε το click πάνω σε στοιχείο του menu να
            // προλάβει να τρέξει πριν κλείσει το menu.
            onBlur={() => window.setTimeout(() => setMenuOpen(false), 120)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && candidates.length) add(candidates[0]);
              if (e.key === "Escape") setMenuOpen(false);
            }}
          />
          {showMenu && (
            <div className="builder-menu">
              {candidates.map((s, i) => (
                <button
                  key={s.key}
                  type="button"
                  className={`builder-menu-item${i === 0 && query ? " cursor" : ""}`}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => add(s)}
                >
                  <span className="builder-menu-key">{shortLabel(s)}</span>
                  <span className="builder-menu-name">{s.label}</span>
                  <span className="builder-menu-cat">{s.group}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="builder-cats">
          {groups.map((g) => (
            <button
              key={g.name}
              type="button"
              className="chip"
              title={`Δείξε τα stats της κατηγορίας «${g.name}»`}
              onClick={() => {
                setQuery(g.name);
                setMenuOpen(true);
                searchRef.current?.focus();
              }}
            >
              {g.name}
              <span className={`chip-n${g.count ? " has" : ""}`}>{g.count}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="builder-list">
        {active.length === 0 ? (
          <div className="empty" style={{ border: 0, padding: "48px 24px" }}>
            <div className="empty-title">Κανένα stat ενεργό</div>
            <div className="empty-body">
              Πρόσθεσε τουλάχιστον ένα stat από το πεδίο αναζήτησης. Το matching τρέχει μόνο
              πάνω στις διαστάσεις που ορίζεις — τα υπόλοιπα features αγνοούνται εντελώς.
            </div>
          </div>
        ) : (
          active.map((meta) => (
            <StatItem
              key={meta.key}
              meta={meta}
              control={controls[meta.key]}
              fullRows={fullRows}
              onChange={(patch) => onChange(meta.key, patch)}
            />
          ))
        )}
      </div>
    </>
  );
}

function StatItem({
  meta,
  control,
  fullRows,
  onChange,
}: {
  meta: StatMeta;
  control: Control;
  fullRows: number;
  onChange: (patch: Partial<Control>) => void;
}) {
  const pos = normalize(meta, control.value);
  const pct = percentileOf(meta, control.value);
  const dist = meta.dist;
  const sparse = meta.n_rows != null && fullRows > 0 && meta.n_rows < fullRows * 0.9;

  return (
    <div className="stat-item">
      <div className="stat-item-head">
        <span className="stat-item-key">{shortLabel(meta)}</span>
        <span className="stat-item-cat">{meta.group}</span>
        <span className="stat-item-val">{formatWithUnit(meta, control.value)}</span>
        <button
          type="button"
          className="stat-item-x"
          aria-label={`Αφαίρεση ${meta.label}`}
          onClick={() => onChange({ enabled: false })}
        >
          <svg width="8" height="8" viewBox="0 0 10 10" stroke="currentColor" strokeWidth="1.3">
            <path d="M1 1 L9 9 M9 1 L1 9" />
          </svg>
        </button>
      </div>

      {/* Πραγματική κατανομή του league. Τα bins κοντά στην επιλεγμένη τιμή
          φωτίζονται, ώστε να φαίνεται αμέσως αν το target είναι mainstream ή
          ακραίο — δηλαδή αν υπάρχουν καν παίκτες εκεί. */}
      {dist && dist.length > 0 && (
        <div className="stat-dist">
          <div className="stat-dist-bars">
            {dist.map((h, i) => {
              const center = (i + 0.5) / dist.length;
              return (
                <div
                  key={i}
                  className={Math.abs(center - pos) < 0.045 ? "near" : undefined}
                  style={{ height: `${Math.max(4, h * 100)}%` }}
                />
              );
            })}
          </div>
          <div className="stat-dist-marker" style={{ left: `${pos * 100}%` }} />
        </div>
      )}

      <div className="stat-controls">
        <input
          type="range"
          min={meta.min}
          max={meta.max}
          step={meta.step}
          value={control.value}
          aria-label={meta.label}
          onChange={(e) => onChange({ value: parseFloat(e.target.value) })}
        />
        <div className="weight-seg">
          <span className="weight-seg-label">W</span>
          {WEIGHTS.map((w) => (
            <button
              key={w}
              type="button"
              className={`weight-opt${control.weight === w ? " on" : ""}`}
              title={`Βάρος ×${w}`}
              onClick={() => onChange({ weight: w })}
            >
              ×{w}
            </button>
          ))}
        </div>
      </div>

      <div className="stat-foot">
        {pct != null && `league p${pct} · `}
        <span className={sparse ? "warn" : undefined}>
          {meta.n_rows != null
            ? `${compactCount(meta.n_rows)} rows έχουν αυτό το stat`
            : `βήμα ${meta.step.toFixed(decimalsFor(meta))}`}
        </span>
      </div>
    </div>
  );
}
