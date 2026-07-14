import type { StatMeta } from "../types";

// Ένα control ανά feature: enable checkbox + slider + weight input.
export interface Control {
  enabled: boolean;
  value: number; // display units
  weight: number;
}

export type Controls = Record<string, Control>;

interface Props {
  stats: StatMeta[];
  controls: Controls;
  onChange: (key: string, patch: Partial<Control>) => void;
}

function fmt(meta: StatMeta, val: number): string {
  const decimals = meta.step < 1 ? (meta.step < 0.5 ? 2 : 1) : 0;
  return `${val.toFixed(decimals)}${meta.unit}`;
}

export default function StatBuilder({ stats, controls, onChange }: Props) {
  // Group stats διατηρώντας τη σειρά εμφάνισης
  const groups: { name: string; items: StatMeta[] }[] = [];
  for (const s of stats) {
    let g = groups.find((x) => x.name === s.group);
    if (!g) {
      g = { name: s.group, items: [] };
      groups.push(g);
    }
    g.items.push(s);
  }

  return (
    <div>
      {groups.map((group) => (
        <div className="stat-group" key={group.name}>
          <h4>{group.name}</h4>
          {group.items.map((meta) => {
            const c = controls[meta.key];
            if (!c) return null;
            return (
              <div className={`stat-row ${c.enabled ? "" : "disabled"}`} key={meta.key}>
                <input
                  type="checkbox"
                  checked={c.enabled}
                  onChange={(e) => onChange(meta.key, { enabled: e.target.checked })}
                  aria-label={`Enable ${meta.label}`}
                />
                <span className="stat-name">{meta.label}</span>
                <input
                  type="range"
                  min={meta.min}
                  max={meta.max}
                  step={meta.step}
                  value={c.value}
                  disabled={!c.enabled}
                  onChange={(e) => onChange(meta.key, { value: parseFloat(e.target.value) })}
                />
                <span className={`stat-val ${c.enabled ? "" : "dim"}`}>{fmt(meta, c.value)}</span>
                <span>
                  <input
                    className="weight-input"
                    type="number"
                    min={0.1}
                    max={5}
                    step={0.5}
                    value={c.weight}
                    disabled={!c.enabled}
                    title="Βάρος: 1 = κανονικό, 3 = πολύ σημαντικό"
                    onChange={(e) => onChange(meta.key, { weight: parseFloat(e.target.value) || 1 })}
                  />
                  <span className="weight-label"> ×</span>
                </span>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
