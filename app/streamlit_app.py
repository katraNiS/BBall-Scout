"""
ProspectMatch — NBA Scouting Tool (v0.2)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from preprocessing import preprocess, FEATURE_COLS, build_percentile_matrix, stat_to_percentile
from archetypes import classify
from similarity import find_similar

# ─── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="ProspectMatch",
    page_icon="🏀",
    layout="wide",
)

st.markdown("""
<style>
    .stat-row { display:flex; justify-content:space-between; padding:2px 0; }
    .stat-label { color:#888; font-size:0.85rem; }
    .stat-match { color:#22c55e; font-weight:600; }
    .stat-close  { color:#f59e0b; font-weight:600; }
    .stat-far   { color:#ef4444; font-weight:600; }
    .badge {
        display:inline-block; padding:2px 8px; border-radius:4px;
        font-size:0.75rem; font-weight:600; margin-right:4px;
    }
    .badge-pos  { background:#1e3a5f; color:#93c5fd; }
    .badge-arch { background:#1a2e1a; color:#86efac; }
    .rank-num { font-size:1.5rem; font-weight:800; color:#6b7280; margin-right:8px; }
    div[data-testid="stExpander"] > div:first-child { padding: 4px 0; }
</style>
""", unsafe_allow_html=True)

# ─── Load data ─────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner="Φόρτωση dataset...")
def load_data():
    df, matrix, scaler = preprocess()
    df = classify(df)
    pct_df = build_percentile_matrix(df)
    df = pd.concat([df, pct_df], axis=1)
    return df, matrix, scaler

df, matrix, scaler = load_data()

# ─── Constants ────────────────────────────────────────────────────────────────

ALL_TRAITS = [
    "on_ball_creator", "slasher", "midrange_scorer",
    "spot_up_shooter", "movement_shooter",
    "lead_playmaker", "connective_passer", "playmaking_big",
    "post_scorer", "roll_finisher", "stretch_big",
    "point_of_attack_defender", "versatile_wing_defender",
    "rim_protector", "help_defender",
    "defensive_rebounder", "offensive_rebounder",
    "efficient_finisher",
]

PCT_COLS = {
    "usg_pct", "ts_pct", "efg_pct", "fg3_pct", "ft_pct",
    "ast_pct", "oreb_pct", "dreb_pct", "pct_pts_2pt_mr",
}

DISPLAY_LABELS = {
    "pts":           "Points (PPG)",
    "usg_pct":       "Usage % (USG%)",
    "ts_pct":        "True Shooting %",
    "efg_pct":       "Effective FG%",
    "fg3a":          "3-Pointers Attempted",
    "fg3_pct":       "3-Point %",
    "fta":           "Free Throw Attempts",
    "ft_pct":        "Free Throw %",
    "pct_pts_2pt_mr":"% Points from Mid-Range",
    "ast_pct":       "Assist %",
    "ast_to":        "AST/TO Ratio",
    "tov":           "Turnovers",
    "oreb_pct":      "Off. Rebound %",
    "dreb_pct":      "Def. Rebound %",
    "stl":           "Steals",
    "blk":           "Blocks",
    "deflections":   "Deflections",
    "net_rating":    "Net Rating",
    "height_cm":     "Height (cm)",
    "weight_lbs":    "Weight (lbs)",
}

# Format for display (after converting decimal → human units)
FORMAT = {
    "pts":           ("{:.1f}", "PPG"),
    "usg_pct":       ("{:.1f}", "%"),
    "ts_pct":        ("{:.1f}", "%"),
    "efg_pct":       ("{:.1f}", "%"),
    "fg3a":          ("{:.1f}", "/gm"),
    "fg3_pct":       ("{:.1f}", "%"),
    "fta":           ("{:.1f}", "/gm"),
    "ft_pct":        ("{:.1f}", "%"),
    "pct_pts_2pt_mr":("{:.1f}", "%"),
    "ast_pct":       ("{:.1f}", "%"),
    "ast_to":        ("{:.2f}", ""),
    "tov":           ("{:.1f}", "/gm"),
    "oreb_pct":      ("{:.1f}", "%"),
    "dreb_pct":      ("{:.1f}", "%"),
    "stl":           ("{:.2f}", "/gm"),
    "blk":           ("{:.2f}", "/gm"),
    "deflections":   ("{:.2f}", "/gm"),
    "net_rating":    ("{:+.1f}", ""),
    "height_cm":     ("{:.0f}", " cm"),
    "weight_lbs":    ("{:.0f}", " lbs"),
}

RANGES = {
    "pts":           (0.0,  45.0, 0.5),
    "usg_pct":       (5.0,  40.0, 0.5),
    "ts_pct":        (35.0, 80.0, 0.5),
    "efg_pct":       (30.0, 75.0, 0.5),
    "fg3a":          (0.0,  16.0, 0.5),
    "fg3_pct":       (0.0,  50.0, 0.5),
    "fta":           (0.0,  12.0, 0.5),
    "ft_pct":        (40.0, 100.0, 1.0),
    "pct_pts_2pt_mr":(0.0,  40.0, 0.5),
    "ast_pct":       (0.0,  55.0, 0.5),
    "ast_to":        (0.0,  8.0,  0.1),
    "tov":           (0.0,  6.0,  0.1),
    "oreb_pct":      (0.0,  20.0, 0.5),
    "dreb_pct":      (0.0,  35.0, 0.5),
    "stl":           (0.0,  3.5,  0.1),
    "blk":           (0.0,  4.0,  0.1),
    "deflections":   (0.0,  6.0,  0.1),
    "net_rating":    (-20.0, 20.0, 0.5),
    "height_cm":     (170.0, 225.0, 1.0),
    "weight_lbs":    (150.0, 290.0, 5.0),
}

GROUPS = {
    "Scoring & Efficiency": ["pts", "usg_pct", "ts_pct", "efg_pct"],
    "Shooting":             ["fg3a", "fg3_pct", "fta", "ft_pct", "pct_pts_2pt_mr"],
    "Playmaking":           ["ast_pct", "ast_to", "tov"],
    "Rebounding":           ["oreb_pct", "dreb_pct"],
    "Defense":              ["stl", "blk", "deflections"],
    "Impact & Physical":    ["net_rating", "height_cm", "weight_lbs"],
}

# ─── Helpers ──────────────────────────────────────────────────────────────────

def ui_to_internal(col, val):
    return val / 100.0 if col in PCT_COLS else val


def make_radar_chart(
    user_stats: dict,
    player_row: pd.Series,
    player_name: str,
) -> go.Figure:
    """
    Radar chart: user target (πορτοκαλί, dashed) vs matched player (μπλε, filled).
    Άξονες = τα stats που ο χρήστης όρισε, max 8 για readability.
    Τιμές σε percentile (0–100) vs όλο το dataset.
    """
    cols = list(user_stats.keys())[:8]
    labels = [DISPLAY_LABELS.get(c, c) for c in cols]

    # Percentile του user target vs dataset
    user_pct = [stat_to_percentile(c, user_stats[c], df) for c in cols]

    # Percentile του matched player (precomputed)
    player_pct = [float(player_row.get(f"pct_{c}", 50.0)) for c in cols]

    # Κλείνουμε το polygon επαναλαμβάνοντας το πρώτο σημείο
    u_r = user_pct + [user_pct[0]]
    p_r = player_pct + [player_pct[0]]
    theta = labels + [labels[0]]

    fig = go.Figure()

    fig.add_trace(go.Scatterpolar(
        r=p_r, theta=theta,
        fill="toself",
        fillcolor="rgba(59,130,246,0.20)",
        line=dict(color="#3b82f6", width=2.5),
        name=player_name,
        hovertemplate="%{theta}: %{r:.0f}th pct<extra></extra>",
    ))
    fig.add_trace(go.Scatterpolar(
        r=u_r, theta=theta,
        fill="toself",
        fillcolor="rgba(249,115,22,0.15)",
        line=dict(color="#f97316", width=2, dash="dash"),
        name="Your target",
        hovertemplate="%{theta}: %{r:.0f}th pct<extra></extra>",
    ))

    fig.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(
                visible=True, range=[0, 100],
                tickvals=[25, 50, 75, 100],
                tickfont=dict(size=9, color="#6b7280"),
                gridcolor="#374151",
                linecolor="#374151",
            ),
            angularaxis=dict(
                tickfont=dict(size=10, color="#d1d5db"),
                gridcolor="#374151",
                linecolor="#374151",
            ),
        ),
        showlegend=True,
        legend=dict(
            orientation="h", yanchor="bottom", y=-0.18,
            xanchor="center", x=0.5,
            font=dict(size=11, color="#d1d5db"),
        ),
        margin=dict(l=55, r=55, t=30, b=55),
        height=360,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e5e7eb"),
    )
    return fig

def internal_to_display(col, val):
    """Decimal internal value → human-readable (multiply pct cols by 100)."""
    return val * 100.0 if col in PCT_COLS else val

def z_to_display(col: str, z: float) -> float:
    """Z-score → raw value → display value."""
    i = FEATURE_COLS.index(col)
    raw = float(z) * scaler.scale_[i] + scaler.mean_[i]
    return internal_to_display(col, raw)

def fmt(col: str, val: float) -> str:
    tmpl, unit = FORMAT[col]
    return tmpl.format(val) + unit


# ─── Sidebar ──────────────────────────────────────────────────────────────────

st.sidebar.title("🏀 ProspectMatch")
st.sidebar.caption("NBA Player Similarity Engine")
st.sidebar.divider()

st.sidebar.subheader("Season Range")
year_range = st.sidebar.slider("", 1996, 2025, (2010, 2025), step=1,
                                label_visibility="collapsed")
season_range_str = f"{year_range[0]}-{year_range[1]}"

st.sidebar.subheader("Trait Boost")
st.sidebar.caption("Μικρό bonus για παίκτες με αυτά τα traits — δεν αποκλείει κανέναν.")
selected_traits = st.sidebar.multiselect(
    "",
    options=ALL_TRAITS,
    default=[],
    format_func=lambda t: t.replace("_", " ").title(),
    label_visibility="collapsed",
)

st.sidebar.divider()
top_n = st.sidebar.slider("Αριθμός αποτελεσμάτων", 5, 20, 10)

# ─── Header ───────────────────────────────────────────────────────────────────

st.title("ProspectMatch")
st.markdown("Ορίσε το player profile που ψάχνεις — stats + βάρη — και βρες τους πιο όμοιους παίκτες της NBA.")
st.divider()

# ─── Stat builder ─────────────────────────────────────────────────────────────

user_stats: dict = {}
weights: dict = {}

for group_name, cols in GROUPS.items():
    st.markdown(f"#### {group_name}")
    for col in cols:
        lo, hi, step = RANGES[col]
        default_val = round((lo + hi) / 2 / step) * step

        c_en, c_label, c_slider, c_weight = st.columns([0.25, 1.4, 3, 0.7])

        with c_en:
            st.write("")  # vertical align
            enabled = st.checkbox("", key=f"en_{col}", value=False, label_visibility="collapsed")

        with c_label:
            st.write("")
            color = "#e5e7eb" if enabled else "#6b7280"
            st.markdown(
                f'<span style="color:{color};font-size:0.85rem;">{DISPLAY_LABELS[col]}</span>',
                unsafe_allow_html=True,
            )

        with c_slider:
            val = st.slider(
                DISPLAY_LABELS[col],
                min_value=lo, max_value=hi, value=default_val, step=step,
                key=f"sl_{col}",
                disabled=not enabled,
                label_visibility="collapsed",
            )

        with c_weight:
            w = st.number_input(
                "×", min_value=0.1, max_value=5.0, value=1.0, step=0.5,
                key=f"w_{col}",
                disabled=not enabled,
                help="Βάρος: 1 = κανονικό, 3 = πολύ σημαντικό",
            )

        if enabled:
            user_stats[col] = ui_to_internal(col, val)
            if w != 1.0:
                weights[col] = w

    st.markdown("")

st.divider()

# ─── Active profile summary ────────────────────────────────────────────────────

if user_stats:
    pills = " &nbsp;·&nbsp; ".join(
        f'<b>{DISPLAY_LABELS[c]}</b>: {fmt(c, internal_to_display(c, v))}'
        + (f' <span style="color:#f59e0b">×{weights[c]:.0f}</span>' if c in weights else "")
        for c, v in user_stats.items()
    )
    st.markdown(f'<div style="font-size:0.82rem;color:#9ca3af;padding:4px 0 12px 0">{pills}</div>',
                unsafe_allow_html=True)

run = st.button(
    "🔍 Βρες παίκτες" if user_stats else "Άναψε τουλάχιστον ένα stat",
    type="primary",
    disabled=not user_stats,
    use_container_width=True,
)

# ─── Results ──────────────────────────────────────────────────────────────────

if run and user_stats:
    with st.spinner("Αναζήτηση..."):
        results = find_similar(
            user_stats=user_stats,
            df_clean=df,
            feature_matrix=matrix,
            scaler=scaler,
            weights=weights if weights else None,
            top_n=top_n,
            active_traits=selected_traits if selected_traits else None,
            season_range=season_range_str,
        )

    if results.empty:
        st.warning("Δεν βρέθηκαν αποτελέσματα. Δοκίμασε να διευρύνεις το season range.")
        st.stop()

    st.subheader(f"Top {len(results)} matches")

    for rank, (_, row) in enumerate(results.iterrows(), 1):
        sim_pct   = row["similarity"]
        pos       = row.get("position_group", "—")
        arch      = row["compound_archetype"]
        exp       = row["explanation"]

        # Colour the rank medal
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"#{rank}")

        header = (
            f"{medal} &nbsp;<b style='font-size:1.1rem'>{row['player_name']}</b>"
            f"&nbsp;&nbsp;<span style='color:#9ca3af'>{row['season']}</span>"
            f"&nbsp;&nbsp;"
            f"<span class='badge badge-pos'>{pos}</span>"
            f"<span class='badge badge-arch'>{arch}</span>"
        )

        with st.expander(
            f"{'★ ' if rank <= 3 else ''}{row['player_name']} ({row['season']}) — {arch} — {sim_pct:.0%}",
            expanded=(rank <= 3),
        ):
            st.markdown(f'<div style="margin-bottom:8px">{header}</div>', unsafe_allow_html=True)

            # Similarity progress bar
            bar_col, pct_col = st.columns([5, 1])
            with bar_col:
                st.progress(min(sim_pct, 1.0))
            with pct_col:
                st.markdown(
                    f'<div style="text-align:right;font-weight:700;font-size:1.1rem;'
                    f'color:{"#22c55e" if sim_pct>=0.55 else "#f59e0b" if sim_pct>=0.35 else "#ef4444"}">'
                    f'{sim_pct:.0%}</div>',
                    unsafe_allow_html=True,
                )

            st.markdown("")

            matching  = exp.get("matching", [])[:4]
            diverging = exp.get("diverging", [])[:3]

            # Layout: radar αριστερά αν ≥3 stats, stat tables δεξιά (ή full-width αν <3)
            show_radar = len(user_stats) >= 3
            left_col, right_col = st.columns([1, 1], gap="large") if show_radar else (st.container(), None)

            with left_col:
                if show_radar:
                    fig = make_radar_chart(user_stats, row, row["player_name"])
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            right_ctx = right_col if show_radar else left_col
            with right_ctx:
                if matching:
                    st.markdown("**You asked → Player had**")
                    table_html = "<table style='width:100%;font-size:0.85rem;border-collapse:collapse'>"
                    for e in matching:
                        col_name = e["feature"]
                        label    = DISPLAY_LABELS.get(col_name, col_name)
                        user_val = fmt(col_name, z_to_display(col_name, e["user_z"]))
                        plyr_val = fmt(col_name, z_to_display(col_name, e["player_z"]))
                        u_pct    = stat_to_percentile(col_name, user_stats.get(col_name, scaler.mean_[FEATURE_COLS.index(col_name)]), df)
                        p_pct    = float(row.get(f"pct_{col_name}", 50.0))
                        diff_abs = abs(e["user_z"] - e["player_z"])
                        css      = "stat-match" if diff_abs < 0.4 else "stat-close" if diff_abs < 1.0 else "stat-far"
                        table_html += (
                            f"<tr>"
                            f"<td style='color:#9ca3af;padding:3px 8px 3px 0;font-size:0.8rem'>{label}</td>"
                            f"<td style='padding:3px 4px;font-size:0.82rem'>{user_val} <span style='color:#6b7280;font-size:0.72rem'>({u_pct:.0f}th)</span></td>"
                            f"<td style='color:#6b7280;padding:3px 4px'>→</td>"
                            f"<td class='{css}' style='padding:3px 0;font-size:0.82rem'>{plyr_val} <span style='color:#6b7280;font-size:0.72rem'>({p_pct:.0f}th)</span></td>"
                            f"</tr>"
                        )
                    table_html += "</table>"
                    st.markdown(table_html, unsafe_allow_html=True)

                if diverging:
                    st.markdown("<div style='margin-top:12px'><b>Biggest differences</b></div>", unsafe_allow_html=True)
                    div_html = "<table style='width:100%;font-size:0.85rem;border-collapse:collapse'>"
                    for e in diverging:
                        col_name = e["feature"]
                        label    = DISPLAY_LABELS.get(col_name, col_name)
                        user_val = fmt(col_name, z_to_display(col_name, e["user_z"]))
                        plyr_val = fmt(col_name, z_to_display(col_name, e["player_z"]))
                        diff_abs = abs(e["user_z"] - e["player_z"])
                        css      = "stat-close" if diff_abs < 1.5 else "stat-far"
                        div_html += (
                            f"<tr>"
                            f"<td style='color:#9ca3af;padding:3px 8px 3px 0;font-size:0.8rem'>{label}</td>"
                            f"<td style='padding:3px 4px;font-size:0.82rem'>{user_val}</td>"
                            f"<td style='color:#6b7280;padding:3px 4px'>→</td>"
                            f"<td class='{css}' style='padding:3px 0;font-size:0.82rem'>{plyr_val}</td>"
                            f"</tr>"
                        )
                    div_html += "</table>"
                    st.markdown(div_html, unsafe_allow_html=True)

            # Footer
            h   = row.get("height_cm", "—")
            w_p = row.get("weight_lbs", "—")
            h_str = f"{h:.0f} cm" if isinstance(h, (int, float)) and not np.isnan(h) else "—"
            w_str = f"{w_p:.0f} lbs" if isinstance(w_p, (int, float)) and not np.isnan(w_p) else "—"
            boost_str = f"+{row['boost']:.4f}" if row["boost"] > 0 else "—"

            st.markdown(
                f'<div style="margin-top:10px;font-size:0.75rem;color:#6b7280">'
                f'{h_str} &nbsp;·&nbsp; {w_str} &nbsp;·&nbsp; '
                f'Base sim: {row["similarity"]:.4f} &nbsp;·&nbsp; Trait boost: {boost_str}'
                f'</div>',
                unsafe_allow_html=True,
            )