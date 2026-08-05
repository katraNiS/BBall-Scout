import type { RadarData } from "../types";

// Radar overlay: target profile (dashed, ουδέτερο) vs matched player (accent, filled).
// Οι τιμές είναι percentiles 0–100 vs όλο το dataset.
//
// Γραμμένο ως raw SVG αντί για charting library: το ίδιο component πρέπει να
// διαβάζεται και στα 84px (μέσα σε γραμμή πίνακα) και στα 252px (expanded), και
// σε αυτά τα μεγέθη το μόνο που μετράει είναι το σχήμα του πολυγώνου — τα ticks,
// τα tooltips και τα legends μιας library είναι θόρυβος που δεν χωράει.

interface Props {
  radar: RadarData;
  size: number;
  /** Ακτίνες + labels ανά άξονα — μόνο στο μεγάλο μέγεθος. */
  detailed?: boolean;
  playerName?: string;
  /**
   * Σύντομα labels ανά άξονα. Τα `radar.axes` είναι τα πλήρη DISPLAY_LABELS
   * ("Usage % (USG%)") που δεν χωράνε γύρω από ένα 252px πολύγωνο — ο caller
   * περνά τις συντομεύσεις γιατί μόνο αυτός έχει το stats metadata.
   */
  labels?: string[];
}

function polygon(values: number[], cx: number, cy: number, r: number): string {
  const n = values.length;
  return values
    .map((v, i) => {
      const angle = -Math.PI / 2 + (i * 2 * Math.PI) / n;
      const k = Math.max(0, Math.min(1, v / 100));
      return `${(cx + Math.cos(angle) * r * k).toFixed(1)},${(cy + Math.sin(angle) * r * k).toFixed(1)}`;
    })
    .join(" ");
}

function ring(n: number, cx: number, cy: number, r: number, frac: number): string {
  return polygon(new Array(n).fill(frac * 100), cx, cy, r);
}

export default function RadarChart({ radar, size, detailed = false, playerName, labels }: Props) {
  const n = radar.axes.length;
  if (n < 3) return null;

  // Στο detailed mode αφήνουμε περιθώριο για τα labels γύρω από το πολύγωνο.
  const box = detailed ? size : size;
  const cx = box / 2;
  const cy = box / 2;
  const r = detailed ? box / 2 - 26 : box / 2 - 8;

  const axisAngles = Array.from({ length: n }, (_, i) => -Math.PI / 2 + (i * 2 * Math.PI) / n);

  return (
    <svg width={box} height={box} viewBox={`0 0 ${box} ${box}`} role="img"
         aria-label={playerName ? `Profile overlay: ${playerName}` : "Profile overlay"}>
      <polygon points={ring(n, cx, cy, r, 1)} fill="none" stroke="rgba(255,255,255,.11)" strokeWidth="1" />
      <polygon points={ring(n, cx, cy, r, 0.66)} fill="none" stroke="rgba(255,255,255,.07)" strokeWidth="1" />
      <polygon points={ring(n, cx, cy, r, 0.33)} fill="none" stroke="rgba(255,255,255,.05)" strokeWidth="1" />

      {detailed && (
        <g stroke="rgba(255,255,255,.06)" strokeWidth="1">
          {axisAngles.map((a, i) => (
            <line key={i} x1={cx} y1={cy} x2={cx + Math.cos(a) * r} y2={cy + Math.sin(a) * r} />
          ))}
        </g>
      )}

      <polygon
        points={polygon(radar.user, cx, cy, r)}
        fill="rgba(232,234,236,.10)"
        stroke="rgba(232,234,236,.6)"
        strokeWidth={detailed ? 1.3 : 1.2}
        strokeDasharray={detailed ? "4 3" : "3 2"}
      />
      <polygon
        points={polygon(radar.player, cx, cy, r)}
        fill="rgba(148,188,227,.20)"
        stroke="#94bce3"
        strokeWidth={detailed ? 1.6 : 1.4}
      />

      {detailed &&
        axisAngles.map((a, i) => {
          const x = cx + Math.cos(a) * (r + 15);
          const y = cy + Math.sin(a) * (r + 15) + 3;
          const anchor = Math.abs(Math.cos(a)) < 0.2 ? "middle" : Math.cos(a) > 0 ? "start" : "end";
          return (
            <text
              key={i}
              x={x.toFixed(0)}
              y={y.toFixed(0)}
              fill="#7d848c"
              fontFamily="ui-monospace, Consolas, Menlo, monospace"
              fontSize="9"
              textAnchor={anchor}
            >
              {labels?.[i] ?? radar.axes[i]}
            </text>
          );
        })}
    </svg>
  );
}
