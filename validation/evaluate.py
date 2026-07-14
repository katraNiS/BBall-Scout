"""
Metrics του classifier σε ένα threshold: per-trait precision/recall/F1,
macro-F1, archetype top-1 accuracy, + λίστες misclassifications.

Σχεδιαστικές αποφάσεις:
  - Τα trait SCORES είναι threshold-independent → υπολογίζονται μία φορά
    (compute_trait_scores) και το evaluate() απλώς ξανα-κατωφλιώνει. Φθηνό sweep.
  - Structural miss vs threshold miss: αν ένα expected trait είναι position-
    ineligible (score = NaN), ΔΕΝ μετριέται ως FN — δεν φταίει το threshold αλλά
    το design (π.χ. lead_playmaker δεν είναι eligible για forwards → "Point Forward"
    δεν μπορεί ποτέ να ανάψει σε forward). Καταγράφεται χωριστά ως structural_miss.
  - Negatives = κάθε eligible trait εκτός του expected set, μείον το `ignore`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from archetypes import COMPOUNDS, TRAITS, _label_archetype

TRAIT_NAMES = list(TRAITS.keys())


@dataclass
class TraitMetric:
    trait: str
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0

    @property
    def support(self) -> int:          # πόσοι παίκτες ΕΠΡΕΠΕ να έχουν το trait
        return self.tp + self.fn

    @property
    def precision(self) -> float:
        d = self.tp + self.fp
        return self.tp / d if d else float("nan")

    @property
    def recall(self) -> float:
        d = self.tp + self.fn
        return self.tp / d if d else float("nan")

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        if p != p or r != r or (p + r) == 0:   # NaN ή μηδέν
            return float("nan")
        return 2 * p * r / (p + r)


@dataclass
class EvalResult:
    threshold: float
    traits: dict[str, TraitMetric]
    structural_misses: list[tuple[str, str]] = field(default_factory=list)  # (player, trait)
    archetype_correct: int = 0
    archetype_total: int = 0
    misclassified: list[tuple[str, str, str]] = field(default_factory=list)  # (player, expected, got)

    @property
    def macro_f1(self) -> float:
        f1s = [m.f1 for m in self.traits.values() if m.support > 0 and m.f1 == m.f1]
        return sum(f1s) / len(f1s) if f1s else float("nan")

    @property
    def archetype_accuracy(self) -> float:
        return self.archetype_correct / self.archetype_total if self.archetype_total else float("nan")


def _active_row(scored_row: pd.Series, threshold: float) -> pd.Series:
    """Row-copy με active_<trait> booleans στο δοσμένο threshold (για _label_archetype)."""
    row = scored_row.copy()
    for t in TRAIT_NAMES:
        s = scored_row.get(f"score_{t}")
        row[f"active_{t}"] = bool(pd.notna(s) and s >= threshold)
    return row


def evaluate(
    scored_df: pd.DataFrame,
    resolved: list[tuple],     # [(PlayerLabel, row_index), ...]
    threshold: float,
) -> EvalResult:
    metrics = {t: TraitMetric(t) for t in TRAIT_NAMES}
    res = EvalResult(threshold=threshold, traits=metrics)

    for lab, idx in resolved:
        row = scored_df.loc[idx]
        expected = set(COMPOUNDS[lab.archetype])

        for t in TRAIT_NAMES:
            if t in lab.ignore:
                continue
            s = row.get(f"score_{t}")
            exp = t in expected
            if pd.isna(s):                     # position-ineligible → structural, όχι threshold
                if exp:
                    res.structural_misses.append((lab.name, t))
                continue
            pred = s >= threshold
            m = metrics[t]
            if   exp and pred:     m.tp += 1
            elif exp and not pred: m.fn += 1
            elif not exp and pred: m.fp += 1
            else:                  m.tn += 1

        # Archetype top-1
        pred_arch = _label_archetype(_active_row(row, threshold), TRAIT_NAMES)
        res.archetype_total += 1
        if pred_arch == lab.archetype or pred_arch in lab.accept_also:
            res.archetype_correct += 1
        else:
            res.misclassified.append((lab.name, lab.archetype, pred_arch))

    return res
