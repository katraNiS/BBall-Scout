"""
Shared fixtures για το test suite.

Το dataset (data/nba_stats_full.csv) ΔΕΝ είναι στο git — αν λείπει, όλα τα
data-dependent tests κάνουν skip αντί να αποτύχουν, ώστε ένα καθαρό clone να
μη φαίνεται σπασμένο.

Το preprocess() είναι ακριβό (~14k rows → clean → z-score), οπότε τα fixtures
είναι session-scoped: φορτώνεται μία φορά για όλο το suite.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "backend"))

DATASET = ROOT / "data" / "nba_stats_full.csv"

# Η πρώτη σεζόν με αξιόπιστα hustle/tracking data (το 2015-16 είναι corrupt,
# βλ. preprocessing.CORRUPT_HUSTLE_SEASONS).
FIRST_TRACKING_SEASON = 2016


def _require_dataset() -> None:
    if not DATASET.exists():
        pytest.skip(f"dataset missing: {DATASET} (δεν είναι στο git)")


@pytest.fixture(scope="session")
def raw_df():
    """Το ακατέργαστο CSV — πριν από κάθε cleaning/imputation."""
    _require_dataset()
    import pandas as pd

    return pd.read_csv(DATASET)


@pytest.fixture(scope="session")
def clean_df():
    """df_clean μετά από load_and_clean() — MPG filter + imputation."""
    _require_dataset()
    from preprocessing import load_and_clean

    return load_and_clean()


@pytest.fixture(scope="session")
def engine(clean_df):
    """(df_classified, feature_matrix, scaler) — έτοιμο για find_similar()."""
    import archetypes
    from preprocessing import build_feature_matrix

    matrix, scaler = build_feature_matrix(clean_df)
    return archetypes.classify(clean_df), matrix, scaler
