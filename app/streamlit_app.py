"""
ProspectMatch — NBA Scouting Tool (demo)

Ο χρήστης ορίζει stats + βάρη + traits → top-N πιο όμοιοι παίκτες + explanation.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import streamlit as st
import pandas as pd

from preprocessing import preprocess, FEATURE_COLS
from archetypes import classify
from similarity import find_similar

# ─── Config ───────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="ProspectMatch",
    page_icon="🏀",
    layout="wide",
)

# ─── Load data (cached) ───────────────────────────────────────────────────────

@st.cache_resource(show_spinner="Φόρτωση dataset...")
def load_data():
    df, matrix, scaler = preprocess()
    df = classify(df)
    return df, matrix, scaler


df, matrix, scaler = load_data()

# ─── Helpers ──────────────────────────────────────────────────────────────────

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

# Columns that are stored as decimals (0.0–1.0) but the user thinks in percentages
PCT_COLS = {
    "usg_pct", "ts_pct", "efg_pct", "fg3_pct", "ft_pct",
    "ast_pct", "oreb_pct", "dreb_pct", "pct_pts_2pt_mr",
}

DISPLAY_LABELS = {
    "pts":           "Points (PPG)",
    "usg_pct":       "Usage % (USG%)",
    "ts_pct":        "True Shooting % (TS%)",
    "efg_pct":       "Effective FG% (eFG%)",
    "fg3a":          "3PA per game",
    "fg3_pct":       "3P%",
    "fta":           "FTA per game",
    "ft_pct":        "FT%",
    "pct_pts_2pt_mr":"% Points from Mid-Range",
    "ast_pct":       "Assist % (AST%)",
    "ast_to":        "AST/TO ratio",
    "tov":           "Turnovers (TOV)",
    "oreb_pct":      "Offensive Reb % (OREB%)",
    "dreb_pct":      "Defensive Reb % (DREB%)",
    "stl":           "Steals (STL)",
    "blk":           "Blocks (BLK)",
    "deflections":   "Deflections per game",
    "net_rating":    "Net Rating",
    "height_cm":     "Height (cm)",
    "weight_lbs":    "Weight (lbs)",
}

# Realistic slider ranges (in user-facing units, i.e., percentages × 100)
RANGES = {
    "pts":           (0.0,  45.0, 0.5),
    "usg_pct":       (5.0,  40.0, 0.5),   # shown as %
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

def ui_to_internal(col: str, val: float) -> float:
    """Μετατρέπει UI τιμή (ανθρώπινες μονάδες) → εσωτερική (decimal για pct cols)."""
    return val / 100.0 if col in PCT_COLS else val


# ─── Sidebar — Profile Builder ─────────────────────────────────────────────────

st.sidebar.title("🏀 ProspectMatch")
st.sidebar.markdown("Ορίσε το player profile που ψάχνεις.")

# Season range
st.sidebar.subheader("Εποχή")
year_range = st.sidebar.slider("Season range", 1996, 2025, (2010, 2025), step=1)
season_range_str = f"{year_range[0]}-{year_range[1]}"

# Traits
st.sidebar.subheader("Traits (boost, όχι hard filter)")
selected_traits = st.sidebar.multiselect(
    "Επίλεξε traits που θες να εμφανίζονται:",
    options=ALL_TRAITS,
    default=[],
    format_func=lambda t: t.replace("_", " ").title(),
)

# Number of results
top_n = st.sidebar.slider("Αριθμός αποτελεσμάτων", 5, 20, 10)

# ─── Main — Stats + Weights ────────────────────────────────────────────────────

st.title("ProspectMatch — NBA Player Similarity")
st.caption("Ορίσε τα stats που σε ενδιαφέρουν, δώσε βάρη, και βρες παίκτες που ταιριάζουν.")

col_stats, col_weights = st.columns([3, 1], gap="large")

with col_stats:
    st.subheader("Stats")
    st.markdown("Άναψε μόνο τα stats που θέλεις να αξιολογηθούν. Αν ένα stat είναι off, δεν επηρεάζει το αποτέλεσμα.")

with col_weights:
    st.subheader("Βάρη")
    st.markdown("1 = κανονικό · 3 = πολύ σημαντικό")

# Grouping for cleaner UI
GROUPS = {
    "Scoring & Efficiency": ["pts", "usg_pct", "ts_pct", "efg_pct"],
    "Shooting": ["fg3a", "fg3_pct", "fta", "ft_pct", "pct_pts_2pt_mr"],
    "Playmaking": ["ast_pct", "ast_to", "tov"],
    "Rebounding": ["oreb_pct", "dreb_pct"],
    "Defense": ["stl", "blk", "deflections"],
    "Impact & Physical": ["net_rating", "height_cm", "weight_lbs"],
}

user_stats = {}
weights = {}

for group_name, cols in GROUPS.items():
    st.markdown(f"**{group_name}**")
    for col in cols:
        lo, hi, step = RANGES[col]
        default_val = (lo + hi) / 2
        c1, c2, c3 = st.columns([0.5, 3, 1])
        with c1:
            enabled = st.checkbox("", key=f"en_{col}", value=False)
        with c2:
            val = st.slider(
                DISPLAY_LABELS[col],
                min_value=lo, max_value=hi, value=default_val, step=step,
                key=f"sl_{col}",
                disabled=not enabled,
                label_visibility="collapsed",
            )
            st.caption(DISPLAY_LABELS[col])
        with c3:
            w = st.number_input(
                "w", min_value=0.1, max_value=5.0, value=1.0, step=0.5,
                key=f"w_{col}",
                disabled=not enabled,
                label_visibility="collapsed",
            )
        if enabled:
            user_stats[col] = ui_to_internal(col, val)
            if w != 1.0:
                weights[col] = w
    st.divider()

# ─── Run matching ──────────────────────────────────────────────────────────────

run = st.button("🔍 Βρες παίκτες", type="primary", disabled=len(user_stats) == 0)

if len(user_stats) == 0:
    st.info("Άναψε τουλάχιστον ένα stat για να ξεκινήσει η αναζήτηση.")

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
    else:
        st.subheader(f"Top {len(results)} αποτελέσματα")

        for rank, (_, row) in enumerate(results.iterrows(), 1):
            sim_pct = int(row["similarity"] * 100)
            with st.expander(
                f"#{rank}  **{row['player_name']}**  ({row['season']})  —  "
                f"{row['compound_archetype']}  —  similarity {sim_pct}%",
                expanded=(rank <= 3),
            ):
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**✅ Matching features**")
                    for e in row["explanation"]["matching"][:4]:
                        label = DISPLAY_LABELS.get(e["feature"], e["feature"])
                        st.markdown(f"- **{label}**: user z={e['user_z']:+.2f} · player z={e['player_z']:+.2f}")
                with c2:
                    st.markdown("**⚠️ Diverging features**")
                    for e in row["explanation"]["diverging"][:3]:
                        label = DISPLAY_LABELS.get(e["feature"], e["feature"])
                        st.markdown(f"- **{label}**: user z={e['user_z']:+.2f} · player z={e['player_z']:+.2f}")

                st.caption(
                    f"Position: {row.get('position_group', '—')} · "
                    f"Height: {row.get('height_cm', '—')} cm · "
                    f"Weight: {row.get('weight_lbs', '—')} lbs · "
                    f"Base sim: {row['similarity']:.4f} · Boost: {row['boost']:.4f}"
                )