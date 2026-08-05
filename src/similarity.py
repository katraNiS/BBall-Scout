"""
Similarity engine: βρίσκει τους πιο όμοιους παίκτες για ένα user-defined profile.

Βασική λογική:
  1. Weighted RMS (L2) distance στο normalized feature space, masked στα stats
     που όρισε ο χρήστης
  2. Archetype boost για παίκτες με shared active traits
  3. Explanation ανά match (τι έφερε κοντά, τι διαφέρει)

find_similar() — κεντρική συνάρτηση
explain_match() — per-match explanation
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from preprocessing import FEATURE_COLS, build_availability_matrix


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



# Πόσο απότομα πέφτει η εμπιστοσύνη καθώς λιγοστεύουν τα διαθέσιμα δεδομένα.
#
# α = 1.0 → γραμμικό shrinkage: το πλεονέκτημα ενός match μειώνεται αναλογικά
# με το κλάσμα της πληροφορίας που πραγματικά είχαμε. Ισοδυναμεί με posterior
# mean όπου το coverage παίζει ρόλο effective sample size — γι' αυτό
# προτιμήθηκε από ad-hoc πολλαπλασιαστικό penalty.
#
# Επιλέχθηκε με μετρημένη σύγκριση (validation/defense_impact.py):
#   α=0   pure masking — υπερδιόρθωση· ο Alex Caruso (coverage 1.00, προφανές
#         match) πέφτει 6ος πίσω από rows με 0.67 coverage
#   α=0.5 era balance πιο κοντά στο baseline, αλλά 4/5 του top-5 έχουν ελλιπή
#         δεδομένα
#   α=1.0 top-4 με πλήρη δεδομένα, ιστορικοί αμυντικοί (Hawkins, Kidd,
#         Christie, Ben Wallace) προσβάσιμοι από την 5η θέση και κάτω  ← εδώ
#   α≥1.5 οι pre-2016 ξαναεξαφανίζονται — επιστροφή στο αρχικό πρόβλημα
CONFIDENCE_ALPHA = 1.0


def _weighted_similarity(
    user_vec: np.ndarray,
    matrix: np.ndarray,
    weight_arr: np.ndarray,
    availability: np.ndarray | None = None,
    alpha: float = CONFIDENCE_ALPHA,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Weighted L2 similarity μεταξύ user_vec και κάθε row του matrix.

    Χρησιμοποιούμε L2 distance αντί cosine γιατί το scouting tool ζητά
    «βρες παίκτες ΚΟΝΤΑ σε αυτές τις τιμές», όχι «ίδιο proportional profile».
    Cosine τιμωρεί παίκτες με extreme stats σε unspecified dimensions —
    L2 τιμωρεί αυτούς που απέχουν από τις τιμές που ζήτησε ο χρήστης.

    distance_i = sqrt(Σ w_j × (user_j - player_j)² / Σ w_j)
    similarity  = 1 / (1 + distance)  →  (0, 1], 1 = τέλεια αντιστοιχία

    Χρησιμοποιούμε 1/(1+d) αντί exp(-d) γιατί τα z-score distances είναι
    φυσικά μεγάλα (sqrt(5 features × 2²) ≈ 4.5), οπότε exp(-4.5) ≈ 0.01
    κάνει όλα τα scores ίδια. Το 1/(1+4.5) = 0.18 δίνει χρήσιμο range.

    Weighted RMS: διαιρούμε με το άθροισμα βαρών ώστε το distance να μην
    αυξάνεται καθώς ορίζονται περισσότερα stats. Χωρίς normalization,
    6 stats με diff=0.5 δίνουν sqrt(6×0.25)≈1.22 αντί sqrt(0.25)=0.5.

    ── Availability-aware masking ────────────────────────────────────────────
    Όταν δίνεται `availability` (boolean, ίδιο shape με το matrix), το distance
    υπολογίζεται ΜΟΝΟ στις διαστάσεις που έχουν πραγματικά δεδομένα για κάθε
    row, με renormalization του Σw σε αυτές. Λόγος: τα hustle stats λείπουν
    πριν το 2016-17 και το group-median imputation τοποθετούσε το 56% της βάσης
    σε σταθερή απόσταση τιμωρίας — defensive queries επέστρεφαν 0% pre-2016.

    Σκέτο masking όμως ΥΠΕΡΔΙΟΡΘΩΝΕΙ: ένα row που κρίνεται σε 2 αντί για 3
    διαστάσεις έχει λιγότερες ευκαιρίες να απέχει, άρα παίρνει ευκολότερα καλό
    score (μετρημένο: 64-88% pre-2016 έναντι baseline 58%).

    Η διόρθωση είναι shrinkage προς το population prior:

        coverage  = Σ(w των διαθέσιμων) / Σ(w των ζητούμενων)
        sim_final = sim_pop + coverage^α × (sim_masked − sim_pop)

    όπου `sim_pop` είναι το similarity ενός τυπικού παίκτη. Επειδή το feature
    space είναι z-scored (mean 0, std 1), το expected squared distance ανά
    διάσταση είναι αναλυτικά υπολογίσιμο:

        E[(u_j − P_j)²] = E[P_j²] − 2·u_j·E[P_j] + u_j² = 1 + u_j²

    Ιδιότητες που μας ενδιαφέρουν:
      - coverage = 1 → sim_final = sim_masked ακριβώς. Μηδενική επίδραση σε
        offensive queries και σε tracking-era παίκτες (κανένα regression).
      - coverage → 0 → sim_final → sim_pop: το row πέφτει στον μέσο όρο αντί
        να ανεβαίνει ψεύτικα. «Δεν ξέρουμε» ≠ «ταιριάζει».

    Επιστρέφει (similarity, coverage) — το coverage εκτίθεται στο UI ως
    ένδειξη εμπιστοσύνης του match.
    """
    diff_sq = (matrix - user_vec) ** 2               # (n_players, n_features)
    total_w = weight_arr.sum() if weight_arr.sum() > 0 else 1.0

    if availability is None:
        distances = np.sqrt((diff_sq * weight_arr).sum(axis=1) / total_w)
        return 1.0 / (1.0 + distances), np.ones(len(matrix))

    avail_w  = (availability * weight_arr).sum(axis=1)   # (n_players,)
    coverage = avail_w / total_w

    # Masked RMS — μόνο στις διαστάσεις με πραγματικά δεδομένα
    num       = (diff_sq * weight_arr * availability).sum(axis=1)
    has_data  = avail_w > 0
    d_masked  = np.full(len(matrix), np.inf)
    d_masked[has_data] = np.sqrt(num[has_data] / avail_w[has_data])
    sim_masked = 1.0 / (1.0 + d_masked)

    # Population baseline (ίδιο για κάθε row — εξαρτάται μόνο από το query)
    d_pop   = np.sqrt((weight_arr * (1.0 + user_vec ** 2)).sum() / total_w)
    sim_pop = 1.0 / (1.0 + d_pop)

    sim = sim_pop + (coverage ** alpha) * (sim_masked - sim_pop)
    sim[~has_data] = sim_pop      # καμία διάσταση γνωστή → καθαρά prior
    return sim, coverage


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
    specified_mask: np.ndarray | None = None,
) -> dict:
    """
    Εξηγεί γιατί ένας παίκτης ταιριάζει στο user profile.

    Μετράει weighted absolute difference ανά feature:
      - Μικρή διαφορά → το feature "ταίριαξε" (contributing)
      - Μεγάλη διαφορά → το feature "διαφέρει" (diverging)

    Args:
      specified_mask — boolean array (len = FEATURE_COLS) που δείχνει ποια features
        όρισε ρητά ο χρήστης. Ίδιο mask με αυτό του similarity, ώστε η εξήγηση να
        είναι συνεπής με το score. Αν είναι None, fallback σε z≠0 heuristic
        (πρόβλημα: stat που ο χρήστης όρισε ΚΟΝΤΑ στο league mean θα χανόταν).

    Επιστρέφει:
      matching   — [(feature, user_val, player_val), ...] top ομοιότητες
      diverging  — [(feature, user_val, player_val), ...] top διαφορές
    """
    w_arr = _weight_array(weights)

    # Weighted absolute difference ανά feature (στο z-score space)
    diffs = np.abs(user_vec_raw - player_vec_raw) * w_arr

    # Κρατάμε μόνο τα features που όρισε ο χρήστης. Χρησιμοποιούμε το ρητό mask
    # όταν δίνεται (συνεπές με τον υπολογισμό του similarity)· αλλιώς fallback
    # στο z≠0 heuristic (ένα stat ίσο με το league mean δίνει z≈0 και θα χανόταν).
    if specified_mask is not None:
        user_defined = np.asarray(specified_mask, dtype=bool)
    else:
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
    availability: np.ndarray | None = None,
    confidence_alpha: float = CONFIDENCE_ALPHA,
) -> pd.DataFrame:
    """
    Βρίσκει τους top_n πιο όμοιους παίκτες.

    Args:
        user_stats:    {"fg3_pct": 0.38, "ast_pct": 0.26, ...}
                       ΠΡΟΣΟΧΗ: τα pct stats είναι fractions (0.0–1.0), όχι percentages
                       (ast_pct=0.26, όχι 26.0 — αλλιώς z-score ~285). Βλ. CLAUDE.md.
                       Stats που δεν ορίζονται → population mean (z=0, neutral)
        df_clean:      DataFrame από preprocessing.load_and_clean()
        feature_matrix: z-scored array από preprocessing.build_feature_matrix()
        scaler:        fitted StandardScaler από preprocessing
        weights:       {"fg3_pct": 3, "ast_pct": 2} — default 1 για όλα
        top_n:         αριθμός αποτελεσμάτων
        active_traits: traits που θέλει ο χρήστης (boost, όχι hard filter)
        trait_boost:   bonus score ανά shared trait
        season_range:  "2010-2025" για φιλτράρισμα εποχής (start-end year)
        availability:  boolean array (n_rows × n_features) — True όπου η τιμή
                       είναι πραγματική, False όπου imputed. Αν είναι None,
                       παράγεται αυτόματα από τις `avail_*` στήλες του df_clean
                       (βλ. preprocessing.build_availability_matrix). Πέρασε
                       ρητά έναν πίνακα από True για να απενεργοποιήσεις το
                       masking.
        confidence_alpha: εκθέτης του shrinkage — μεγαλύτερο = αυστηρότερη
                       τιμωρία των rows με ελλιπή δεδομένα.

    Returns:
        DataFrame με columns: player_name, season, compound_archetype,
        similarity, coverage, boost, final_score, explanation, + original stats
    """
    # ── 1. Μετατροπή user stats σε scaled vector ──────────────────────────────
    # Ξεκινάμε από τα population means (= 0 μετά το z-score scaling)
    user_raw = scaler.mean_.copy()
    for i, col in enumerate(FEATURE_COLS):
        if col in user_stats and user_stats[col] is not None:
            user_raw[i] = float(user_stats[col])

    user_vec = scaler.transform(user_raw.reshape(1, -1)).flatten()

    # Mask των features που ο χρήστης όρισε ρητά.
    # Το distance υπολογίζεται ΜΟΝΟ σε αυτές τις διαστάσεις — τα unspecified stats
    # δεν επηρεάζουν το score. Έτσι ένας παίκτης με extreme τιμές σε features που
    # ο χρήστης δεν ρώτησε (π.χ. πολλά deflections ενώ δεν ζητήθηκε άμυνα) δεν
    # τιμωρείται: "βρες παίκτες που ταιριάζουν σε ΑΥΤΑ τα stats."
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

    if availability is None:
        availability = build_availability_matrix(df_clean)
    avail_filtered = np.asarray(availability, dtype=bool)[mask.values]

    if df_filtered.empty:
        return pd.DataFrame()

    # ── 3. Weighted L2 similarity (masked) ────────────────────────────────────
    # Μόνο τα specified dimensions μπαίνουν στον υπολογισμό.
    # L2 distance: «βρες παίκτες ΚΟΝΤΑ σε αυτές τις τιμές» — σωστό για scouting.
    w_arr = _weight_array(weights)

    user_masked   = user_vec[specified_mask]
    matrix_masked = mat_filtered[:, specified_mask]
    w_masked      = w_arr[specified_mask]
    avail_masked  = avail_filtered[:, specified_mask]

    similarities, coverage = _weighted_similarity(
        user_masked, matrix_masked, w_masked,
        availability=avail_masked, alpha=confidence_alpha,
    )

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
    df_scored["_coverage"]   = coverage
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
    # df_scored/df_best κληρονομούν το RangeIndex του df_filtered (reset στο βήμα 2),
    # οπότε το index είναι θέση στο mat_filtered — direct lookup, χωρίς get_loc.
    explanations = []
    for idx in df_best.index:
        player_vec = mat_filtered[idx]
        exp        = explain_match(
            user_vec, player_vec, weights=weights, specified_mask=specified_mask
        )
        explanations.append(exp)

    # ── 8. Output DataFrame ───────────────────────────────────────────────────
    pct_cols = [c for c in df_best.columns if c.startswith("pct_")]
    result_cols = [
        "player_name", "season", "compound_archetype",
        "position_group", "height_cm", "weight_lbs",
    ] + [c for c in ("active_traits",) if c in df_best.columns] + pct_cols

    out = df_best[result_cols].copy()
    out["similarity"]   = df_best["_similarity"].round(4).values
    # Κλάσμα του ζητούμενου weight που είχε πραγματικά δεδομένα (1.0 = πλήρης
    # πληροφορία). Το UI το δείχνει ως confidence indicator του match.
    out["coverage"]     = df_best["_coverage"].round(4).values
    out["boost"]        = df_best["_boost"].round(4).values
    out["final_score"]  = df_best["_final"].round(4).values
    out["explanation"]  = explanations

    return out.reset_index(drop=True)