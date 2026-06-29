"""
Φόρτωμα, καθαρισμός και normalization του dataset για το matching engine.

Output της preprocess():
  df_clean     — φιλτραρισμένο DataFrame με metadata + raw stats
  feature_matrix — numpy array (n_rows × 20), StandardScaler normalized
  scaler       — fitted scaler για να transform-αρουμε το user input
"""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

DATA_DIR = Path(__file__).parent.parent / "data"
DATASET_PATH = DATA_DIR / "nba_stats_full.csv"

# Minimum playing time — αποφεύγουμε noise από garbage-time / injured seasons
MIN_GP  = 20
MIN_MPG = 10.0   # για 2013-14+ · παλαιότερες σεζόν: 20 MPG (βλ. get_min_mpg)


def get_min_mpg(season: str) -> float:
    """
    Tiered MPG threshold ανά εποχή.

    1996–2013 (pre-tracking era): ≥20 MPG — κρατάμε μόνο meaningful contributors.
      Λόγος: λείπουν hustle/tracking stats → role players με 5 λεπτά δεν
      προσφέρουν ουσιαστικό signal και μολύνουν το similarity space.

    2013+ (tracking era): ≥10 MPG — full data, μπορούμε να κρατήσουμε
      specialists (π.χ. Vanderbilt, Nance Jr.) που παίζουν 15-18 λεπτά.
    """
    year = int(season[:4])
    return 20.0 if year < 2013 else MIN_MPG


# Feature vector για cosine similarity.
# Δεν περιλαμβάνει position (categorical) — χρησιμοποιείται μόνο για archetype filter.
# Δεν περιλαμβάνει raw reb (= oreb+dreb, redundant), pace/tm_tov_pct (team stats),
# plus_minus (net_rating είναι το pace-adjusted equivalent).
FEATURE_COLS = [
    # Scoring & efficiency
    "pts", "usg_pct", "ts_pct", "efg_pct",
    # Shooting profile (volume + accuracy + zone distribution)
    "fg3a", "fg3_pct", "fta", "ft_pct",
    "pct_pts_2pt_mr",     # % πόντων από mid-range (API: PCT_PTS_2PT_MR) — κρίσιμο για midrange_scorer
    # Playmaking
    "ast_pct", "ast_to", "tov",
    # Rebounding (percentage-adjusted για να μην ευνοεί high-minute players)
    "oreb_pct", "dreb_pct",
    # Defense — stl/blk + deflections (tracking, 2015-16+; pre-era: group median)
    "stl", "blk", "deflections",
    # Overall impact (team-dependent αλλά adds signal)
    "net_rating",
    # Physical
    "height_cm", "weight_lbs",
]


def load_and_clean(path: Path = DATASET_PATH) -> pd.DataFrame:
    df = pd.read_csv(path)

    # Tiered MPG filter: 1996–2012 → ≥20 MPG, 2013+ → ≥10 MPG
    min_mpg_per_row = df["season"].apply(get_min_mpg)
    df = df[(df["gp"] >= MIN_GP) & (df["min"] >= min_mpg_per_row)].copy()

    # Numeric coercion — weight_lbs αποθηκεύεται ως string στο CSV
    df["weight_lbs"] = pd.to_numeric(df["weight_lbs"], errors="coerce")
    df["height_cm"] = pd.to_numeric(df["height_cm"], errors="coerce")

    # fg3_pct / ft_pct είναι NaN όταν ο παίκτης δεν έχει απόπειρες.
    # Γεμίζουμε με 0.0 — σωστό semantically (δεν σουτάρει 3, δεν πάει FT).
    df["fg3_pct"] = df.apply(
        lambda r: 0.0 if pd.isna(r["fg3_pct"]) and r["fg3a"] < 0.1 else r["fg3_pct"],
        axis=1,
    )
    df["ft_pct"] = df.apply(
        lambda r: 0.0 if pd.isna(r["ft_pct"]) and r["fta"] < 0.1 else r["ft_pct"],
        axis=1,
    )
    # ast_to είναι NaN όταν ast=0 (division by zero στο API)
    df["ast_to"] = df["ast_to"].fillna(0.0)

    # Remaining pct nulls → column median
    for col in ("fg3_pct", "ft_pct"):
        df[col] = df[col].fillna(df[col].median())

    # height/weight nulls → median της ίδιας position_group
    for col in ("height_cm", "weight_lbs"):
        group_medians = df.groupby("position_group")[col].transform("median")
        df[col] = df[col].fillna(group_medians).fillna(df[col].median())

    # Hustle stats (deflections, charges_drawn, box_outs, screen_assists):
    # NaN για seasons πριν το 2015-16 — γεμίζουμε με position_group median.
    # Αποτέλεσμα: z-score ≈ 0 για παλιές σεζόν (neutral, όχι τιμωρία).
    hustle_like = [c for c in ("deflections", "charges_drawn", "box_outs", "screen_assists") if c in df.columns]
    for col in hustle_like:
        group_medians = df.groupby("position_group")[col].transform("median")
        df[col] = df[col].fillna(group_medians).fillna(df[col].median())

    # Scoring profile (pct_pts_midrange κ.λπ.):
    # Σε περίπτωση που κάποια σεζόν δεν έχει Scoring data → group median.
    scoring_like = [c for c in ("pct_pts_2pt_mr", "pct_pts_paint", "pct_fga_3pt", "pct_pts_3pt", "pct_pts_ft", "pct_uast_2pm") if c in df.columns]
    for col in scoring_like:
        group_medians = df.groupby("position_group")[col].transform("median")
        df[col] = df[col].fillna(group_medians).fillna(df[col].median())

    # Position nulls
    df["position"] = df["position"].fillna("Unknown")
    df["position_group"] = df["position_group"].fillna("Unknown")

    # Αν τρέξει σε dataset χωρίς τις νέες στήλες (π.χ. παλιό nba_stats_full.csv),
    # γεμίζουμε με 0.0 (= population mean μετά z-score → neutral για similarity).
    for col in FEATURE_COLS:
        if col not in df.columns:
            df[col] = 0.0

    # Drop όποιες σειρές έχουν ακόμα null σε feature columns (ελάχιστες)
    df = df.dropna(subset=FEATURE_COLS).reset_index(drop=True)

    return df


def build_feature_matrix(df: pd.DataFrame) -> tuple[np.ndarray, StandardScaler]:
    """
    Επιστρέφει (matrix, scaler).
    matrix: shape (n_rows, len(FEATURE_COLS)), z-score normalized.
    scaler: φυλάγεται για να transform-αρουμε το user input με τον ίδιο τρόπο.
    """
    X = df[FEATURE_COLS].values.astype(float)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    return X_scaled, scaler


def transform_user_input(user_stats: dict, scaler: StandardScaler) -> np.ndarray:
    """
    Μετατρέπει user-defined stats dict σε scaled vector (shape: (1, n_features)).

    Stats που δεν ορίστηκαν → population mean (= 0 μετά τo scaling),
    άρα δεν επηρεάζουν το similarity score για αυτή τη διάσταση.
    """
    vec = scaler.mean_.copy()  # default: population mean για κάθε feature
    for i, col in enumerate(FEATURE_COLS):
        if col in user_stats:
            vec[i] = float(user_stats[col])
    return scaler.transform(vec.reshape(1, -1))


def build_percentile_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """
    Για κάθε feature column, υπολογίζει το percentile (0–100) κάθε row
    ως rank / n_rows × 100. Επιστρέφει DataFrame ίδιου shape με το df[FEATURE_COLS].
    """
    X = df[FEATURE_COLS].copy()
    pct = X.rank(pct=True) * 100
    pct.columns = [f"pct_{c}" for c in FEATURE_COLS]
    return pct


def stat_to_percentile(col: str, value: float, df: pd.DataFrame) -> float:
    """
    Μετατρέπει μία τιμή για συγκεκριμένο stat σε percentile vs όλο το dataset.
    Χρησιμοποιείται για να βρούμε σε ποιο percentile βρίσκεται το user's target.
    """
    series = df[col].dropna()
    return float((series < value).sum() / len(series) * 100)


def preprocess(path: Path = DATASET_PATH) -> tuple[pd.DataFrame, np.ndarray, StandardScaler]:
    """
    Κεντρική συνάρτηση. Επιστρέφει (df_clean, feature_matrix, scaler).
    """
    df = load_and_clean(path)
    matrix, scaler = build_feature_matrix(df)
    return df, matrix, scaler
