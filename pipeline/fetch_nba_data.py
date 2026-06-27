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

Φάση 2 — player info (position, height):
  CommonPlayerInfo ανά παίκτη (~2500 calls, ~60 λεπτά)
  Υποστηρίζει checkpoint/resume αν διακοπεί.

Output:
  data/seasons_raw.csv        ← merged Base+Advanced, όλες οι seasons
  data/seasons_scoring.csv    ← shot profile (% πόντων / % FGA ανά zone)
  data/seasons_hustle.csv     ← deflections, charges, box outs (2015-16+)
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
) -> pd.DataFrame:
    """
    Merge όλων των sources σε ένα DataFrame.

    Merge order:
    1. seasons_raw (Base+Advanced) LEFT JOIN seasons_scoring (on player_id + season)
    2. result LEFT JOIN seasons_hustle (on player_id + season)
       → NaN για pre-2015 rows (χειρίζεται στο preprocessing)
    3. result LEFT JOIN player_info (on player_id)

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

    # Φάση 2: Player info (skip αν υπάρχει)
    log.info("=== Φάση 2: Player info ===")
    player_ids = seasons_df["PLAYER_ID"].unique().tolist()
    info_df = fetch_player_info(player_ids, DATA_DIR / "player_info.csv")

    # Merge όλων
    log.info("=== Merge ===")
    final = build_final_dataset(seasons_df, info_df, scoring_df, hustle_df)
    out = DATA_DIR / "nba_stats_full.csv"
    final.to_csv(out, index=False)

    log.info(f"Τελικό dataset: {len(final)} rows × {len(final.columns)} columns → {out}")
    log.info(f"Columns: {final.columns.tolist()}")


if __name__ == "__main__":
    main()
