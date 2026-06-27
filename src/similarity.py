"""
Similarity engine: βρίσκει τους πιο όμοιους παίκτες για ένα user-defined profile.

Βασική λογική:
  1. Weighted cosine similarity στο normalized feature space
  2. Archetype boost για παίκτες με shared active traits
  3. Explanation ανά match (τι έφερε κοντά, τι διαφέρει)

find_similar() — κεντρική συνάρτηση
explain_match() — per-match explanation
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from preprocessing import FEATURE_COLS


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _weight_array(weights: dict | None) -> np.ndarray:
    """
    Μετατρέπει weights dict σε array aligned με FEATURE_COLS.
    Missing keys → weight 1.0. Αρνητικά/μηδενικά → clamp σε 0.01.
    """
    w = np.ones(len(FEATURE_COLS), dtype=float)
    if weights:
        for i, col in enumerate(FEATURE_COLS):
            if col in weights:
                w[i] = max(float(weights[col]), 0.01)
    return w



def _weighted_similarity(
    user_vec: np.ndarray,
    matrix: np.ndarray,
    weight_arr: np.ndarray,
) -> np.ndarray:
    """
    Weighted L2 similarity μεταξύ user_vec και κάθε row του matrix.

    Χρησιμοποιούμε L2 distance αντί cosine γιατί το scouting tool ζητά
    «βρες παίκτες ΚΟΝΤΑ σε αυτές τις τιμές», όχι «ίδιο proportional profile».
    Cosine τιμωρεί παίκτες με extreme stats σε unspecified dimensions —
    L2 τιμωρεί αυτούς που απέχουν από τις τιμές που ζήτησε ο χρήστης.

    distance_i = sqrt(Σ w_j × (user_j - player_j)²)
    similarity  = 1 / (1 + distance)  →  (0, 1], 1 = τέλεια αντιστοιχία

    Χρησιμοποιούμε 1/(1+d) αντί exp(-d) γιατί τα z-score distances είναι
    φυσικά μεγάλα (sqrt(5 features × 2²) ≈ 4.5), οπότε exp(-4.5) ≈ 0.01
    κάνει όλα τα scores ίδια. Το 1/(1+4.5) = 0.18 δίνει χρήσιμο range.
    """
    diff      = matrix - user_vec          # (n_players, n_features)
    w_diff_sq = (diff ** 2) * weight_arr   # broadcast weights
    distances = np.sqrt(w_diff_sq.sum(axis=1))
    return 1.0 / (1.0 + distances)


def _parse_season_range(seasons: str | None) -> tuple[int | None, int | None]:
    """
    Μετατρέπει "2010-2025" ή "2010" ή None σε (start_year, end_year).
    Το season string "2010-11" → start year 2010.
    """
    if not seasons:
        return None, None
    parts = str(seasons).split("-")
    try:
        if len(parts) == 1:
            y = int(parts[0])
            return y, y
        # "2010-2025" → start=2010, end=2025
        # Αν το δεύτερο μέρος είναι 2-digit (π.χ. "2010-11") θεωρείται season string, όχι range
        if len(parts[1]) <= 2:
            # Μοιάζει με season string "2010-11" — το αντιμετωπίζουμε ως single year
            return int(parts[0]), int(parts[0])
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None, None


# ─── Explanation ──────────────────────────────────────────────────────────────

def explain_match(
    user_vec_raw: np.ndarray,
    player_vec_raw: np.ndarray,
    weights: dict | None = None,
    top_n: int = 4,
) -> dict:
    """
    Εξηγεί γιατί ένας παίκτης ταιριάζει στο user profile.

    Μετράει weighted absolute difference ανά feature:
      - Μικρή διαφορά → το feature "ταίριαξε" (contributing)
      - Μεγάλη διαφορά → το feature "διαφέρει" (diverging)

    Επιστρέφει:
      matching   — [(feature, user_val, player_val), ...] top ομοιότητες
      diverging  — [(feature, user_val, player_val), ...] top διαφορές
    """
    w_arr = _weight_array(weights)

    # Weighted absolute difference ανά feature (στο z-score space)
    diffs = np.abs(user_vec_raw - player_vec_raw) * w_arr

    # Φιλτράρουμε μόνο features που ο χρήστης ΔΕΝ άφησε στο mean (z≠0 για user)
    # Αν o χρήστης δεν όρισε ένα stat, δεν έχει νόημα να το εξηγήσουμε
    user_defined = np.abs(user_vec_raw) > 0.05  # z=0 → population mean → skip

    # Matching: μικρές διαφορές σε user-defined features
    # Unspecified → inf ώστε να βγαίνουν τελευταία
    matching_idx  = np.argsort(np.where(user_defined, diffs, np.inf))[:top_n]
    # Diverging: μεγάλες διαφορές σε user-defined features
    # Unspecified → -inf ώστε με argsort[::-1] να βγαίνουν τελευταία
    diverging_idx = np.argsort(np.where(user_defined, diffs, -np.inf))[::-1][:top_n]

    def make_entries(indices):
        entries = []
        for i in indices:
            if i >= len(FEATURE_COLS):
                continue
            col = FEATURE_COLS[i]
            entries.append({
                "feature":     col,
                "user_z":      round(float(user_vec_raw[i]), 2),
                "player_z":    round(float(player_vec_raw[i]), 2),
                "diff":        round(float(diffs[i]), 2),
                "weight":      round(float(w_arr[i]), 2),
            })
        return entries

    return {
        "matching":  make_entries(matching_idx),
        "diverging": make_entries(diverging_idx),
    }


# ─── Core ─────────────────────────────────────────────────────────────────────

def find_similar(
    user_stats: dict,
    df_clean: pd.DataFrame,
    feature_matrix: np.ndarray,
    scaler: StandardScaler,
    weights: dict | None = None,
    top_n: int = 10,
    active_traits: list[str] | None = None,
    trait_boost: float = 0.004,
    season_range: str | None = None,
) -> pd.DataFrame:
    """
    Βρίσκει τους top_n πιο όμοιους παίκτες.

    Args:
        user_stats:    {"fg3_pct": 0.38, "ast_pct": 25.0, ...}
                       Stats που δεν ορίζονται → population mean (z=0, neutral)
        df_clean:      DataFrame από preprocessing.load_and_clean()
        feature_matrix: z-scored array από preprocessing.build_feature_matrix()
        scaler:        fitted StandardScaler από preprocessing
        weights:       {"fg3_pct": 3, "ast_pct": 2} — default 1 για όλα
        top_n:         αριθμός αποτελεσμάτων
        active_traits: traits που θέλει ο χρήστης (boost, όχι hard filter)
        trait_boost:   bonus score ανά shared trait
        season_range:  "2010-2025" για φιλτράρισμα εποχής (start-end year)

    Returns:
        DataFrame με columns: player_name, season, compound_archetype,
        similarity, boost, final_score, explanation, + original stats
    """
    # ── 1. Μετατροπή user stats σε scaled vector ──────────────────────────────
    # Ξεκινάμε από τα population means (= 0 μετά το z-score scaling)
    user_raw = scaler.mean_.copy()
    for i, col in enumerate(FEATURE_COLS):
        if col in user_stats and user_stats[col] is not None:
            user_raw[i] = float(user_stats[col])

    user_vec = scaler.transform(user_raw.reshape(1, -1)).flatten()

    # Mask των features που ο χρήστης όρισε ρητά.
    # Cosine similarity υπολογίζεται ΜΟΝΟ σε αυτές τις διαστάσεις.
    # Αιτία: cosine κανονικοποιεί τον |player| vector — αν ένας παίκτης έχει
    # extreme τιμές σε unspecified features (π.χ. πολλά deflections ενώ ο χρήστης
    # δεν ρώτησε για άμυνα), ο μεγάλος |player| τον τιμωρεί άδικα.
    # Masked cosine: "βρες παίκτες που ταιριάζουν σε ΑΥΤΑ τα stats."
    specified_mask = np.array([col in user_stats for col in FEATURE_COLS])

    # ── 2. Season range filter ────────────────────────────────────────────────
    start_year, end_year = _parse_season_range(season_range)
    mask = pd.Series(True, index=df_clean.index)
    if start_year is not None:
        season_years = df_clean["season"].str[:4].astype(int)
        mask &= season_years >= start_year
    if end_year is not None:
        season_years = df_clean["season"].str[:4].astype(int)
        mask &= season_years <= end_year

    df_filtered   = df_clean[mask].reset_index(drop=True)
    mat_filtered  = feature_matrix[mask.values]

    if df_filtered.empty:
        return pd.DataFrame()

    # ── 3. Weighted L2 similarity (masked) ────────────────────────────────────
    # Μόνο τα specified dimensions μπαίνουν στον υπολογισμό.
    # L2 distance: «βρες παίκτες ΚΟΝΤΑ σε αυτές τις τιμές» — σωστό για scouting.
    w_arr = _weight_array(weights)

    user_masked   = user_vec[specified_mask]
    matrix_masked = mat_filtered[:, specified_mask]
    w_masked      = w_arr[specified_mask]

    similarities = _weighted_similarity(user_masked, matrix_masked, w_masked)

    # ── 4. Archetype boost ────────────────────────────────────────────────────
    boost = np.zeros(len(df_filtered))
    if active_traits:
        for trait in active_traits:
            col = f"active_{trait}"
            if col in df_filtered.columns:
                boost += df_filtered[col].astype(float).values * trait_boost

    final_scores = similarities + boost

    # ── 5. Best season ανά παίκτη ─────────────────────────────────────────────
    # Κρατάμε τη σεζόν με το υψηλότερο final_score ανά player_id
    df_scored = df_filtered.copy()
    df_scored["_similarity"] = similarities
    df_scored["_boost"]      = boost
    df_scored["_final"]      = final_scores

    # Για κάθε player_id, κράτα τη σεζόν με max final score
    best_idx = (
        df_scored
        .groupby("player_id")["_final"]
        .idxmax()
    )
    df_best = df_scored.loc[best_idx].copy()

    # ── 6. Sort + top_n ───────────────────────────────────────────────────────
    df_best = df_best.sort_values("_final", ascending=False).head(top_n)

    # ── 7. Explanations ───────────────────────────────────────────────────────
    explanations = []
    for idx in df_best.index:
        orig_idx      = df_filtered.index.get_loc(idx) if idx in df_filtered.index else None
        player_vec    = mat_filtered[df_filtered.index.get_loc(idx)]
        exp           = explain_match(user_vec, player_vec, weights=weights)
        explanations.append(exp)

    # ── 8. Output DataFrame ───────────────────────────────────────────────────
    result_cols = [
        "player_name", "season", "compound_archetype",
        "position_group", "height_cm", "weight_lbs",
    ] + [c for c in ("active_traits",) if c in df_best.columns]

    out = df_best[result_cols].copy()
    out["similarity"]   = df_best["_similarity"].round(4).values
    out["boost"]        = df_best["_boost"].round(4).values
    out["final_score"]  = df_best["_final"].round(4).values
    out["explanation"]  = explanations

    return out.reset_index(drop=True)