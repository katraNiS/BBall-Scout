"""
Behavioural tests: τι επιστρέφει πραγματικά η similarity engine σε defensive
queries.

Τα thresholds εδώ ΔΕΝ είναι μαντεψιά — προέρχονται από το
`validation/defense_impact.py`, και είναι σκόπιμα χαλαρά ώστε να πιάνουν
κατάρρευση συμπεριφοράς, όχι φυσιολογικό θόρυβο ranking.
"""

from __future__ import annotations

import numpy as np
import pytest

from conftest import FIRST_TRACKING_SEASON

TOP_N = 25


def _pre_tracking_share(res) -> float:
    return float((res["season"].str[:4].astype(int) < FIRST_TRACKING_SEASON).mean())


def _lookup(df, res, col) -> np.ndarray:
    """Τιμές του `col` για τα rows που επέστρεψε το find_similar."""
    ids = set(zip(res["player_name"], res["season"]))
    hit = [(n, s) in ids for n, s in zip(df["player_name"], df["season"])]
    return df.loc[hit, col].to_numpy()


@pytest.fixture(scope="module")
def search(engine):
    from similarity import find_similar

    df, matrix, scaler = engine

    def _run(user_stats, weights=None, top_n=TOP_N):
        return find_similar(user_stats, df, matrix, scaler,
                            weights=weights, top_n=top_n)

    return _run


# ─── Season-centering του def_rating ──────────────────────────────────────────

class TestSeasonCentering:
    """
    Το raw def_rating ανέβηκε league-wide από ~99.7 (1998-99) σε ~113.1
    (2023-24) λόγω pace/3pt revolution. Χωρίς centering, το feature λειτουργεί
    ως ΕΠΟΧΗ-selector αντί για defense-selector.
    """

    def test_era_dependence_is_removed(self, clean_df):
        years = clean_df["season"].str[:4].astype(int)
        r = abs(np.corrcoef(clean_df["def_rating"], years)[0, 1])
        assert r < 0.05, f"corr(def_rating, year) = {r:.3f} — era leak"

    def test_raw_column_still_shows_the_problem(self, clean_df):
        """Ο detector: αν αυτό πάψει να ισχύει, το centering δεν χρειάζεται."""
        years = clean_df["season"].str[:4].astype(int)
        r = np.corrcoef(clean_df["def_rating_raw"], years)[0, 1]
        assert r > 0.4, f"raw corr = {r:.3f} — αναμενόταν έντονο era drift"

    def test_season_means_are_aligned(self, clean_df):
        means = clean_df.groupby("season")["def_rating"].mean()
        assert (means.max() - means.min()) < 0.01, "οι σεζόν δεν ευθυγραμμίστηκαν"

    def test_player_level_signal_is_preserved(self, clean_df):
        """
        Το centering πρέπει να αφαιρεί ΜΟΝΟ το era offset. Αν έπεφτε και το
        within-season std, θα είχαμε χάσει διακριτική ικανότητα.
        """
        within = clean_df.groupby("season")["def_rating_raw"].std().mean()
        after = clean_df["def_rating"].std()
        assert abs(after - within) < 0.3, (
            f"within-season std {within:.2f} → overall {after:.2f}: χάθηκε signal"
        )

    def test_units_are_unchanged(self, clean_df):
        """
        Επιλέχθηκε re-centering αντί για z-score ακριβώς ώστε να μείνουν οι
        μονάδες σε "def rating points" και να μη σπάσει το stat builder.
        """
        v = clean_df["def_rating"]
        assert 100.0 < v.mean() < 112.0
        assert 85.0 < v.min() and v.max() < 130.0


# ─── Era balance ──────────────────────────────────────────────────────────────

class TestEraBalance:

    @pytest.mark.parametrize("query", [
        {"fg3a": 5.5, "fg3_pct": 0.38, "stl": 1.3, "def_rating": 103.0},
        {"stl": 1.8, "def_rating": 101.0, "usg_pct": 0.14},
        {"def_rating": 100.0, "stl": 1.4, "blk": 1.0},
    ])
    def test_full_coverage_defensive_query_spans_eras(self, search, query):
        """
        Το κύριο σύμπτωμα που διορθώθηκε: defensive queries επέστρεφαν 0%
        pre-tracking παίκτες. Μετρημένο εύρος τώρα: 48–84%.
        """
        share = _pre_tracking_share(search(query))
        assert share > 0.25, (
            f"μόνο {share:.0%} pre-{FIRST_TRACKING_SEASON} — era collapse"
        )

    def test_offensive_control_is_unaffected(self, search):
        """Τα offensive queries δεν είχαν ποτέ το πρόβλημα — ας μείνει έτσι."""
        share = _pre_tracking_share(search({"pts": 20.0, "fta": 6.5, "usg_pct": 0.28}))
        assert share > 0.25

    @pytest.mark.parametrize("query", [
        {"fg3a": 5.5, "fg3_pct": 0.38, "stl": 1.3, "deflections": 3.0},
        {"stl": 1.8, "deflections": 3.8, "usg_pct": 0.14},
        {"blk": 1.8, "deflections": 2.6, "dreb_pct": 0.22},
    ])
    def test_tracking_only_query_no_longer_collapses(self, search, query):
        """
        Ήταν 0% πριν το availability-aware masking: τα imputed rows (56% της
        βάσης) κάθονταν σε σταθερή απόσταση τιμωρίας. Τώρα το distance
        υπολογίζεται μόνο στις διαστάσεις με πραγματικά δεδομένα.
        """
        share = _pre_tracking_share(search(query))
        assert share > 0.15, f"μόνο {share:.0%} pre-{FIRST_TRACKING_SEASON}"


# ─── Corrupt-season contamination ─────────────────────────────────────────────

class TestCorruptSeasonContamination:

    def test_2015_16_does_not_dominate_deflection_queries(self, search):
        """
        Πριν το fix, ένα high-deflections query επέστρεφε 5/10 rows από το
        2015-16 — με Curry, Harden και Butler ως «elite stoppers», επειδή οι
        partial-season τιμές τους έφταναν z ≈ +18.
        """
        res = search({"deflections": 4.5, "stl": 1.5},
                     weights={"deflections": 4}, top_n=10)
        n = int((res["season"] == "2015-16").sum())
        assert n <= 1, f"{n}/10 αποτελέσματα από την corrupt σεζόν"

    def test_top_defensive_matches_are_plausible(self, search):
        """
        Smoke test με ονόματα: ένα high-deflections query πρέπει να επιστρέφει
        αναγνωρισμένους αμυντικούς. Χαλαρό κατώφλι — ελέγχει ότι δεν έχει
        ξεφύγει τελείως, όχι το ακριβές ranking.
        """
        res = search({"deflections": 4.0, "stl": 1.6}, top_n=15)
        known = {
            "Herbert Jones", "Robert Covington", "Draymond Green", "Jrue Holiday",
            "Dejounte Murray", "Paul George", "Alex Caruso", "Matisse Thybulle",
            "Marcus Smart", "OG Anunoby", "Kawhi Leonard", "Ricky Rubio",
            "Fred VanVleet", "T.J. McConnell", "Ausar Thompson", "Dyson Daniels",
            "Kelly Oubre Jr.", "Mikal Bridges", "Jimmy Butler III", "John Wall",
        }
        hits = known & set(res["player_name"])
        assert len(hits) >= 3, f"μόνο {len(hits)} αναγνωρίσιμοι αμυντικοί: {hits}"


# ─── Discriminative power ─────────────────────────────────────────────────────

class TestDefRatingIsUsable:

    def test_query_target_is_actually_hit(self, engine, search):
        """
        Ζητώντας def_rating = X, ο μέσος όρος των αποτελεσμάτων πρέπει να είναι
        κοντά στο X. Αν όχι, το feature είναι διακοσμητικό.
        """
        df, _, _ = engine
        for target in (98.0, 102.0, 106.0, 110.0):
            res = search({"def_rating": target, "stl": 1.2},
                         weights={"def_rating": 3})
            got = float(_lookup(df, res, "def_rating").mean())
            assert abs(got - target) < 1.5, (
                f"ζητήθηκε def_rating {target}, βρέθηκε {got:.1f}"
            )

    def test_response_is_monotonic(self, engine, search):
        """Αυστηρότερο: χαμηλότερο target → σταθερά καλύτεροι αμυντικοί."""
        df, _, _ = engine
        got = [
            float(_lookup(df, search({"def_rating": t, "stl": 1.2},
                                     weights={"def_rating": 3}), "def_rating").mean())
            for t in (98.0, 102.0, 106.0, 110.0)
        ]
        assert got == sorted(got), f"μη μονοτονική απόκριση: {got}"

    def test_changes_the_ranking(self, search):
        """
        Δύο queries που διαφέρουν ΜΟΝΟ στο def_rating πρέπει να δίνουν
        διαφορετικά αποτελέσματα — αλλιώς το feature αγνοείται.
        """
        a = search({"stl": 1.5, "def_rating": 99.0}, weights={"def_rating": 3})
        b = search({"stl": 1.5, "def_rating": 113.0}, weights={"def_rating": 3})
        overlap = set(a["player_name"]) & set(b["player_name"])
        assert len(overlap) < TOP_N * 0.5, (
            f"{len(overlap)}/{TOP_N} κοινά — το def_rating δεν επηρεάζει το ranking"
        )

    def test_is_a_valid_api_stat_key(self):
        """Guard: το /similar απορρίπτει keys εκτός FEATURE_COLS."""
        from preprocessing import FEATURE_COLS

        assert "def_rating" in set(FEATURE_COLS)


# ─── Availability-aware masking + confidence discount ─────────────────────────

class TestAvailabilityMasking:
    """
    Το distance υπολογίζεται μόνο στις διαστάσεις που έχουν πραγματικά δεδομένα
    ανά row, και το αποτέλεσμα shrink-άρει προς το population prior ανάλογα με
    το coverage:  sim = sim_pop + coverage^α × (sim_masked − sim_pop)
    """

    def test_availability_matrix_matches_the_tracking_era(self, clean_df):
        from preprocessing import FEATURE_COLS, build_availability_matrix

        avail = build_availability_matrix(clean_df)
        assert avail.shape == (len(clean_df), len(FEATURE_COLS))

        i = FEATURE_COLS.index("deflections")
        years = clean_df["season"].str[:4].astype(int).to_numpy()
        # Πριν το tracking era (και στην corrupt σεζόν) τίποτα δεν είναι διαθέσιμο
        assert not avail[years < FIRST_TRACKING_SEASON, i].any()
        # Μέσα στο tracking era, τα περισσότερα rows έχουν πραγματικά δεδομένα
        assert avail[years >= FIRST_TRACKING_SEASON, i].mean() > 0.9

    def test_non_tracking_features_are_always_available(self, clean_df):
        from preprocessing import FEATURE_COLS, build_availability_matrix

        avail = build_availability_matrix(clean_df)
        for col in ("pts", "def_rating", "stl", "height_cm"):
            assert avail[:, FEATURE_COLS.index(col)].all(), f"{col}: κενά"

    def test_coverage_is_reported(self, search):
        res = search({"stl": 1.8, "deflections": 3.8, "usg_pct": 0.14})
        assert "coverage" in res.columns
        assert ((res["coverage"] > 0) & (res["coverage"] <= 1.0)).all()

    def test_coverage_reflects_missing_dimensions(self, search):
        """
        Query με 3 ισοβαρή stats εκ των οποίων 1 tracking-only: τα pre-2016
        rows πρέπει να έχουν coverage ≈ 2/3, τα υπόλοιπα 1.0.
        """
        res = search({"stl": 1.8, "deflections": 3.8, "usg_pct": 0.14}, top_n=40)
        years = res["season"].str[:4].astype(int)
        pre, post = res[years < FIRST_TRACKING_SEASON], res[years >= FIRST_TRACKING_SEASON]
        if len(pre):
            assert np.allclose(pre["coverage"], 2 / 3, atol=0.01)
        assert np.allclose(post["coverage"], 1.0, atol=0.01)

    def test_no_regression_when_all_data_is_available(self, engine):
        """
        ΚΡΙΣΙΜΟ: coverage = 1 πρέπει να δίνει ΑΚΡΙΒΩΣ το προηγούμενο score.
        Queries χωρίς tracking features δεν επιτρέπεται να αλλάξουν καθόλου.
        """
        import numpy as np
        from similarity import find_similar

        df, matrix, scaler = engine
        all_avail = np.ones_like(matrix, dtype=bool)
        for q in ({"fg3a": 8.0, "fg3_pct": 0.40, "ts_pct": 0.62},
                  {"ast_pct": 0.35, "ast_to": 2.5},
                  {"stl": 1.8, "def_rating": 101.0, "usg_pct": 0.14}):
            a = find_similar(q, df, matrix, scaler, top_n=20)
            b = find_similar(q, df, matrix, scaler, top_n=20, availability=all_avail)
            assert list(a["player_name"]) == list(b["player_name"])
            assert np.allclose(a["similarity"], b["similarity"])

    def test_partial_data_does_not_outrank_full_data(self, search):
        """
        Η υπερδιόρθωση που έπρεπε να αποφύγουμε: χωρίς confidence discount, rows
        με λιγότερες διαστάσεις κρίνονται ευκολότερα και εκτοπίζουν παίκτες με
        πλήρη δεδομένα. Ο κορυφαίος πρέπει να έχει coverage = 1.
        """
        res = search({"stl": 1.8, "deflections": 3.8, "usg_pct": 0.14}, top_n=10)
        assert res.iloc[0]["coverage"] == 1.0, (
            f"#1 έχει coverage {res.iloc[0]['coverage']:.2f} — υπερδιόρθωση"
        )
        top5_full = (res.head(5)["coverage"] == 1.0).sum()
        assert top5_full >= 3, f"μόνο {top5_full}/5 του top-5 έχουν πλήρη δεδομένα"

    def test_zero_coverage_falls_back_to_prior(self, engine):
        """
        Αν ο χρήστης ορίσει ΜΟΝΟ tracking stats, τα pre-2016 rows δεν έχουν
        καμία βάση σύγκρισης → πρέπει να πάρουν το population prior, όχι top
        ranking. «Δεν ξέρουμε» ≠ «ταιριάζει».
        """
        from similarity import find_similar

        df, matrix, scaler = engine
        res = find_similar({"deflections": 4.0}, df, matrix, scaler, top_n=25)
        years = res["season"].str[:4].astype(int)
        assert (years >= FIRST_TRACKING_SEASON).all(), (
            "rows χωρίς κανένα δεδομένο δεν πρέπει να μπαίνουν στο top-N"
        )

    def test_alpha_controls_the_discount(self, engine):
        """Μεγαλύτερο α → αυστηρότερη τιμωρία → λιγότεροι pre-tracking παίκτες."""
        from similarity import find_similar

        df, matrix, scaler = engine
        q = {"stl": 1.8, "deflections": 3.8, "usg_pct": 0.14}
        shares = [
            _pre_tracking_share(
                find_similar(q, df, matrix, scaler, top_n=25, confidence_alpha=a)
            )
            for a in (0.0, 1.0, 3.0)
        ]
        assert shares[0] > shares[1] > shares[2], f"μη μονοτονικό: {shares}"
