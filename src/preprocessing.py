"""
Φόρτωμα, καθαρισμός και normalization του dataset για το matching engine.

Output της preprocess():
  df_clean     — φιλτραρισμένο DataFrame με metadata + raw stats
  feature_matrix — numpy array (n_rows × 21), StandardScaler normalized
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

# Hustle/tracking columns — διαθέσιμα μόνο από το LeagueHustleStatsPlayer endpoint.
HUSTLE_COLS = ("deflections", "charges_drawn", "box_outs", "screen_assists")

# Matchup-based defensive impact (LeagueDashPtDefend, Phase 1d) — διαθέσιμα από
# 2013-14. Ίδιο coverage pattern με τα hustle: group-median imputation + avail_*
# tracking, ώστε το availability-aware masking να τα χειριστεί σωστά.
DEFENSE_COLS = (
    "d_ovr_fga", "d_ovr_pct", "d_ovr_base", "d_ovr_diff",
    "d_fg3_fga", "d_fg3_pct", "d_fg3_base", "d_fg3_diff",
    "d_rim_fga", "d_rim_pct", "d_rim_base", "d_rim_diff",
)

# Σεζόν με αναξιόπιστα hustle data, που ΔΕΝ πρέπει να μπουν στο feature space.
#
# Το 2015-16 είναι η σεζόν που το NBA πρωτοξεκίνησε hustle tracking, mid-season:
# μόνο 147/476 rows έχουν τιμές (31%) και αυτές είναι partial-season sample από
# τα πρώτα tracked παιχνίδια — όχι season averages. Το αποτύπωμα είναι σαφές:
#   deflections    89.8% ακέραιες τιμές, max 11.00/gm (Dwight Howard)
#   charges_drawn  98.6% ακέραιες, box_outs 100%, screen_assists 92.5%
# ενώ κάθε επόμενη σεζόν έχει ~5-10% ακέραιες και max ~4-5 deflections/gm.
#
# Η σωστή κλίμακα δεν είναι ανακτήσιμη (δεν ξέρουμε σε πόσα παιχνίδια αντιστοιχεί
# κάθε row), οπότε τα invalidate-άρουμε → πάνε στο ίδιο group-median imputation
# path με τις pre-2015 σεζόν. Χωρίς αυτό, οι corrupt τιμές κυριαρχούν στην ουρά
# της κατανομής (z έως +18) και εμφανίζονται πρώτες σε κάθε defensive query.
CORRUPT_HUSTLE_SEASONS = frozenset({"2015-16"})

# Prefix για τις boolean στήλες που καταγράφουν αν μια τιμή είναι ΠΡΑΓΜΑΤΙΚΗ ή
# imputed. Γράφονται πριν από κάθε fillna, γιατί μετά η πληροφορία χάνεται.
# Τις καταναλώνει το build_availability_matrix() → similarity.find_similar().
AVAIL_PREFIX = "avail_"


def get_min_mpg(season: str) -> float:
    """
    Tiered MPG threshold ανά εποχή.

    1996–2012 (pre-tracking era): ≥20 MPG — κρατάμε μόνο meaningful contributors.
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
    # Defense — stl/blk + deflections (tracking, 2016-17+; pre-era: group median)
    "stl", "blk", "deflections",
    # def_rating: 100% coverage σε όλες τις σεζόν (1996+), σε αντίθεση με το
    # deflections που υπάρχει μόνο από το 2016-17. Είναι το ΜΟΝΟ defensive signal
    # που καλύπτει όλη τη βάση, οπότε δίνει στον χρήστη τρόπο να ζητήσει άμυνα
    # χωρίς να αποκλείσει το 56% των rows (βλ. CORRUPT_HUSTLE_SEASONS σχόλιο).
    # Ήδη validated: ο classifier το χρησιμοποιεί σε 4 defensive traits
    # (archetypes.py) — μέχρι τώρα η similarity engine δεν είχε πρόσβαση.
    # Team-dependent (adds noise) αλλά corr ≤0.16 με ό,τι άλλο υπάρχει εδώ,
    # δηλαδή σχεδόν εξ ολοκλήρου νέα πληροφορία.
    # ΠΡΟΣΟΧΗ: χαμηλό = καλή άμυνα (αντίθετη κατεύθυνση από τα υπόλοιπα features).
    "def_rating",
    # Matchup-based defensive impact (Phase 1d): πόσο ΧΕΙΡΟΤΕΡΑ σουτάρουν οι
    # αντίπαλοι όταν αυτός είναι ο κοντινότερος defender, vs τον κανονικό τους
    # μέσο όρο. Αρνητικό = καλή άμυνα.
    #
    # Γιατί αυτά τα δύο και όχι το d_ovr_diff: είναι σχεδόν ΟΡΘΟΓΩΝΙΑ μεταξύ
    # τους (corr −0.01) — perimeter και rim defense είναι ξεχωριστά skills, που
    # ταιριάζουν σε διαφορετικά traits. Το d_ovr_diff είναι μίγμα τους (0.44 /
    # 0.60) και έχει ήδη corr 0.43 με το def_rating, άρα προσθέτει λίγα.
    #
    # Γιατί αξίζουν παρά το deflections: μετρούν ΑΠΟΤΕΛΕΣΜΑ, όχι στυλ.
    # corr(deflections, d_ovr_diff) = +0.017 — ουσιαστικά νέα πληροφορία.
    # Era-stable χωρίς centering (corr με σεζόν −0.009), σε αντίθεση με το
    # def_rating, γιατί το _diff είναι ήδη baseline-adjusted.
    "d_fg3_diff",   # perimeter defense
    "d_rim_diff",   # rim protection — corr −0.52 με blk· blocks ≠ deterrence
    # Overall impact (team-dependent αλλά adds signal)
    "net_rating",
    # Physical
    "height_cm", "weight_lbs",
]


def load_and_clean(path: Path = DATASET_PATH) -> pd.DataFrame:
    # low_memory=False: το CSV έχει 67 στήλες και το `weight_lbs` αποθηκεύεται ως
    # string (βλ. numeric coercion παρακάτω). Με chunked parsing η στήλη βγάζει
    # διαφορετικό dtype ανά chunk → DtypeWarning. Δεν επηρεάζει τα δεδομένα,
    # αλλά ο πλήρης parse είναι ντετερμινιστικός και σβήνει τον θόρυβο.
    df = pd.read_csv(path, low_memory=False)

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

    # Hustle stats: NaN για seasons πριν το tracking era — γεμίζουμε με
    # position_group median. Πρώτα όμως invalidate-άρουμε τις σεζόν που έχουν
    # μεν τιμές αλλά σε λάθος κλίμακα (βλ. CORRUPT_HUSTLE_SEASONS), αλλιώς οι
    # corrupt τιμές θα περάσουν αυτούσιες στο feature space.
    #
    # ΣΗΜΕΙΩΣΗ για το imputation: το group median δίνει z ≈ 0, που είναι neutral
    # ΜΟΝΟ όσο ο χρήστης δεν ορίζει το stat στο query του. Μόλις το ορίσει (π.χ.
    # «θέλω 3.5 deflections»), κάθε imputed row κάθεται σε σταθερή απόσταση
    # τιμωρίας και αποκλείεται de facto. Γι' αυτό προστέθηκε το def_rating στα
    # FEATURE_COLS: δίνει defensive signal με κάλυψη σε ΟΛΕΣ τις σεζόν.
    hustle_like = [c for c in HUSTLE_COLS if c in df.columns]
    if hustle_like:
        corrupt = df["season"].isin(CORRUPT_HUSTLE_SEASONS)
        df.loc[corrupt, hustle_like] = np.nan

    # Καταγραφή διαθεσιμότητας ΠΡΙΝ το fillna — μετά είναι αδύνατο να ξεχωρίσεις
    # πραγματική τιμή από imputed. Το similarity engine το χρησιμοποιεί για να
    # υπολογίζει distance μόνο στις διαστάσεις που όντως ξέρουμε.
    for col in hustle_like:
        df[f"{AVAIL_PREFIX}{col}"] = df[col].notna()

    for col in hustle_like:
        group_medians = df.groupby("position_group")[col].transform("median")
        df[col] = df[col].fillna(group_medians).fillna(df[col].median())

    # Defensive impact (Phase 1d): ίδιο pattern — avail_* πριν το fillna.
    # Λείπουν πριν το 2013-14, οπότε χωρίς availability tracking ένα query που
    # ζητά «καλή perimeter άμυνα» θα απέκλειε de facto όλη την pre-tracking εποχή
    # (το ίδιο bug που διορθώθηκε στο Phase 9 για τα hustle stats).
    defense_like = [c for c in DEFENSE_COLS if c in df.columns]
    for col in defense_like:
        df[f"{AVAIL_PREFIX}{col}"] = df[col].notna()
    for col in defense_like:
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

    # ── Season-relative centering του def_rating ──────────────────────────────
    # Το def_rating είναι έντονα era-dependent: corr(def_rating, season) = 0.62.
    # League mean 1998-99: 99.7 → 2023-24: 113.1, δηλαδή spread 13.4 points,
    # ενώ το within-season std είναι μόλις 3.7. Η διαφορά ΕΠΟΧΗΣ είναι 3.6×
    # μεγαλύτερη από τη διαφορά ΠΑΙΚΤΩΝ (pace + 3pt revolution ανέβασαν τα
    # ratings όλων).
    #
    # Χωρίς διόρθωση, ένα global z-score κωδικοποιεί «ποια δεκαετία» αντί για
    # «πόσο καλός αμυντικός»: ένας μέτριος του 1998 φαίνεται elite δίπλα σε
    # έναν κορυφαίο του 2023, και κάθε defensive query γεμίζει με παλιούς
    # παίκτες (μετρημένο: 84% pre-2016 vs 58% baseline).
    #
    # Re-centering ανά σεζόν στο global mean: κρατά τις ΜΟΝΑΔΕΣ (def rating
    # points), οπότε τα UI ranges και το API contract δεν αλλάζουν, αλλά η τιμή
    # σημαίνει πλέον «πόσο καλύτερος από τον μέσο όρο ΤΗΣ ΕΠΟΧΗΣ ΤΟΥ».
    # Προτιμήθηκε από full per-season z-score ακριβώς γι' αυτό: το z θα άλλαζε
    # τις μονάδες και θα έσπαγε το stat builder.
    #
    # Η αρχική τιμή διατηρείται ως def_rating_raw για display/debugging.
    if "def_rating" in df.columns:
        df["def_rating_raw"] = df["def_rating"]
        season_mean = df.groupby("season")["def_rating"].transform("mean")
        df["def_rating"] = df["def_rating"] - season_mean + df["def_rating"].mean()

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


def build_availability_matrix(df: pd.DataFrame) -> np.ndarray:
    """
    Boolean array (n_rows × len(FEATURE_COLS)): True όπου η τιμή είναι πραγματική
    μέτρηση, False όπου προέκυψε από imputation.

    Features χωρίς `avail_<col>` στήλη θεωρούνται πάντα διαθέσιμα — ισχύει για
    όλα εκτός των hustle stats, που λείπουν πριν το 2016-17.
    """
    avail = np.ones((len(df), len(FEATURE_COLS)), dtype=bool)
    for i, col in enumerate(FEATURE_COLS):
        flag = f"{AVAIL_PREFIX}{col}"
        if flag in df.columns:
            avail[:, i] = df[flag].to_numpy(dtype=bool)
    return avail


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
