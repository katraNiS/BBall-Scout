import type { MatchResult, ExplainEntry } from "../types";
import RadarChart from "./RadarChart";

const MEDALS: Record<number, string> = { 1: "🥇", 2: "🥈", 3: "🥉" };

function simColor(sim: number): string {
  return sim >= 0.55 ? "var(--green)" : sim >= 0.35 ? "var(--amber)" : "var(--red)";
}

function StatTable({ entries, title, klass }: { entries: ExplainEntry[]; title: string; klass?: string }) {
  if (!entries.length) return null;
  return (
    <>
      <div className={`table-title ${klass ?? ""}`}>{title}</div>
      <table className="stat-table">
        <tbody>
          {entries.map((e) => (
            <tr key={e.feature}>
              <td className="lbl">{e.label}</td>
              <td>
                {e.user_display} <span className="pct">({e.user_pct}th)</span>
              </td>
              <td className="arrow">→</td>
              <td className={`q-${e.quality}`}>
                {e.player_display} <span className="pct">({e.player_pct}th)</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

export default function ResultCard({ r, showRadar }: { r: MatchResult; showRadar: boolean }) {
  const simPct = Math.round(r.similarity * 100);
  const medal = MEDALS[r.rank] ?? `#${r.rank}`;

  return (
    <div className="card">
      <div className="card-top">
        <span className="rank">{medal}</span>
        <span className="card-name">{r.player_name}</span>
        <span className="card-season">{r.season}</span>
        <span className="badge badge-pos">{r.position_group}</span>
        <span className="badge badge-arch">{r.compound_archetype}</span>
      </div>

      <div className="sim-wrap">
        <div className="sim-bar">
          <div style={{ width: `${Math.min(simPct, 100)}%` }} />
        </div>
        <span className="sim-pct" style={{ color: simColor(r.similarity) }}>
          {simPct}%
        </span>
      </div>

      <div className={`card-body ${showRadar ? "" : "no-radar"}`}>
        {showRadar && (
          <div>
            <RadarChart radar={r.radar} playerName={r.player_name} />
          </div>
        )}
        <div>
          <StatTable entries={r.matching} title="You asked → Player had" />
          <StatTable entries={r.diverging} title="Biggest differences" klass="divs" />
        </div>
      </div>

      <div className="card-foot">
        {r.height_cm ? `${r.height_cm.toFixed(0)} cm` : "—"} &nbsp;·&nbsp;{" "}
        {r.weight_lbs ? `${r.weight_lbs.toFixed(0)} lbs` : "—"} &nbsp;·&nbsp; Base sim:{" "}
        {r.similarity.toFixed(4)} &nbsp;·&nbsp; Trait boost:{" "}
        {r.boost > 0 ? `+${r.boost.toFixed(4)}` : "—"}
      </div>
    </div>
  );
}
