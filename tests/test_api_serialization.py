"""
Serialization layer (`backend/engine.py`) — τι *δείχνει* το API, όχι τι υπολογίζει
το `src/`.

Γιατί ξεχωριστό αρχείο: τα δύο ευρήματα που κλειδώνει εδώ είναι ακριβώς το είδος
που δεν πιάνεται από τα engine tests, επειδή το engine υπολογίζει σωστά — το
serialization είναι που παρουσίαζε λάθος πράγματα:

  1. Το `explain_match()` γεμίζει matching/diverging μέχρι top_n=4 με argsort πάνω
     σε ΟΛΑ τα features· τα unspecified πάνε τελευταία αλλά δεν κόβονται. Με 2-3
     ζητούμενα stats οι λίστες γέμιζαν με features που ο χρήστης δεν ζήτησε (και
     που δεν βάρυναν καθόλου στο distance) και επικαλύπτονταν μεταξύ τους.
  2. Το `find_similar()` επιστρέφει προβολή μόνο των result_cols — οι στήλες
     `avail_*` δεν επιβιώνουν. Το per-stat availability πρέπει να έρθει από
     ξεχωριστό index, αλλιώς κάθε imputed τιμή παρουσιάζεται ως μετρημένη.
"""

from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def api_engine(clean_df):  # noqa: ARG001 — εξαρτάται μόνο για το dataset skip
    from engine import engine as singleton

    if not singleton.ready:
        singleton.load()
    return singleton


class TestExplanationScope:
    """Το breakdown δείχνει μόνο ό,τι πραγματικά μέτρησε στο distance."""

    def test_only_requested_features_appear(self, api_engine):
        # Λιγότερα stats από το top_n=4 του explain_match — εδώ εμφανιζόταν το bug.
        stats = {"pts": 22.5, "ts_pct": 57.5}
        payload = api_engine.similar(
            stats=stats, weights=None, top_n=5, active_traits=None, season_range="2018-2025"
        )

        assert payload["results"], "χωρίς αποτελέσματα δεν ελέγχεται τίποτα"
        for r in payload["results"]:
            features = [e["feature"] for e in r["matching"] + r["diverging"]]
            assert set(features) <= set(stats), (
                f"{r['player_name']}: το breakdown δείχνει feature που δεν ζητήθηκε — "
                f"{set(features) - set(stats)}"
            )

    def test_no_duplicate_features_across_lists(self, api_engine):
        stats = {"pts": 22.5, "ts_pct": 57.5, "deflections": 3.0}
        payload = api_engine.similar(
            stats=stats, weights=None, top_n=5, active_traits=None, season_range="2018-2025"
        )

        for r in payload["results"]:
            features = [e["feature"] for e in r["matching"] + r["diverging"]]
            assert len(features) == len(set(features)), (
                f"{r['player_name']}: διπλότυπο feature στο breakdown — {features}"
            )


class TestPerStatAvailability:
    """
    Το `available` flag πρέπει να συμφωνεί με το row-level `coverage`: αν το
    coverage λέει ότι μισό από το ζητούμενο βάρος έλειπε, το breakdown πρέπει να
    δείχνει *ποιο* μισό.
    """

    def test_pre_tracking_seasons_report_missing_hustle(self, api_engine):
        payload = api_engine.similar(
            stats={"pts": 22.5, "deflections": 3.0},
            weights=None,
            top_n=5,
            active_traits=None,
            season_range="1998-2012",  # πριν από κάθε hustle tracking
        )

        assert payload["results"]
        for r in payload["results"]:
            by_feature = {e["feature"]: e for e in r["matching"] + r["diverging"]}
            assert by_feature["deflections"]["available"] is False, (
                f"{r['player_name']} {r['season']}: deflections σημειώνεται ως διαθέσιμο "
                "ενώ δεν καταγραφόταν"
            )
            assert by_feature["pts"]["available"] is True

    def test_tracking_era_reports_everything_available(self, api_engine):
        payload = api_engine.similar(
            stats={"pts": 22.5, "deflections": 3.0},
            weights=None,
            top_n=5,
            active_traits=None,
            season_range="2018-2025",
        )

        assert payload["results"]
        for r in payload["results"]:
            for e in r["matching"] + r["diverging"]:
                assert e["available"] is True, (
                    f"{r['player_name']} {r['season']}: {e['feature']} σημειώνεται ως ελλιπές "
                    "μέσα στην tracking era"
                )

    def test_available_flags_agree_with_coverage(self, api_engine):
        """
        Ο έλεγχος που πιάνει τη σιωπηλή αποσύνδεση: το ποσοστό των διαθέσιμων
        stats πρέπει να ταιριάζει με το coverage. Με ίσα βάρη τα δύο είναι το ίδιο
        κλάσμα — αν αποκλίνουν, το ένα από τα δύο λέει ψέματα.
        """
        stats = {"pts": 22.5, "deflections": 3.0}
        payload = api_engine.similar(
            stats=stats, weights=None, top_n=8, active_traits=None, season_range="1998-2016"
        )

        assert payload["results"]
        for r in payload["results"]:
            entries = r["matching"] + r["diverging"]
            assert len(entries) == len(stats)
            share = sum(e["available"] for e in entries) / len(entries)
            assert share == pytest.approx(r["coverage"], abs=0.01), (
                f"{r['player_name']} {r['season']}: available share {share:.2f} vs "
                f"coverage {r['coverage']:.2f}"
            )


class TestStatsDistributions:
    """Το /stats σερβίρει πραγματικές κατανομές — ο builder τις ζωγραφίζει."""

    def test_every_feature_carries_a_distribution(self, api_engine):
        from preprocessing import FEATURE_COLS

        stats = {s["key"]: s for s in api_engine.stats_meta()["stats"]}
        for col in FEATURE_COLS:
            meta = stats[col]
            assert len(meta["dist"]) == 24, f"{col}: λάθος πλήθος bins"
            assert len(meta["pcts"]) == 101, f"{col}: λάθος πλήθος quantiles"
            assert meta["n_rows"] > 0, f"{col}: μηδέν rows με πραγματικά δεδομένα"

    def test_quantiles_are_monotonic(self, api_engine):
        """Μη μονότονα quantiles σπάνε το binary search του percentileOf()."""
        for meta in api_engine.stats_meta()["stats"]:
            q = meta["pcts"]
            assert all(a <= b for a, b in zip(q, q[1:])), f"{meta['key']}: μη μονότονα quantiles"

    def test_imputed_rows_are_excluded_from_distributions(self, api_engine):
        """
        Τα hustle/defensive features είναι group-median imputed για μεγάλο μέρος
        της βάσης. Αν έμπαιναν στο histogram θα έφτιαχναν τεχνητή κορυφή στη
        median — δηλαδή ψέμα ακριβώς εκεί που το UI υπόσχεται ειλικρίνεια.
        """
        stats = {s["key"]: s for s in api_engine.stats_meta()["stats"]}
        full = max(s["n_rows"] for s in stats.values())

        assert stats["deflections"]["n_rows"] < full * 0.7, (
            "το deflections δεν φαίνεται να αποκλείει τα imputed rows"
        )
        assert stats["pts"]["n_rows"] == full, "το pts δεν έχει πλήρη κάλυψη"
