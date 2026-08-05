"""
Guards για το preset/trait design του classifier.

Δύο κατηγορίες προβλημάτων που δεν φαίνονται στο macro-F1:

  1. Preset που δεν εμφανίζεται ΠΟΤΕ — υπάρχει στο `/archetypes` endpoint και
     στο ARCHETYPES.md, αλλά κανένας παίκτης δεν το παίρνει. Νεκρό vocabulary.
  2. Trait signals με λάθος κατεύθυνση — ανταμείβουν τα χαρακτηριστικά των
     λάθος παικτών.
"""

from __future__ import annotations

import pytest


class TestPresetReachability:
    """
    Το `_label_archetype()` κρατά το preset με score (pos_ok, trait_count) και
    λύνει τις ισοπαλίες με το dict ordering. Ένα preset μπορεί έτσι να γίνει
    δομικά απρόσιτο — δεν το πιάνει καμία μετρική ακρίβειας.
    """

    def test_no_preset_is_completely_unreachable(self, clean_df):
        import archetypes

        res = archetypes.classify(clean_df)
        counts = res["compound_archetype"].value_counts()
        dead = [p for p in archetypes.COMPOUNDS if counts.get(p, 0) == 0]
        assert not dead, (
            f"{len(dead)} preset(s) δεν εμφανίζονται ποτέ σε {len(clean_df)} rows: "
            f"{dead}. Ελέγξτε subset σχέσεις και dict ordering."
        )

    def test_three_and_d_wing_precedes_guard(self):
        """
        Έχουν και τα δύο 2 traits, οπότε για G-F ισοπαλούν και αποφασίζει η
        σειρά στο dict. Με το Guard πρώτο, το Wing ήταν 0/8382 και 21 G-F wings
        έπαιρναν "Guard" label.
        """
        import archetypes

        keys = list(archetypes.COMPOUNDS)
        assert keys.index("3-and-D Wing") < keys.index("3-and-D Guard")

    def test_wing_preset_not_given_to_pure_guards(self, clean_df):
        """Το position gate πρέπει να προστατεύει τους καθαρούς guards."""
        import archetypes

        res = archetypes.classify(clean_df)
        wings = res[res["compound_archetype"] == "3-and-D Wing"]
        assert len(wings) > 0
        allowed = archetypes.PRESET_POSITIONS["3-and-D Wing"]
        assert wings["position_group"].isin(allowed).all()
        assert "G" not in allowed, "το Wing preset δεν πρέπει να δέχεται καθαρούς guards"

    def test_preset_count_is_stable(self):
        """Η αναδιάταξη δεν επιτρέπεται να χάσει ή να διπλασιάσει preset."""
        import archetypes

        assert len(archetypes.COMPOUNDS) == 36
        assert len(set(archetypes.COMPOUNDS)) == 36


class TestWingDefenderSignalDirection:
    """
    Το `versatile_wing_defender` είχε ΘΕΤΙΚΑ weights σε reb_pct/height_cm,
    με τη λογική «ο wing defender είναι ψηλός και μαζεύει». Μέσα όμως στο
    eligible pool (G-F/F/F-C) αυτά ξεχωρίζουν BIGS, όχι καλούς wing defenders:
    6 από τα 8 false positives ήταν F-C (Embiid, KAT, Hartenstein, AD, Bam, JJJ).
    Μετρημένο Cohen's d expected vs FP: reb_pct -1.80, screen_assists -1.59,
    height -1.39 — όλα αντίθετα από την αρχική υπόθεση.
    """

    @pytest.mark.parametrize("col", ["reb_pct", "height_cm", "screen_assists"])
    def test_size_markers_are_penalised(self, col):
        import archetypes

        sigs = {s.col: s.weight for s in
                archetypes.TRAITS["versatile_wing_defender"].signals}
        assert col in sigs, f"{col}: λείπει από τα signals"
        assert sigs[col] < 0, (
            f"{col} έχει weight {sigs[col]:+.1f} — θετικό σημαίνει ότι το trait "
            f"ανταμείβει το μέγεθος, δηλαδή διαλέγει bigs αντί για wings"
        )

    def test_deflections_remains_the_primary_signal(self):
        """
        Μετρημένο: αφαίρεση του deflections ρίχνει το recall σε 0.05. Είναι το
        μόνο individual defensive signal στο dataset — αν κάποιος το μειώσει
        δραστικά, το trait παύει να λειτουργεί.
        """
        import archetypes

        sigs = {s.col: s.weight for s in
                archetypes.TRAITS["versatile_wing_defender"].signals}
        assert sigs.get("deflections", 0) >= 2.0

    def test_precision_does_not_regress(self, clean_df):
        """
        Κλειδώνει το κέρδος: precision 0.529 -> 0.692 στα 72 labeled παίκτες.
        Κατώφλι χαλαρό (0.60) ώστε να πιάνει regression, όχι θόρυβο.
        """
        import sys
        from pathlib import Path

        root = Path(__file__).parent.parent
        sys.path.insert(0, str(root / "validation"))
        try:
            from evaluate import evaluate
            from labels import LABELS
            from matching import build_resolver
        except ImportError:
            pytest.skip("validation harness μη διαθέσιμο")

        import archetypes

        scored = archetypes.compute_trait_scores(clean_df)
        resolve = build_resolver(scored)
        resolved = [(l, resolve(l.name, l.season)) for l in LABELS
                    if resolve(l.name, l.season) is not None]
        r = evaluate(scored, resolved, archetypes.TRAIT_THRESHOLD)
        m = r.traits["versatile_wing_defender"]
        assert m.precision >= 0.60, f"precision έπεσε σε {m.precision:.3f}"
