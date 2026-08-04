"""
Engine layer — γεφυρώνει το FastAPI με τον υπάρχοντα κώδικα στο `src/`.

Ευθύνες:
  1. Φόρτωμα dataset μία φορά στο startup (preprocess + classify + percentiles)
  2. Wrappers γύρω από τις find_similar / classify — ΧΩΡΙΣ αλλαγή του src/ κώδικα
  3. Serialization των αποτελεσμάτων σε display-ready JSON (z→display, percentiles,
     match-quality classes) ώστε ο React client να μένει thin

Ο υπάρχων κώδικας στο src/ κάνει bare imports (`from preprocessing import ...`),
οπότε προσθέτουμε το src/ στο sys.path εδώ αντί να τον πειράξουμε.
"""

from __future__ import annotations

import sys
import unicodedata
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

# Πλήθος bins στο histogram που σερβίρει το /stats ανά feature. 24 είναι αρκετά
# για να διαβάζεται το σχήμα της κατανομής σε ένα ~370px sparkline και αρκετά
# λίγα ώστε το payload να μένει μικρό (23 features × 24 floats).
_DIST_BINS = 24


def _ascii_fold(s: str) -> str:
    """Strip diacritics ώστε "Jokic" να ματσάρει "Jokić" (NFKD + drop combining)."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", str(s)) if not unicodedata.combining(c)
    ).lower()

# ── src/ στο path ώστε τα bare imports (preprocessing/archetypes/similarity) να δουλέψουν
_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from preprocessing import (  # noqa: E402
    preprocess,
    build_percentile_matrix,
    stat_to_percentile,
    AVAIL_PREFIX,
    FEATURE_COLS,
)
from archetypes import classify, COMPOUNDS, PRESET_POSITIONS, TRAITS  # noqa: E402
from similarity import find_similar  # noqa: E402

from metadata import (  # noqa: E402
    ALL_TRAITS,
    DISPLAY_LABELS,
    GROUPS,
    PCT_COLS,
    to_internal,
    to_display,
    format_display,
    stats_metadata,
)


class Engine:
    """Κρατά το φορτωμένο dataset + scaler και εξυπηρετεί τα API requests."""

    def __init__(self) -> None:
        self.df: pd.DataFrame | None = None
        self.matrix: np.ndarray | None = None
        self.scaler = None
        # Cache του /stats payload — οι κατανομές είναι ακριβές να ξαναϋπολογίζονται
        # ανά request και το df είναι immutable μετά το load().
        self._stats_meta: dict | None = None
        # (player_name, season) → set των features που ΕΛΕΙΠΑΝ και είναι imputed.
        self._imputed: dict[tuple[str, str], frozenset[str]] = {}

    # ── Startup ────────────────────────────────────────────────────────────────
    def load(self) -> None:
        """Φορτώνει το dataset. Καλείται μία φορά στο FastAPI lifespan startup."""
        df, matrix, scaler = preprocess()
        df = classify(df)
        pct_df = build_percentile_matrix(df)
        df = pd.concat([df, pct_df], axis=1)

        # Precompute diacritic-folded names για robust substring search
        df["_name_fold"] = df["player_name"].map(_ascii_fold)

        self.df = df
        self.matrix = matrix
        self.scaler = scaler
        self._stats_meta = self._build_stats_meta()
        self._imputed = self._build_imputed_index()

    def _build_imputed_index(self) -> dict[tuple[str, str], frozenset[str]]:
        """
        Ποια features είναι group-median imputed ανά (player_name, season).

        Το `find_similar()` επιστρέφει προβολή μόνο των result_cols — οι στήλες
        `avail_*` δεν επιβιώνουν, οπότε το serialization δεν μπορεί να τις
        διαβάσει από το result row. Το κλειδί είναι (player_name, season) και όχι
        player_id γιατί ούτε το player_id επιβιώνει· είναι μοναδικό στην πράξη,
        αφού το find_similar κρατά μία σεζόν ανά παίκτη.
        """
        df = self.df
        cols = [c for c in FEATURE_COLS if AVAIL_PREFIX + c in df.columns]
        if not cols:
            return {}

        index: dict[tuple[str, str], frozenset[str]] = {}
        avail = df[[AVAIL_PREFIX + c for c in cols]].astype(bool)
        for pos, (name, season) in enumerate(zip(df["player_name"], df["season"])):
            missing = frozenset(c for j, c in enumerate(cols) if not avail.iat[pos, j])
            if missing:
                index[(str(name), str(season))] = missing
        return index

    @property
    def ready(self) -> bool:
        return self.df is not None

    @property
    def n_players(self) -> int:
        return 0 if self.df is None else int(self.df["player_id"].nunique())

    @property
    def n_rows(self) -> int:
        return 0 if self.df is None else int(len(self.df))

    # ── Display helpers (port από streamlit_app.py) ────────────────────────────
    def _z_to_display(self, col: str, z: float) -> float:
        """Z-score → raw internal value → display value."""
        i = FEATURE_COLS.index(col)
        raw = float(z) * self.scaler.scale_[i] + self.scaler.mean_[i]
        return to_display(col, raw)

    # Ίδιο (col, value) ζητιέται επανειλημμένα ανά request — μέχρι top_n × 7 φορές
    # στο _explain_entries, ενώ η τιμή είναι πάντα η ίδια (user target ή population
    # mean). Το engine είναι singleton με immutable df μετά το load(), οπότε το
    # caching στη μέθοδο ζει ασφαλώς όσο ζει το process.
    @lru_cache(maxsize=4096)
    def _user_percentile(self, col: str, internal_val: float) -> float:
        return stat_to_percentile(col, internal_val, self.df)

    # ── /similar ───────────────────────────────────────────────────────────────
    def similar(
        self,
        stats: dict[str, float],
        weights: dict[str, float] | None,
        top_n: int,
        active_traits: list[str] | None,
        season_range: str | None,
    ) -> dict:
        """
        stats: display-unit values ανά feature key (π.χ. {"ts_pct": 60.0, "pts": 25}).
               Μετατρέπονται σε internal εδώ (÷100 για PCT_COLS).
        Επιστρέφει serialized payload έτοιμο για JSON.
        """
        internal_stats = {c: to_internal(c, v) for c, v in stats.items()}

        results = find_similar(
            user_stats=internal_stats,
            df_clean=self.df,
            feature_matrix=self.matrix,
            scaler=self.scaler,
            weights=weights or None,
            top_n=top_n,
            active_traits=active_traits or None,
            season_range=season_range,
        )

        if results.empty:
            return {"count": 0, "results": [], "requested_stats": list(stats.keys())}

        specified = list(stats.keys())
        radar_axes = specified[:8]  # max 8 axes για readability (ίδιο με Streamlit)

        # Percentiles του user target (ίδια για όλα τα matches)
        user_radar = [self._user_percentile(c, internal_stats[c]) for c in radar_axes]

        serialized = [
            self._serialize_match(row, rank, internal_stats, radar_axes, user_radar)
            for rank, (_, row) in enumerate(results.iterrows(), start=1)
        ]

        return {
            "count": len(serialized),
            "results": serialized,
            "requested_stats": specified,
        }

    def _serialize_match(
        self,
        row: pd.Series,
        rank: int,
        internal_stats: dict[str, float],
        radar_axes: list[str],
        user_radar: list[float],
    ) -> dict:
        exp = row["explanation"] or {}

        # Το explain_match() γεμίζει και τις δύο λίστες μέχρι top_n=4 με argsort
        # πάνω σε ΟΛΑ τα features — τα unspecified απλώς πάνε τελευταία, δεν
        # κόβονται. Όταν ο χρήστης ορίσει λιγότερα από 4 stats, οι λίστες
        # (α) γεμίζουν με features που ΔΕΝ ζητήθηκαν και δεν βάρυναν καθόλου στο
        # distance, και (β) επικαλύπτονται μεταξύ τους (τα ίδια 3 stats, ανάποδη
        # σειρά). Και τα δύο θα εμφανίζονταν στο breakdown ως πραγματική
        # συνεισφορά. Φιλτράρουμε εδώ, στο serialization layer, γιατί το ποια
        # στοιχεία *δείχνεις* είναι ευθύνη του API — όχι του engine.
        requested = set(internal_stats)
        matching_raw = [e for e in exp.get("matching", []) if e["feature"] in requested][:4]
        seen = {e["feature"] for e in matching_raw}
        diverging_raw = [
            e for e in exp.get("diverging", [])
            if e["feature"] in requested and e["feature"] not in seen
        ][:3]

        matching = self._explain_entries(matching_raw, internal_stats, row, kind="match")
        diverging = self._explain_entries(diverging_raw, internal_stats, row, kind="diverge")

        player_radar = [float(row.get(f"pct_{c}", 50.0)) for c in radar_axes]

        height = row.get("height_cm")
        weight = row.get("weight_lbs")

        return {
            "rank":               rank,
            "player_name":        str(row["player_name"]),
            "season":             str(row["season"]),
            "position_group":     str(row.get("position_group", "—")),
            "compound_archetype": str(row["compound_archetype"]),
            "height_cm":          _num(height),
            "weight_lbs":         _num(weight),
            "similarity":         float(row["similarity"]),
            # Κλάσμα του ζητούμενου weight που είχε πραγματικά δεδομένα για
            # αυτό το row. < 1.0 σημαίνει ότι κάποιο ζητούμενο stat δεν
            # υπάρχει για την εποχή του παίκτη (hustle stats πριν το 2016-17)
            # και το score έχει ήδη shrink-άρει ανάλογα — ο client το δείχνει
            # ως confidence indicator.
            "coverage":           float(row.get("coverage", 1.0)),
            "boost":              float(row["boost"]),
            "final_score":        float(row["final_score"]),
            "active_traits":      list(row.get("active_traits", []) or []),
            "matching":           matching,
            "diverging":          diverging,
            "radar": {
                "axes":   [DISPLAY_LABELS.get(c, c) for c in radar_axes],
                "keys":   radar_axes,
                "user":   [round(v, 1) for v in user_radar],
                "player": [round(v, 1) for v in player_radar],
            },
        }

    def _explain_entries(
        self,
        entries: list[dict],
        internal_stats: dict[str, float],
        row: pd.Series,
        kind: str,
    ) -> list[dict]:
        imputed = self._imputed.get((str(row["player_name"]), str(row["season"])), frozenset())
        out = []
        for e in entries:
            col = e["feature"]
            user_disp = self._z_to_display(col, e["user_z"])
            plyr_disp = self._z_to_display(col, e["player_z"])
            diff_abs = abs(e["user_z"] - e["player_z"])

            # Match-quality class (ίδια thresholds με το Streamlit UI)
            if kind == "match":
                quality = "match" if diff_abs < 0.4 else "close" if diff_abs < 1.0 else "far"
            else:
                quality = "close" if diff_abs < 1.5 else "far"

            u_pct = (
                self._user_percentile(col, internal_stats[col])
                if col in internal_stats
                else self._user_percentile(col, float(self.scaler.mean_[FEATURE_COLS.index(col)]))
            )
            out.append({
                "feature":       col,
                "label":         DISPLAY_LABELS.get(col, col),
                # Είχε αυτό το row πραγματικά δεδομένα, ή είναι group-median
                # imputed; Χωρίς αυτό το breakdown δείχνει imputed αριθμό σαν
                # μετρημένο — με fit bar — ενώ το availability masking τον έχει
                # ήδη αποκλείσει από το distance. Το row-level coverage λέει
                # "50%" αλλά όχι *ποιο* 50%.
                "available":     col not in imputed,
                "user_value":    round(user_disp, 3),
                "player_value":  round(plyr_disp, 3),
                "user_display":  format_display(col, user_disp),
                "player_display": format_display(col, plyr_disp),
                "user_pct":      round(float(u_pct), 0),
                "player_pct":    round(float(row.get(f"pct_{col}", 50.0)), 0),
                "diff":          round(float(diff_abs), 2),
                "quality":       quality,
            })
        return out

    # ── /classify ──────────────────────────────────────────────────────────────
    def classify_player(self, player_name: str, season: str | None) -> dict | None:
        """
        Βρίσκει τον παίκτη (case-insensitive substring) και επιστρέφει archetype +
        active traits + trait scores. Αν δοθεί season → ακριβής σεζόν, αλλιώς η
        σεζόν με τα περισσότερα active traits (πιο "χαρακτηριστική").
        """
        df = self.df
        name_mask = df["_name_fold"].str.contains(_ascii_fold(player_name.strip()), na=False, regex=False)
        cand = df[name_mask]
        if cand.empty:
            return None

        if season:
            cand = cand[cand["season"] == season]
            if cand.empty:
                return None
            best = cand.iloc[0]
        else:
            # Σεζόν με τα περισσότερα active traits (fallback: πρώτη)
            n_traits = cand["active_traits"].apply(lambda t: len(t) if isinstance(t, list) else 0)
            best = cand.loc[n_traits.idxmax()]

        trait_scores = {
            t: round(float(best[f"score_{t}"]), 3)
            for t in TRAITS
            if f"score_{t}" in best.index and pd.notna(best[f"score_{t}"])
        }
        # Ταξινόμηση κατά score φθίνουσα
        trait_scores = dict(sorted(trait_scores.items(), key=lambda kv: kv[1], reverse=True))

        return {
            "player_name":        str(best["player_name"]),
            "season":             str(best["season"]),
            "position_group":     str(best.get("position_group", "—")),
            "compound_archetype": str(best["compound_archetype"]),
            "active_traits":      list(best.get("active_traits", []) or []),
            "trait_scores":       trait_scores,
        }

    def player_names(self, query: str, limit: int = 20) -> list[str]:
        """Autocomplete helper — μοναδικά ονόματα που ταιριάζουν στο query."""
        df = self.df
        mask = df["_name_fold"].str.contains(_ascii_fold(query.strip()), na=False, regex=False)
        names = df.loc[mask, "player_name"].drop_duplicates().head(limit)
        return [str(n) for n in names]

    # ── /stats & /archetypes ───────────────────────────────────────────────────
    def _real_values(self, col: str) -> pd.Series:
        """
        Οι τιμές ενός feature **μόνο** για τα rows που έχουν πραγματικά δεδομένα,
        σε display units.

        Το `avail_<col>` φιλτράρισμα είναι κρίσιμο: τα hustle/defensive features
        είναι group-median imputed για το ~44-56% της βάσης, οπότε χωρίς αυτό η
        κατανομή θα έδειχνε μια τεράστια τεχνητή κορυφή στη median — δηλαδή θα
        έλεγε ψέματα ακριβώς εκεί που το UI υπόσχεται ειλικρίνεια για την κάλυψη.
        """
        df = self.df
        avail = AVAIL_PREFIX + col
        series = df[col] if avail not in df.columns else df.loc[df[avail].astype(bool), col]
        series = series.dropna()
        return series * 100.0 if col in PCT_COLS else series

    def _build_stats_meta(self) -> dict:
        """
        Το /stats payload, εμπλουτισμένο με την πραγματική κατανομή κάθε feature.

        Ο client το χρειάζεται για δύο πράγματα που αλλιώς θα ήταν εικασίες:
          * `dist` — 24-bin histogram πάνω στο [min, max] των RANGES, κανονικοποιημένο
            στο 1.0, ώστε το stat builder να δείχνει πού πέφτει η τιμή του χρήστη
            μέσα στο league.
          * `pcts` — 101 quantiles (p0…p100) σε display units. Με binary search ο
            client βγάζει ακριβές percentile χωρίς round-trip ανά κίνηση του slider.
        Το `n_rows` είναι το πλήθος rows με πραγματικά (μη imputed) δεδομένα.
        """
        stats = stats_metadata()
        for meta in stats:
            col = meta["key"]
            values = self._real_values(col)
            meta["n_rows"] = int(values.size)
            if values.empty:
                meta["dist"] = [0.0] * _DIST_BINS
                meta["pcts"] = [meta["min"]] * 101
                continue

            counts, _ = np.histogram(
                values, bins=_DIST_BINS, range=(meta["min"], meta["max"])
            )
            peak = int(counts.max())
            meta["dist"] = [round(float(c) / peak, 3) for c in counts] if peak else [0.0] * _DIST_BINS
            meta["pcts"] = [
                round(float(q), 4)
                for q in np.percentile(values, np.arange(0, 101))
            ]

        return {
            "stats": stats,
            "traits": ALL_TRAITS,
            "groups": list(GROUPS.keys()),
            "trait_labels": {t: t.replace("_", " ").title() for t in ALL_TRAITS},
        }

    def stats_meta(self) -> dict:
        # Πριν το load() δεν υπάρχει dataset για κατανομές — ο client χειρίζεται
        # το `dist` ως optional, οπότε σερβίρουμε τα σκέτα metadata.
        if self._stats_meta is not None:
            return self._stats_meta
        return {
            "stats": stats_metadata(),
            "traits": ALL_TRAITS,
            "groups": list(GROUPS.keys()),
            "trait_labels": {t: t.replace("_", " ").title() for t in ALL_TRAITS},
        }

    @staticmethod
    def archetypes_meta() -> dict:
        archetypes = [
            {
                "name":      name,
                "traits":    sorted(traits),
                "positions": PRESET_POSITIONS.get(name, []),
            }
            for name, traits in COMPOUNDS.items()
        ]
        return {"count": len(archetypes), "archetypes": archetypes}


def _num(v) -> float | None:
    """numpy/NaN-safe μετατροπή σε float ή None."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(f) else round(f, 1)


# Singleton — φορτώνεται στο startup του app
engine = Engine()
