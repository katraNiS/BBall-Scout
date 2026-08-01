"""
Regression guards για τα δύο defensive fixes:

  Fix 1 — invalidation της corrupt 2015-16 hustle σεζόν
  Fix 2 — προσθήκη του def_rating στα FEATURE_COLS

Και τα δύο προέκυψαν από μετρημένη διάγνωση, όχι από υπόθεση· τα tests εδώ
κλειδώνουν το αποτέλεσμα ώστε μια μελλοντική αλλαγή στο pipeline (π.χ. νέο
fetch που ξαναφέρνει τα 2015-16 rows) να το σπάσει θορυβωδώς.
"""

from __future__ import annotations

import numpy as np
import pytest

from conftest import FIRST_TRACKING_SEASON


# ─── Fix 1: corrupt hustle season ─────────────────────────────────────────────

class TestCorruptHustleSeason:
    """
    Το 2015-16 ήταν η σεζόν που το NBA πρωτοξεκίνησε hustle tracking, mid-season.
    Μόνο 147/476 rows είχαν τιμές, και αυτές ήταν partial-season totals — όχι
    per-game averages: 89.8% ακέραιες, max 11.00 deflections/gm (Dwight Howard),
    τη στιγμή που το πραγματικό NBA record είναι ~5.9 (Dyson Daniels 2024-25).
    """

    def test_season_is_flagged_as_corrupt(self):
        from preprocessing import CORRUPT_HUSTLE_SEASONS

        assert "2015-16" in CORRUPT_HUSTLE_SEASONS

    def test_raw_data_still_contains_the_bug(self, raw_df):
        """
        Sanity check του ίδιου του detector: αν αυτό αποτύχει, το dataset άλλαξε
        και το fix μπορεί να μη χρειάζεται πια (ή να χρειάζεται αλλού).
        """
        s = raw_df[raw_df["season"] == "2015-16"]["deflections"].dropna()
        assert len(s) > 0, "το raw CSV δεν έχει καθόλου 2015-16 hustle data"
        assert (s % 1 == 0).mean() > 0.5, "αναμενόταν integer-valued corruption"
        assert s.max() > 6.0, "αναμενόταν out-of-scale τιμές"

    def test_corrupt_values_do_not_survive_cleaning(self, clean_df):
        """Καμία 2015-16 τιμή δεν περνά αυτούσια στο feature space."""
        s = clean_df[clean_df["season"] == "2015-16"]["deflections"]
        assert len(s) > 0, "χάθηκαν όλα τα 2015-16 rows — υπερβολικό filtering"
        # Μετά το invalidation όλα γεμίζουν με position_group medians, άρα ο
        # αριθμός distinct τιμών είναι ≤ πλήθος position groups.
        n_groups = clean_df["position_group"].nunique()
        assert s.nunique() <= n_groups, (
            f"2015-16 deflections έχει {s.nunique()} distinct τιμές, "
            f"αναμένονταν ≤{n_groups} (μόνο group medians)"
        )

    def test_deflections_scale_is_physically_plausible(self, clean_df):
        """
        Το per-game NBA record deflections είναι ~5.9. Οτιδήποτε πάνω από 6.5
        σημαίνει ότι μπήκε ξανά totals-scaled data.
        """
        assert clean_df["deflections"].max() <= 6.5, (
            f"max deflections = {clean_df['deflections'].max()} — out of scale"
        )

    @pytest.mark.parametrize("col", ["deflections", "charges_drawn", "screen_assists"])
    def test_every_integer_spike_season_is_flagged(self, raw_df, col):
        """
        Generic detector για το ίδιο bug σε ΑΛΛΗ σεζόν.

        Ένα per-game rate stat με σχεδόν-όλες ακέραιες τιμές σημαίνει ότι
        αποθηκεύτηκαν totals (ή partial-season sample). Το test δεν απαιτεί να
        μην υπάρχει τέτοια σεζόν — απαιτεί να είναι **δηλωμένη** στο
        CORRUPT_HUSTLE_SEASONS, ώστε το cleaning να την εξουδετερώνει.

        Μετράμε ΜΟΝΟ τις μη-μηδενικές τιμές: το charges_drawn είναι σπάνιο
        event (mean 0.05/gm) και οι μισοί παίκτες έχουν ακριβώς 0.0, που είναι
        μεν ακέραιο αλλά απολύτως φυσιολογικό. Χωρίς αυτό ο detector βγάζει
        false positive στο 2023-24 (54.9% ακέραιες → 0.0% αν αγνοήσεις τα
        μηδενικά). Ο διαχωρισμός είναι καθαρός: 2015-16 → 75-85%, κάθε άλλη
        σεζόν → 0-7%.

        Ελέγχεται το raw CSV επίτηδες: εκεί ζει το bug· στο cleaned df οι τιμές
        έχουν ήδη αντικατασταθεί από group medians.
        """
        from preprocessing import CORRUPT_HUSTLE_SEASONS

        if col not in raw_df.columns:
            pytest.skip(f"{col} λείπει από το dataset")

        real = raw_df[raw_df[col].notna()]
        for season, g in real.groupby("season"):
            nonzero = g[g[col] > 0][col]
            if len(nonzero) < 50:
                continue
            int_share = (nonzero % 1 == 0).mean()
            if int_share >= 0.5:
                assert season in CORRUPT_HUSTLE_SEASONS, (
                    f"{col} @ {season}: {int_share:.1%} ακέραιες τιμές — "
                    f"αδήλωτη corrupt σεζόν (πρόσθεσέ τη στο "
                    f"CORRUPT_HUSTLE_SEASONS)"
                )

    def test_tracking_era_starts_after_the_corrupt_season(self, clean_df, raw_df):
        """Τα εναπομείναντα πραγματικά hustle data ξεκινούν από το 2016-17."""
        merged = clean_df[["player_id", "season"]].merge(
            raw_df[["player_id", "season", "deflections"]],
            on=["player_id", "season"], how="left",
        )
        real = merged[merged["deflections"].notna()]
        real = real[real["season"] != "2015-16"]
        assert real["season"].str[:4].astype(int).min() == FIRST_TRACKING_SEASON


# ─── Fix 2: def_rating ως searchable feature ──────────────────────────────────

class TestDefRatingFeature:
    """
    Το def_rating ήταν ήδη validated signal στον classifier (4 defensive traits
    το χρησιμοποιούν) αλλά έλειπε από τα FEATURE_COLS — δηλαδή ο χρήστης δεν
    μπορούσε να το ζητήσει στο search. Είναι το μόνο defensive feature με
    κάλυψη 100% σε όλες τις σεζόν (1996+).
    """

    def test_is_a_searchable_feature(self):
        from preprocessing import FEATURE_COLS

        assert "def_rating" in FEATURE_COLS

    def test_full_coverage_across_all_seasons(self, clean_df):
        """Σε αντίθεση με το deflections, δεν λείπει από καμία εποχή."""
        assert clean_df["def_rating"].isna().sum() == 0
        per_season = clean_df.groupby("season")["def_rating"].apply(
            lambda s: s.notna().mean()
        )
        assert (per_season == 1.0).all()

    def test_values_are_in_realistic_range(self, clean_df):
        """
        Το raw CSV έχει garbage outliers (min 0.0, max 250.0) από παίκτες με
        ελάχιστα λεπτά· το MPG filter τους καθαρίζει. Αν αυτό αλλάξει, το
        z-space του feature θα διαστρεβλωθεί.
        """
        v = clean_df["def_rating"]
        assert v.min() > 85.0, f"def_rating min = {v.min()} — garbage outlier"
        assert v.max() < 130.0, f"def_rating max = {v.max()} — garbage outlier"

    def test_carries_information_not_already_present(self, clean_df):
        """
        Αξίζει τη θέση του στο feature space μόνο αν δεν είναι σχεδόν-αντίγραφο
        άλλου feature. Χαμηλή |corr| = ανεξάρτητο signal.
        """
        for other in ("stl", "blk", "deflections", "dreb_pct"):
            r = abs(np.corrcoef(clean_df["def_rating"], clean_df[other])[0, 1])
            assert r < 0.35, f"def_rating ~ {other}: |corr| = {r:.2f} (redundant)"

    def test_feature_matrix_includes_it(self, clean_df):
        from preprocessing import FEATURE_COLS, build_feature_matrix

        matrix, scaler = build_feature_matrix(clean_df)
        assert matrix.shape[1] == len(FEATURE_COLS)
        i = FEATURE_COLS.index("def_rating")
        assert abs(matrix[:, i].std() - 1.0) < 0.01, "δεν κανονικοποιήθηκε"


# ─── Phase 1d: matchup-based defensive impact ─────────────────────────────────

class TestDefensiveImpactColumns:
    """
    Το `LeagueDashPtDefend` (Phase 1d) δίνει DFG% — τι σουτάρουν οι αντίπαλοι
    όταν ο παίκτης είναι ο κοντινότερος defender. Δεν είναι ακόμα στα
    FEATURE_COLS, οπότε τα tests κάνουν skip αν λείπουν οι στήλες (παλιό
    dataset) αντί να αποτύχουν.
    """

    COLS = ["d_ovr_diff", "d_fg3_diff", "d_rim_diff"]

    def _require(self, raw_df):
        missing = [c for c in self.COLS if c not in raw_df.columns]
        if missing:
            pytest.skip(f"λείπουν {missing} — τρέξε το Phase 1d του pipeline")

    def test_columns_present_and_populated(self, raw_df):
        self._require(raw_df)
        for c in self.COLS:
            cov = raw_df[c].notna().mean()
            assert cov > 0.35, f"{c}: coverage μόλις {cov:.1%}"

    def test_tracking_era_only(self, raw_df):
        """Τα matchup data ξεκινούν 2013-14· το 2012-13 επιστρέφει 0 rows."""
        self._require(raw_df)
        have = raw_df[raw_df["d_ovr_diff"].notna()]
        assert have["season"].str[:4].astype(int).min() >= 2013

    def test_diff_is_era_stable(self, raw_df):
        """
        Σε αντίθεση με το raw def_rating (corr 0.62 με τη σεζόν), το `_diff`
        είναι ήδη baseline-adjusted → δεν χρειάζεται season-centering. Αν αυτό
        πάψει να ισχύει, το feature θα γίνει εποχή-selector.
        """
        self._require(raw_df)
        have = raw_df[raw_df["d_ovr_diff"].notna()]
        years = have["season"].str[:4].astype(int)
        r = abs(np.corrcoef(have["d_ovr_diff"], years)[0, 1])
        assert r < 0.10, f"corr(d_ovr_diff, year) = {r:.3f} — era leak"

    def test_negative_means_good_defense(self, raw_df):
        """
        Sanity της κατεύθυνσης: το `_diff` = DFG% − baseline, οπότε πρέπει να
        κεντράρει κοντά στο 0 και να έχει και τα δύο πρόσημα.
        """
        self._require(raw_df)
        v = raw_df["d_ovr_diff"].dropna()
        assert abs(v.mean()) < 0.05, f"mean {v.mean():.3f} — αναμενόταν ~0"
        assert (v < 0).any() and (v > 0).any()


# ─── Threshold health ─────────────────────────────────────────────────────────

class TestTraitThresholdHealth:
    """
    Guard για το `TRAIT_THRESHOLD`: το macro-F1 του validation set κορυφώνεται
    στο 0.9, αλλά εκεί το 32% του dataset μένει "Unclassified". Τα tests εδώ
    κλειδώνουν την usability πλευρά, που το macro-F1 δεν βλέπει.
    """

    def test_most_players_get_an_archetype(self, clean_df):
        import archetypes

        res = archetypes.classify(clean_df)
        uncl = (res["compound_archetype"] == "Unclassified").mean()
        assert uncl < 0.20, (
            f"{uncl:.1%} Unclassified — πολύ υψηλό TRAIT_THRESHOLD "
            f"(τρέχον: {archetypes.TRAIT_THRESHOLD})"
        )

    def test_archetype_vocabulary_stays_usable(self, clean_df):
        """Ένα υψηλό threshold σβήνει ολόκληρα archetypes από τη χρήση."""
        import archetypes

        res = archetypes.classify(clean_df)
        used = res["compound_archetype"].isin(archetypes.COMPOUNDS.keys())
        n_used = res.loc[used, "compound_archetype"].nunique()
        assert n_used >= 34, f"μόνο {n_used}/{len(archetypes.COMPOUNDS)} presets σε χρήση"

    def test_players_get_a_meaningful_number_of_traits(self, clean_df):
        import archetypes

        res = archetypes.classify(clean_df)
        mean_traits = res["active_traits"].apply(len).mean()
        assert 2.0 < mean_traits < 3.5, (
            f"{mean_traits:.2f} traits/παίκτη — πολύ χαμηλό threshold δίνει "
            f"θόρυβο, πολύ υψηλό αφήνει τους παίκτες χωρίς περιγραφή"
        )


# ─── Metadata συνέπεια ────────────────────────────────────────────────────────

class TestMetadataConsistency:
    """
    Guard για ΚΑΘΕ μελλοντική προσθήκη feature, όχι μόνο για το def_rating:
    ένα feature χωρίς metadata δεν εμφανίζεται στο stat builder, οπότε ο χρήστης
    δεν μπορεί να το ζητήσει — σιωπηλή αποτυχία.
    """

    def test_backend_metadata_covers_every_feature(self):
        import metadata
        from preprocessing import FEATURE_COLS

        grouped = {c for cols in metadata.GROUPS.values() for c in cols}
        for col in FEATURE_COLS:
            assert col in metadata.DISPLAY_LABELS, f"{col}: λείπει label"
            assert col in metadata.FORMAT, f"{col}: λείπει format"
            assert col in metadata.RANGES, f"{col}: λείπει range"
            assert col in grouped, f"{col}: δεν ανήκει σε κανένα GROUP"

    def test_no_orphan_metadata_entries(self):
        """Το αντίστροφο: metadata για feature που δεν υπάρχει πια."""
        import metadata
        from preprocessing import FEATURE_COLS

        grouped = {c for cols in metadata.GROUPS.values() for c in cols}
        assert grouped <= set(FEATURE_COLS), (
            f"orphan entries: {grouped - set(FEATURE_COLS)}"
        )

    def test_ranges_actually_contain_the_data(self, clean_df):
        """
        Ένα range που δεν καλύπτει τα πραγματικά δεδομένα σημαίνει ότι ο χρήστης
        δεν μπορεί να στοχεύσει υπαρκτούς παίκτες. Ελέγχουμε σε display units.
        """
        import metadata
        from preprocessing import FEATURE_COLS

        for col in FEATURE_COLS:
            lo, hi, _ = metadata.RANGES[col]
            q05 = metadata.to_display(col, float(clean_df[col].quantile(0.05)))
            q95 = metadata.to_display(col, float(clean_df[col].quantile(0.95)))
            assert lo <= q05, f"{col}: range min {lo} > 5th pct {q05:.1f}"
            assert hi >= q95, f"{col}: range max {hi} < 95th pct {q95:.1f}"

    def test_stats_endpoint_payload_includes_def_rating(self):
        import metadata

        keys = [s["key"] for s in metadata.stats_metadata()]
        assert "def_rating" in keys
        assert len(keys) == len(set(keys)), "διπλότυπα keys στο /stats"

    def test_streamlit_legacy_ui_stays_in_sync(self):
        """
        Το app/streamlit_app.py κρατά δικά του duplicate dicts (legacy). Αν
        αποκλίνουν, το legacy UI χάνει σιωπηλά features.
        """
        import importlib.util

        from conftest import ROOT
        from preprocessing import FEATURE_COLS

        spec = importlib.util.find_spec("streamlit")
        if spec is None:
            pytest.skip("streamlit δεν είναι εγκατεστημένο")

        src = (ROOT / "app" / "streamlit_app.py").read_text(encoding="utf-8")
        for col in FEATURE_COLS:
            assert f'"{col}"' in src, f"{col}: λείπει από το legacy Streamlit UI"
