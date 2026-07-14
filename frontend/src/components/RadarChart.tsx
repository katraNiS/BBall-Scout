import {
  Radar,
  RadarChart as RRadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from "recharts";
import type { RadarData } from "../types";

// Radar: user target (πορτοκαλί, dashed) vs matched player (μπλε, filled).
// Τιμές σε percentile (0–100) vs όλο το dataset — ίδια σημασιολογία με το Streamlit.
export default function RadarChart({ radar, playerName }: { radar: RadarData; playerName: string }) {
  const data = radar.axes.map((axis, i) => ({
    axis,
    player: radar.player[i],
    user: radar.user[i],
  }));

  return (
    <ResponsiveContainer width="100%" height={280}>
      <RRadarChart data={data} outerRadius="72%">
        <PolarGrid stroke="#374151" />
        <PolarAngleAxis dataKey="axis" tick={{ fill: "#d1d5db", fontSize: 10 }} />
        <PolarRadiusAxis
          domain={[0, 100]}
          tickCount={5}
          tick={{ fill: "#6b7280", fontSize: 9 }}
          axisLine={false}
        />
        <Radar
          name={playerName}
          dataKey="player"
          stroke="#3b82f6"
          strokeWidth={2.5}
          fill="#3b82f6"
          fillOpacity={0.2}
        />
        <Radar
          name="Your target"
          dataKey="user"
          stroke="#f97316"
          strokeWidth={2}
          strokeDasharray="5 4"
          fill="#f97316"
          fillOpacity={0.12}
        />
        <Legend wrapperStyle={{ fontSize: 11, color: "#d1d5db" }} />
        <Tooltip
          contentStyle={{ background: "#161b22", border: "1px solid #2a3140", borderRadius: 6, fontSize: 12 }}
          formatter={(v: number) => [`${Math.round(v)}th pct`, ""]}
        />
      </RRadarChart>
    </ResponsiveContainer>
  );
}
