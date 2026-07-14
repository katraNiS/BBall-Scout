"""
UI / API metadata για τα 20 features.

Single source of truth για labels, ranges, format και grouping — mirror των
constants που ζούσαν στο `app/streamlit_app.py`. Το `/stats` endpoint σερβίρει
αυτά ώστε το React frontend να χτίσει το stat builder δυναμικά (χωρίς hardcoded
λίστες στον client).

ΚΡΙΣΙΜΟ — data format (βλ. CLAUDE.md):
Τα PCT_COLS αποθηκεύονται internally ως fractions (0.0–1.0). Τα RANGES εδώ είναι
σε **display units** (π.χ. ts_pct 35–80 σημαίνει 35%–80%). Ο client στέλνει
display values· ο μετατροπέας display→internal γίνεται server-side στο engine,
ώστε η λογική ×100/÷100 να ζει σε ένα μόνο σημείο.
"""

from __future__ import annotations

# 18 primitive traits — για trait-boost multiselect στο UI
ALL_TRAITS: list[str] = [
    "on_ball_creator", "slasher", "midrange_scorer",
    "spot_up_shooter", "movement_shooter",
    "lead_playmaker", "connective_passer", "playmaking_big",
    "post_scorer", "roll_finisher", "stretch_big",
    "point_of_attack_defender", "versatile_wing_defender",
    "rim_protector", "help_defender",
    "defensive_rebounder", "offensive_rebounder",
    "efficient_finisher",
]

# Features που αποθηκεύονται ως fractions (0–1) internally αλλά εμφανίζονται ×100
PCT_COLS: set[str] = {
    "usg_pct", "ts_pct", "efg_pct", "fg3_pct", "ft_pct",
    "ast_pct", "oreb_pct", "dreb_pct", "pct_pts_2pt_mr",
}

DISPLAY_LABELS: dict[str, str] = {
    "pts":            "Points (PPG)",
    "usg_pct":        "Usage % (USG%)",
    "ts_pct":         "True Shooting %",
    "efg_pct":        "Effective FG%",
    "fg3a":           "3-Pointers Attempted",
    "fg3_pct":        "3-Point %",
    "fta":            "Free Throw Attempts",
    "ft_pct":         "Free Throw %",
    "pct_pts_2pt_mr": "% Points from Mid-Range",
    "ast_pct":        "Assist %",
    "ast_to":         "AST/TO Ratio",
    "tov":            "Turnovers",
    "oreb_pct":       "Off. Rebound %",
    "dreb_pct":       "Def. Rebound %",
    "stl":            "Steals",
    "blk":            "Blocks",
    "deflections":    "Deflections",
    "net_rating":     "Net Rating",
    "height_cm":      "Height (cm)",
    "weight_lbs":     "Weight (lbs)",
}

# (python format template, unit suffix) — εφαρμόζεται στο display value
FORMAT: dict[str, tuple[str, str]] = {
    "pts":            ("{:.1f}", "PPG"),
    "usg_pct":        ("{:.1f}", "%"),
    "ts_pct":         ("{:.1f}", "%"),
    "efg_pct":        ("{:.1f}", "%"),
    "fg3a":           ("{:.1f}", "/gm"),
    "fg3_pct":        ("{:.1f}", "%"),
    "fta":            ("{:.1f}", "/gm"),
    "ft_pct":         ("{:.1f}", "%"),
    "pct_pts_2pt_mr": ("{:.1f}", "%"),
    "ast_pct":        ("{:.1f}", "%"),
    "ast_to":         ("{:.2f}", ""),
    "tov":            ("{:.1f}", "/gm"),
    "oreb_pct":       ("{:.1f}", "%"),
    "dreb_pct":       ("{:.1f}", "%"),
    "stl":            ("{:.2f}", "/gm"),
    "blk":            ("{:.2f}", "/gm"),
    "deflections":    ("{:.2f}", "/gm"),
    "net_rating":     ("{:+.1f}", ""),
    "height_cm":      ("{:.0f}", " cm"),
    "weight_lbs":     ("{:.0f}", " lbs"),
}

# (min, max, step) σε display units
RANGES: dict[str, tuple[float, float, float]] = {
    "pts":            (0.0,   45.0,  0.5),
    "usg_pct":        (5.0,   40.0,  0.5),
    "ts_pct":         (35.0,  80.0,  0.5),
    "efg_pct":        (30.0,  75.0,  0.5),
    "fg3a":           (0.0,   16.0,  0.5),
    "fg3_pct":        (0.0,   50.0,  0.5),
    "fta":            (0.0,   12.0,  0.5),
    "ft_pct":         (40.0,  100.0, 1.0),
    "pct_pts_2pt_mr": (0.0,   40.0,  0.5),
    "ast_pct":        (0.0,   55.0,  0.5),
    "ast_to":         (0.0,   8.0,   0.1),
    "tov":            (0.0,   6.0,   0.1),
    "oreb_pct":       (0.0,   20.0,  0.5),
    "dreb_pct":       (0.0,   35.0,  0.5),
    "stl":            (0.0,   3.5,   0.1),
    "blk":            (0.0,   4.0,   0.1),
    "deflections":    (0.0,   6.0,   0.1),
    "net_rating":     (-20.0, 20.0,  0.5),
    "height_cm":      (170.0, 225.0, 1.0),
    "weight_lbs":     (150.0, 290.0, 5.0),
}

# Grouping για το stat builder (σειρά εμφάνισης)
GROUPS: dict[str, list[str]] = {
    "Scoring & Efficiency": ["pts", "usg_pct", "ts_pct", "efg_pct"],
    "Shooting":             ["fg3a", "fg3_pct", "fta", "ft_pct", "pct_pts_2pt_mr"],
    "Playmaking":           ["ast_pct", "ast_to", "tov"],
    "Rebounding":           ["oreb_pct", "dreb_pct"],
    "Defense":              ["stl", "blk", "deflections"],
    "Impact & Physical":    ["net_rating", "height_cm", "weight_lbs"],
}


def to_internal(col: str, display_val: float) -> float:
    """Display value → internal. PCT_COLS διαιρούνται με 100 (Streamlit ui_to_internal)."""
    return display_val / 100.0 if col in PCT_COLS else display_val


def to_display(col: str, internal_val: float) -> float:
    """Internal value → display. PCT_COLS πολλαπλασιάζονται ×100."""
    return internal_val * 100.0 if col in PCT_COLS else internal_val


def format_display(col: str, display_val: float) -> str:
    """Format display value με template + unit (Streamlit fmt)."""
    tmpl, unit = FORMAT.get(col, ("{:.2f}", ""))
    return tmpl.format(display_val) + unit


def stats_metadata() -> list[dict]:
    """
    Επιστρέφει flat λίστα με metadata ανά feature, σε σειρά GROUPS.
    Ο client χτίζει το stat builder από αυτό.
    """
    out: list[dict] = []
    for group_name, cols in GROUPS.items():
        for col in cols:
            lo, hi, step = RANGES[col]
            tmpl, unit = FORMAT[col]
            default = round((lo + hi) / 2 / step) * step
            out.append({
                "key":     col,
                "label":   DISPLAY_LABELS[col],
                "group":   group_name,
                "min":     lo,
                "max":     hi,
                "step":    step,
                "default": default,
                "is_pct":  col in PCT_COLS,
                "unit":    unit,
                "format":  tmpl,
            })
    return out
