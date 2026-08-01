"""
Φέρνει NBA stats από nba_api και αποθηκεύει σε CSV.

Φάση 1 — bulk season stats (Base + Advanced):
  LeagueDashPlayerStats × 2 ανά season
  ~58 API calls, ~2 λεπτά

Φάση 1b — scoring profile:
  LeagueDashPlayerStats (Scoring) ανά season
  ~29 API calls, ~1 λεπτό

Φάση 1c — hustle stats:
  LeagueHustleStatsPlayer ανά season (2015-16+ μόνο)
  ~10 API calls, ~15 δευτερόλεπτα

Φάση 1d — defensive impact (matchup-based):
  LeagueDashPtDefend × 3 categories ανά season (2013-14+ μόνο)
  ~36 API calls, ~1 λεπτό

Φάση 2 — player info (position, height):
  CommonPlayerInfo ανά παίκτη (~2500 calls, ~60 λεπτά)
  Υποστηρίζει checkpoint/resume αν διακοπεί.

Output:
  data/seasons_raw.csv        ← merged Base+Advanced, όλες οι seasons
  data/seasons_scoring.csv    ← shot profile (% πόντων / % FGA ανά zone)
  data/seasons_hustle.csv     ← deflections, charges, box outs (2015-16+)
  data/seasons_defense.csv    ← DFG% / diff vs baseline ανά zone (2013-14+)
  data/player_info.csv        ← position, height, weight ανά παίκτη
  data/nba_stats_full.csv     ← τελικό merged dataset
"""

import json
import logging
import time
from pathlib import Path

import pandas as pd
from nba_api.stats.endpoints import (
    CommonPlayerInfo,
    LeagueDashPlayerStats,
    LeagueDashPtDefend,
    LeagueHustleStatsPlayer,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"

SLEEP_BULK = 1.0    # μεταξύ season calls (μικρός αριθμός calls)
SLEEP_PLAYER = 1.5  # μεταξύ per-player calls (πολλές κλήσεις)

# Seasons 1996-97 → 2024-25
SEASONS = [f"{y}-{str(y + 1)[2:]}" for y in range(1996, 2025)]

# Hustle stats διαθέσιμα μόνο από 2015-16 (nba.com player tracking era)
HUSTLE_SEASONS = [s for s in SEASONS if int(s[:4]) >= 2015]

# Defensive matchup tracking (SportVU): επιβεβαιωμένο ότι το 2012-13 επιστρέφει
# 0 rows ενώ το 2013-14 δίνει 481 — άρα το tracking ξεκινά ουσιαστικά το 2013-14.
DEFEND_SEASONS = [s for s in SEASONS if int(s[:4]) >= 2013]

# Columns που κρατάμε από το Base endpoint
BASE_COLS = [
    "PLAYER_ID", "PLAYER_NAME", "TEAM_ABBREVIATION", "AGE",
    "GP", "MIN",
    "FGM", "FGA", "FG_PCT",
    "FG3M", "FG3A", "FG3_PCT",
    "FTM", "FTA", "FT_PCT",
    "OREB", "DREB", "REB",
    "AST", "TOV", "STL", "BLK",
    "PTS", "PLUS_MINUS",
]

# Columns από το Advanced endpoint
ADVANCED_COLS = [
    "PLAYER_ID",
    "OFF_RATING", "DEF_RATING", "NET_RATING",
    "AST_PCT", "AST_TO",
    "OREB_PCT", "DREB_PCT", "REB_PCT",
    "TM_TOV_PCT", "EFG_PCT", "TS_PCT",
    "USG_PCT", "PACE", "PIE",
]

# Shot profile: ποσοστό πόντων / ποσοστό FGA ανά zone.
# Αυτό δίνει εικόνα του «τι είδους scorer» είναι ο παίκτης.
# Π.χ. DeRozan: pct_pts_midrange ψηλό · Curry: pct_pts_3pt ψηλό.
SCORING_COLS = [
    "PLAYER_ID",
    "PCT_FGA_2PT", "PCT_FGA_3PT",
    "PCT_PTS_2PT_MR",    # % πόντων από mid-range (API name: PCT_PTS_2PT_MR, όχι MIDRANGE)
    "PCT_PTS_PAINT",
    "PCT_PTS_3PT", "PCT_PTS_FT",
    "PCT_UAST_2PM",      # % of 2PM που είναι unassisted = self-creation signal (post scorer / creator)
]

# Hustle: defensive activity metrics — μόνο από 2015-16.
# Για παλαιότερες σεζόν τα πεδία αυτά θα είναι NaN στο final dataset
# και θα γεμίσουν με group median στο preprocessing (neutral signal).
HUSTLE_COLS = [
    "PLAYER_ID",
    "DEFLECTIONS", "CHARGES_DRAWN",
    "BOX_OUTS", "SCREEN_ASSISTS",
]

# Defensive impact (LeagueDashPtDefend) — τι σουτάρουν οι αντίπαλοι όταν ΑΥΤΟΣ
# είναι ο κοντινότερος defender.
#
# ΓΙΑΤΙ: το `deflections` μετράει ΣΤΥΛ άμυνας (ball-hawking), όχι ποιότητα —
# ο Mikal Bridges (elite on-ball, δεν κάνει gambles) έχει 1.71 ενώ ο Luka
# Doncic 3.38. Το DFG% μετράει ΑΠΟΤΕΛΕΣΜΑ, οπότε τους διαχωρίζει σωστά.
# Βλ. §versatile_wing_defender στο src/archetypes.py.
#
# ΠΡΟΣΟΧΗ — κάθε defense_category επιστρέφει ΔΙΑΦΟΡΕΤΙΚΑ column names:
#   Overall       → D_FGA / D_FG_PCT / NORMAL_FG_PCT / PCT_PLUSMINUS
#   3 Pointers    → FG3A  / FG3_PCT  / NS_FG3_PCT    / PLUSMINUS
#   Less Than 6Ft → FGA_LT_06 / LT_06_PCT / NS_LT_06_PCT / PLUSMINUS
# Τα κανονικοποιούμε σε <prefix>_fga / _pct / _diff ώστε ο downstream κώδικας
# να μη χρειάζεται να ξέρει το quirk. Το FG3_PCT ΠΡΕΠΕΙ να μετονομαστεί:
# συγκρούεται με το offensive fg3_pct του ίδιου του παίκτη.
#
# Το `_diff` (PCT_PLUSMINUS) είναι το πιο χρήσιμο σήμα: πόσο χειρότερα
# σουτάρουν οι αντίπαλοι σε σχέση με τον ΚΑΝΟΝΙΚΟ τους μέσο όρο. Είναι ήδη
# baseline-adjusted, άρα λιγότερο team/era-dependent από το raw DFG%.
# Αρνητικό = καλή άμυνα.
DEFEND_CATEGORIES = {
    "Overall": {
        "prefix": "d_ovr",
        "fga": "D_FGA", "pct": "D_FG_PCT",
        "base": "NORMAL_FG_PCT", "diff": "PCT_PLUSMINUS",
    },
    "3 Pointers": {
        "prefix": "d_fg3",
        "fga": "FG3A", "pct": "FG3_PCT",
        "base": "NS_FG3_PCT", "diff": "PLUSMINUS",
    },
    "Less Than 6Ft": {
        "prefix": "d_rim",
        "fga": "FGA_LT_06", "pct": "LT_06_PCT",
        "base": "NS_LT_06_PCT", "diff": "PLUSMINUS",
    },
}


# ─── Φάση 1: Base + Advanced ─────────────────────────────────────────────────

def fetch_season(season: str) -> pd.DataFrame | None:
    """
    Merged Base+Advanced DataFrame για μία σεζόν.
    Trades: κρατά το row με τα περισσότερα GP (total season stats).
    """
    try:
        log.info(f"  {season} Base...")
        base = LeagueDashPlayerStats(
            season=season,
            measure_type_detailed_defense="Base",
            per_mode_detailed="PerGame",
            timeout=30,
        ).get_data_frames()[0]
        time.sleep(SLEEP_BULK)

        log.info(f"  {season} Advanced...")
        adv = LeagueDashPlayerStats(
            season=season,
            measure_type_detailed_defense="Advanced",
            per_mode_detailed="PerGame",
            timeout=30,
        ).get_data_frames()[0]
        time.sleep(SLEEP_BULK)

    except Exception as e:
        log.error(f"  {season} failed: {e}")
        return None

    base_available = [c for c in BASE_COLS if c in base.columns]
    adv_available  = [c for c in ADVANCED_COLS if c in adv.columns]

    merged = base[base_available].merge(adv[adv_available], on="PLAYER_ID", how="left")
    merged["season"] = season

    merged = (
        merged
        .sort_values("GP", ascending=False)
        .drop_duplicates(subset="PLAYER_ID", keep="first")
        .reset_index(drop=True)
    )

    log.info(f"  {season} → {len(merged)} players")
    return merged


def fetch_all_seasons(output_path: Path) -> pd.DataFrame:
    if output_path.exists():
        log.info("seasons_raw.csv υπάρχει ήδη — παρακάμπτεται η fetch")
        return pd.read_csv(output_path)

    frames = []
    for season in SEASONS:
        df = fetch_season(season)
        if df is not None:
            frames.append(df)

    result = pd.concat(frames, ignore_index=True)
    result.to_csv(output_path, index=False)
    log.info(f"Αποθηκεύτηκαν {len(result)} rows → {output_path}")
    return result


# ─── Φάση 1b: Scoring profile ────────────────────────────────────────────────

def fetch_scoring_season(season: str) -> pd.DataFrame | None:
    """
    Shot profile για μία σεζόν — % FGA και % πόντων ανά zone.
    Κρίσιμο για τον midrange_scorer trait που δεν είχε direct signal.
    """
    try:
        log.info(f"  {season} Scoring...")
        df = LeagueDashPlayerStats(
            season=season,
            measure_type_detailed_defense="Scoring",
            per_mode_detailed="PerGame",
            timeout=30,
        ).get_data_frames()[0]
        time.sleep(SLEEP_BULK)
    except Exception as e:
        log.error(f"  {season} Scoring failed: {e}")
        return None

    # Κρατάμε GP για trade dedup, μετά το αφαιρούμε
    keep = [c for c in ["PLAYER_ID", "GP"] + SCORING_COLS[1:] if c in df.columns]
    result = df[keep].copy()

    if "GP" in result.columns:
        result = (
            result.sort_values("GP", ascending=False)
            .drop_duplicates(subset="PLAYER_ID", keep="first")
            .drop(columns=["GP"])
            .reset_index(drop=True)
        )

    result["season"] = season
    log.info(f"  {season} Scoring → {len(result)} players")
    return result


def fetch_all_scoring_stats(output_path: Path) -> pd.DataFrame:
    if output_path.exists():
        log.info("seasons_scoring.csv υπάρχει ήδη — παρακάμπτεται")
        return pd.read_csv(output_path)

    frames = []
    for season in SEASONS:
        df = fetch_scoring_season(season)
        if df is not None:
            frames.append(df)

    result = pd.concat(frames, ignore_index=True)
    result.to_csv(output_path, index=False)
    log.info(f"Αποθηκεύτηκαν {len(result)} rows → {output_path}")
    return result


# ─── Φάση 1c: Hustle stats ───────────────────────────────────────────────────

def fetch_hustle_season(season: str) -> pd.DataFrame | None:
    """
    Hustle/tracking stats για μία σεζόν.
    Χρησιμοποιεί 'G' (όχι 'GP') για games — διαφορετικό naming από το LeagueDashPlayerStats.
    """
    try:
        log.info(f"  {season} Hustle...")
        df = LeagueHustleStatsPlayer(
            season=season,
            per_mode_time="PerGame",       # σωστό parameter name σε αυτή την έκδοση nba_api
            season_type_all_star="Regular Season",
            timeout=30,
        ).get_data_frames()[0]
        time.sleep(SLEEP_BULK)
    except Exception as e:
        log.error(f"  {season} Hustle failed: {e}")
        return None

    # Hustle endpoint χρησιμοποιεί "G" για games (όχι "GP")
    gp_col = "G" if "G" in df.columns else None
    extra  = [gp_col] if gp_col else []
    keep   = [c for c in ["PLAYER_ID"] + extra + HUSTLE_COLS[1:] if c in df.columns]
    result = df[keep].copy()

    if gp_col and gp_col in result.columns:
        result = (
            result.sort_values(gp_col, ascending=False)
            .drop_duplicates(subset="PLAYER_ID", keep="first")
            .drop(columns=[gp_col])
            .reset_index(drop=True)
        )

    result["season"] = season
    log.info(f"  {season} Hustle → {len(result)} players")
    return result


def fetch_all_hustle_stats(output_path: Path) -> pd.DataFrame:
    if output_path.exists():
        log.info("seasons_hustle.csv υπάρχει ήδη — παρακάμπτεται")
        return pd.read_csv(output_path)

    frames = []
    for season in HUSTLE_SEASONS:
        df = fetch_hustle_season(season)
        if df is not None:
            frames.append(df)

    if not frames:
        log.warning("Κανένα hustle data — επιστρέφεται κενό DataFrame")
        empty = pd.DataFrame(columns=["PLAYER_ID", "season"] + HUSTLE_COLS[1:])
        empty.to_csv(output_path, index=False)
        return empty

    result = pd.concat(frames, ignore_index=True)
    result.to_csv(output_path, index=False)
    log.info(f"Αποθηκεύτηκαν {len(result)} rows → {output_path}")
    return result


# ─── Φάση 1d: Defensive impact (matchup-based) ───────────────────────────────

def fetch_defend_category(season: str, category: str) -> pd.DataFrame | None:
    """
    DFG% για μία σεζόν × μία defense_category.

    Το endpoint κλειδώνει στο `CLOSE_DEF_PERSON_ID` (όχι `PLAYER_ID`) — είναι
    ο defender, όχι ο shooter. Το μετονομάζουμε ώστε να κάνει join με τα
    υπόλοιπα sources.
    """
    spec = DEFEND_CATEGORIES[category]
    try:
        log.info(f"  {season} Defend [{category}]...")
        df = LeagueDashPtDefend(
            season=season,
            defense_category=category,
            per_mode_simple="PerGame",
            season_type_all_star="Regular Season",
            timeout=30,
        ).get_data_frames()[0]
        time.sleep(SLEEP_BULK)
    except Exception as e:
        log.error(f"  {season} Defend [{category}] failed: {e}")
        return None

    if df.empty:
        log.warning(f"  {season} Defend [{category}] → 0 rows (πριν το tracking era;)")
        return None

    df = df.rename(columns={"CLOSE_DEF_PERSON_ID": "PLAYER_ID"})

    p = spec["prefix"]
    rename = {
        spec["fga"]:  f"{p}_fga",     # volume — πόσο συχνά τον challenge-άρουν
        spec["pct"]:  f"{p}_pct",     # τι σουτάρουν εναντίον του
        spec["base"]: f"{p}_base",    # τι σουτάρουν κανονικά
        spec["diff"]: f"{p}_diff",    # διαφορά· αρνητικό = καλή άμυνα
    }
    missing = [c for c in rename if c not in df.columns]
    if missing:
        log.warning(f"  {season} [{category}]: λείπουν columns {missing} — skip")
        return None

    # Games column: το endpoint δίνει και GP και G· κρατάμε ό,τι υπάρχει για dedup
    gp_col = "GP" if "GP" in df.columns else ("G" if "G" in df.columns else None)
    keep = ["PLAYER_ID"] + ([gp_col] if gp_col else []) + list(rename)
    result = df[keep].rename(columns=rename)

    if gp_col:
        result = (
            result.sort_values(gp_col, ascending=False)
            .drop_duplicates(subset="PLAYER_ID", keep="first")
            .drop(columns=[gp_col])
            .reset_index(drop=True)
        )
    else:
        result = result.drop_duplicates(subset="PLAYER_ID", keep="first")

    return result


def fetch_defense_season(season: str) -> pd.DataFrame | None:
    """Και τις 3 categories για μία σεζόν, merged σε ένα row ανά παίκτη."""
    merged: pd.DataFrame | None = None
    for category in DEFEND_CATEGORIES:
        part = fetch_defend_category(season, category)
        if part is None:
            continue
        merged = part if merged is None else merged.merge(part, on="PLAYER_ID", how="outer")

    if merged is None:
        return None

    merged["season"] = season
    log.info(f"  {season} Defense → {len(merged)} players")
    return merged


def fetch_all_defense_stats(output_path: Path) -> pd.DataFrame:
    if output_path.exists():
        log.info("seasons_defense.csv υπάρχει ήδη — παρακάμπτεται")
        return pd.read_csv(output_path)

    frames = []
    for season in DEFEND_SEASONS:
        df = fetch_defense_season(season)
        if df is not None:
            frames.append(df)

    cols = [f"{s['prefix']}_{k}" for s in DEFEND_CATEGORIES.values()
            for k in ("fga", "pct", "base", "diff")]
    if not frames:
        log.warning("Κανένα defense data — επιστρέφεται κενό DataFrame")
        empty = pd.DataFrame(columns=["PLAYER_ID", "season"] + cols)
        empty.to_csv(output_path, index=False)
        return empty

    result = pd.concat(frames, ignore_index=True)
    result.to_csv(output_path, index=False)
    log.info(f"Αποθηκεύτηκαν {len(result)} rows → {output_path}")
    return result


# ─── Φάση 2: Player info ──────────────────────────────────────────────────────

def height_to_cm(height_str: str) -> float | None:
    """'6-9' → 205.74. Returns None αν το format δεν αναγνωριστεί."""
    try:
        feet, inches = str(height_str).strip().split("-")
        return round(int(feet) * 30.48 + int(inches) * 2.54, 2)
    except Exception:
        return None


def fetch_player_info(player_ids: list[int], output_path: Path) -> pd.DataFrame:
    """
    Φέρνει position, height, weight για κάθε μοναδικό παίκτη.
    Checkpoint κάθε 100 παίκτες για resume αν διακοπεί.
    """
    if output_path.exists():
        log.info("player_info.csv υπάρχει ήδη — παρακάμπτεται η fetch")
        return pd.read_csv(output_path)

    checkpoint_path = DATA_DIR / "player_info_checkpoint.json"
    done: dict = {}
    if checkpoint_path.exists():
        with open(checkpoint_path) as f:
            done = json.load(f)
        log.info(f"Checkpoint: {len(done)} παίκτες ήδη fetched")

    remaining = [pid for pid in player_ids if str(pid) not in done]
    log.info(f"Fetch player info: {len(remaining)} παίκτες ({len(done)} από checkpoint)")

    for i, pid in enumerate(remaining):
        try:
            row = CommonPlayerInfo(player_id=pid, timeout=30).get_data_frames()[0].iloc[0]
            done[str(pid)] = {
                "position": str(row.get("POSITION", "")),
                "height_raw": str(row.get("HEIGHT", "")),
                "height_cm": height_to_cm(str(row.get("HEIGHT", ""))),
                "weight_lbs": row.get("WEIGHT", None),
                "country": str(row.get("COUNTRY", "")),
                "birthdate": str(row.get("BIRTHDATE", "")),
            }
        except Exception as e:
            log.warning(f"  Player {pid} failed: {e}")
            done[str(pid)] = {}

        if (i + 1) % 100 == 0:
            with open(checkpoint_path, "w") as f:
                json.dump(done, f)
            pct = (i + 1) / len(remaining) * 100
            log.info(f"  Checkpoint: {i + 1}/{len(remaining)} ({pct:.0f}%)")

        time.sleep(SLEEP_PLAYER)

    with open(checkpoint_path, "w") as f:
        json.dump(done, f)

    rows = [{"player_id": int(pid), **info} for pid, info in done.items()]
    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    log.info(f"Αποθηκεύτηκαν {len(df)} player profiles → {output_path}")
    return df


# ─── Merge & κανονικοποίηση ───────────────────────────────────────────────────

POSITION_MAP = {
    "Guard": "G",
    "Guard-Forward": "G-F",
    "Forward-Guard": "G-F",
    "Forward": "F",
    "Forward-Center": "F-C",
    "Center-Forward": "F-C",
    "Center": "C",
}


def build_final_dataset(
    seasons_df: pd.DataFrame,
    info_df: pd.DataFrame,
    scoring_df: pd.DataFrame | None = None,
    hustle_df: pd.DataFrame | None = None,
    defense_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Merge όλων των sources σε ένα DataFrame.

    Merge order:
    1. seasons_raw (Base+Advanced) LEFT JOIN seasons_scoring (on player_id + season)
    2. result LEFT JOIN seasons_hustle (on player_id + season)
       → NaN για pre-2015 rows (χειρίζεται στο preprocessing)
    3. result LEFT JOIN seasons_defense (on player_id + season)
       → NaN για pre-2013 rows· το preprocessing καταγράφει `avail_*` πριν το
         imputation και το similarity engine τα μασκάρει (βλ. CLAUDE.md)
    4. result LEFT JOIN player_info (on player_id)

    LEFT JOIN παντού: κρατάμε όλες τις σεζόν, ακόμα και αν λείπει κάποιο source.
    """
    # Ομοιόμορφα ονόματα για join keys
    if "PLAYER_ID" in info_df.columns:
        info_df = info_df.rename(columns={"PLAYER_ID": "player_id"})

    seasons_df = seasons_df.rename(columns={"PLAYER_ID": "player_id"})

    merged = seasons_df.copy()

    # Φάση 1b merge: scoring profile
    if scoring_df is not None and not scoring_df.empty:
        scoring_df = scoring_df.rename(columns={"PLAYER_ID": "player_id"})
        scoring_cols = [c for c in scoring_df.columns if c not in ("player_id", "season")]
        merged = merged.merge(
            scoring_df[["player_id", "season"] + scoring_cols],
            on=["player_id", "season"],
            how="left",
        )

    # Φάση 1c merge: hustle stats (NaN για pre-2015 seasons — φυσιολογικό)
    if hustle_df is not None and not hustle_df.empty:
        hustle_df = hustle_df.rename(columns={"PLAYER_ID": "player_id"})
        hustle_cols = [c for c in hustle_df.columns if c not in ("player_id", "season")]
        merged = merged.merge(
            hustle_df[["player_id", "season"] + hustle_cols],
            on=["player_id", "season"],
            how="left",
        )

    # Φάση 1d merge: defensive impact (NaN για pre-2013 seasons — φυσιολογικό)
    if defense_df is not None and not defense_df.empty:
        defense_df = defense_df.rename(columns={"PLAYER_ID": "player_id"})
        defense_cols = [c for c in defense_df.columns if c not in ("player_id", "season")]
        merged = merged.merge(
            defense_df[["player_id", "season"] + defense_cols],
            on=["player_id", "season"],
            how="left",
        )

    # Φάση 2 merge: player info
    merged = merged.merge(
        info_df[["player_id", "position", "height_cm", "weight_lbs", "country"]],
        on="player_id",
        how="left",
    )

    merged["position_group"] = merged["position"].map(POSITION_MAP).fillna(merged["position"])

    # Lowercase column names για consistency με το υπόλοιπο codebase
    merged.columns = [c.lower() for c in merged.columns]

    return merged


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    DATA_DIR.mkdir(exist_ok=True)

    # Φάση 1: Base + Advanced (skip αν υπάρχει)
    seasons_df = fetch_all_seasons(DATA_DIR / "seasons_raw.csv")
    log.info(f"Seasons dataset: {len(seasons_df)} rows")

    # Φάση 1b: Scoring profile (skip αν υπάρχει)
    log.info("=== Φάση 1b: Scoring profile ===")
    scoring_df = fetch_all_scoring_stats(DATA_DIR / "seasons_scoring.csv")

    # Φάση 1c: Hustle stats (skip αν υπάρχει)
    log.info("=== Φάση 1c: Hustle stats ===")
    hustle_df = fetch_all_hustle_stats(DATA_DIR / "seasons_hustle.csv")

    # Φάση 1d: Defensive impact (skip αν υπάρχει)
    log.info("=== Φάση 1d: Defensive impact ===")
    defense_df = fetch_all_defense_stats(DATA_DIR / "seasons_defense.csv")

    # Φάση 2: Player info (skip αν υπάρχει)
    log.info("=== Φάση 2: Player info ===")
    player_ids = seasons_df["PLAYER_ID"].unique().tolist()
    info_df = fetch_player_info(player_ids, DATA_DIR / "player_info.csv")

    # Merge όλων
    log.info("=== Merge ===")
    final = build_final_dataset(seasons_df, info_df, scoring_df, hustle_df, defense_df)
    out = DATA_DIR / "nba_stats_full.csv"
    final.to_csv(out, index=False)

    log.info(f"Τελικό dataset: {len(final)} rows × {len(final.columns)} columns → {out}")
    log.info(f"Columns: {final.columns.tolist()}")


if __name__ == "__main__":
    main()
