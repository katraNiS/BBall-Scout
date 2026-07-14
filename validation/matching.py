"""
Accent/apostrophe/suffix-tolerant αντιστοίχιση ονόματος → row στο dataset.

Το CSV αποθηκεύει ονόματα με τόνους ("Nikola Jokić"), αποστρόφους ("De'Aaron Fox")
και suffixes ("Jaren Jackson Jr."). Ο resolver κανονικοποιεί και τις δύο πλευρές
ώστε "de aaron fox" να ταιριάζει ανεξάρτητα από στίξη/τόνους.
"""

from __future__ import annotations

import re
import unicodedata

import pandas as pd


def normalize_name(name: str) -> str:
    """
    NFKD → drop combining marks (τόνοι) → lowercase → μη-alphanumeric σε κενό →
    collapse spaces. "De'Aaron Fox" και "De Aaron Fox" → "de aaron fox".
    """
    decomposed = unicodedata.normalize("NFKD", str(name))
    ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
    lowered = ascii_only.lower()
    cleaned = re.sub(r"[^a-z0-9]+", " ", lowered)
    return cleaned.strip()


def build_resolver(df: pd.DataFrame):
    """
    Επιστρέφει resolve(name, season=None) → index στο df ή None.

    - Χτίζει normalized-name → [indices] map μία φορά.
    - season=None → κρατά τη ΝΕΟΤΕΡΗ διαθέσιμη σεζόν (max season string).
    - season="2016-17" → ακριβής σεζόν· αν λείπει, επιστρέφει None.
    """
    norm_to_rows: dict[str, list[int]] = {}
    for idx, raw in df["player_name"].items():
        if pd.isna(raw):
            continue
        norm_to_rows.setdefault(normalize_name(raw), []).append(idx)

    def resolve(name: str, season: str | None = None) -> int | None:
        rows = norm_to_rows.get(normalize_name(name))
        if not rows:
            return None
        sub = df.loc[rows]
        if season is not None:
            match = sub[sub["season"] == season]
            if match.empty:
                return None
            return int(match.index[0])
        # Νεότερη σεζόν (season strings ταξινομούνται λεξικογραφικά σωστά: "2016-17")
        return int(sub.sort_values("season").index[-1])

    return resolve
