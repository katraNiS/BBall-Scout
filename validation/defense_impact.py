"""
Impact measurement για τα δύο defensive fixes.

Τρέξε από repo root:
    python validation/defense_impact.py

Μετράει τρία πράγματα πάνω στο τρέχον feature space:
  1. Era balance — τι ποσοστό pre-tracking παικτών επιστρέφει κάθε defensive query
     (το core σύμπτωμα: το deflections μηδένιζε το 56% της βάσης)
  2. Corrupt-season contamination — αν τα 2015-16 rows κυριαρχούν σε high-deflections
     queries
  3. Discriminative power του def_rating — αν το νέο feature όντως ξεχωρίζει
     αμυντικούς

ΜΟΝΟ measurement — δεν αλλάζει τίποτα.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from archetypes import classify                                  # noqa: E402
from preprocessing import build_feature_matrix, load_and_clean    # noqa: E402
from similarity import CONFIDENCE_ALPHA, find_similar           # noqa: E402

TRACKING_ERA = 2016          # πρώτη σεζόν με αξιόπιστα hustle data
TOP_N = 25

# (label, query) — τα queries χωρίζονται σε αυτά που ΑΓΓΙΖΟΥΝ tracking-only
# features και σε αυτά που μένουν σε full-coverage features.
QUERIES_TRACKING = [
    ("3-and-D wing",       {"fg3a": 5.5, "fg3_pct": 0.38, "stl": 1.3, "deflections": 3.0}),
    ("perimeter stopper",  {"stl": 1.8, "deflections": 3.8, "usg_pct": 0.14}),
    ("hustle big",         {"blk": 1.8, "deflections": 2.6, "dreb_pct": 0.22}),
]
QUERIES_FULL_COVERAGE = [
    ("3-and-D (def_rating)",   {"fg3a": 5.5, "fg3_pct": 0.38, "stl": 1.3, "def_rating": 103.0}),
    ("stopper (def_rating)",   {"stl": 1.8, "def_rating": 101.0, "usg_pct": 0.14}),
    ("rim protector",          {"blk": 2.4, "dreb_pct": 0.24, "def_rating": 102.0}),
    ("elite team defender",    {"def_rating": 100.0, "stl": 1.4, "blk": 1.0}),
]
QUERIES_CONTROL = [
    ("elite shooter",   {"fg3a": 8.0, "fg3_pct": 0.40, "ts_pct": 0.62}),
    ("lead playmaker",  {"ast_pct": 0.35, "ast_to": 2.5, "usg_pct": 0.26}),
    ("post scorer",     {"pts": 20.0, "fta": 6.5, "usg_pct": 0.28}),
]


def _pre_era_share(res) -> float:
    return float((res["season"].str[:4].astype(int) < TRACKING_ERA).mean())


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    df = classify(load_and_clean())
    matrix, scaler = build_feature_matrix(df)

    years = df["season"].str[:4].astype(int)
    baseline = float((years < TRACKING_ERA).mean())

    L: list[str] = []
    A = L.append

    A("# Defensive Matching — Impact Report")
    A("")
    A(f"- Rows: **{len(df)}** | features: **{matrix.shape[1]}**")
    A(f"- Pre-tracking (<{TRACKING_ERA}) share of dataset: **{baseline:.1%}** "
      "— ένα αμερόληπτο query πρέπει να πλησιάζει αυτό το ποσοστό")
    A(f"- Max deflections: **{df['deflections'].max():.2f}**/gm "
      "(NBA record ≈ 5.9· τιμές >6.5 σημαίνουν totals-scaled corruption)")
    A("")

    # ── 1. Era balance ────────────────────────────────────────────────────────
    A("## 1. Era balance ανά query type")
    A("")
    A(f"Ποσοστό pre-{TRACKING_ERA} παικτών στα top-{TOP_N}.")
    A("")
    A("| Query | Features | pre-tracking | Απόκλιση από baseline |")
    A("|---|---|---|---|")

    def row(label, q, kind):
        res = find_similar(q, df, matrix, scaler, top_n=TOP_N)
        share = _pre_era_share(res)
        delta = share - baseline
        return share, f"| {label} | {kind} | {share:.1%} | {delta:+.1%} |"

    tracking_shares, full_shares = [], []
    for label, q in QUERIES_TRACKING:
        s, line = row(label, q, "tracking-only")
        tracking_shares.append(s)
        A(line)
    for label, q in QUERIES_FULL_COVERAGE:
        s, line = row(label, q, "full-coverage")
        full_shares.append(s)
        A(line)
    for label, q in QUERIES_CONTROL:
        _, line = row(label, q, "offense (control)")
        A(line)
    A("")
    A(f"- Defensive queries με **deflections**: μέσο pre-tracking share "
      f"**{np.mean(tracking_shares):.1%}** _(ήταν 0.0% πριν το masking)_")
    A(f"- Defensive queries με **def_rating**: μέσο pre-tracking share "
      f"**{np.mean(full_shares):.1%}**")
    A("")
    A("> Το `deflections` υπάρχει μόνο από το 2016-17. Πριν το availability-aware")
    A("> masking, κάθε imputed row καθόταν σε σταθερή απόσταση τιμωρίας και το era")
    A("> share κατέρρεε στο 0%. Τώρα το distance υπολογίζεται μόνο στις διαστάσεις")
    A("> με πραγματικά δεδομένα, και το score shrink-άρει προς το population prior")
    A("> ανάλογα με το coverage — ώστε τα ελλιπή rows να μην εκτοπίζουν όσα έχουν")
    A("> πλήρη δεδομένα.")
    A("")

    # ── 1b. Confidence discount ───────────────────────────────────────────────
    A("### Confidence discount (`CONFIDENCE_ALPHA`)")
    A("")
    A("`sim = sim_pop + coverage^α × (sim_masked − sim_pop)`")
    A("")
    A("Ευαισθησία του era balance στο α, για το query «perimeter stopper»:")
    A("")
    A("| α | pre-tracking | #1 result | coverage του #1 |")
    A("|---|---|---|---|")
    q_alpha = {"stl": 1.8, "deflections": 3.8, "usg_pct": 0.14}
    for a in (0.0, 0.5, 1.0, 1.5, 3.0):
        r = find_similar(q_alpha, df, matrix, scaler, top_n=TOP_N, confidence_alpha=a)
        top = r.iloc[0]
        mark = "  ← ενεργό" if a == CONFIDENCE_ALPHA else ""
        A(f"| {a}{mark} | {_pre_era_share(r):.1%} | {top['player_name']} "
          f"({top['season']}) | {top['coverage']:.2f} |")
    A("")
    A("> α=0 είναι σκέτο masking: υπερδιορθώνει, και rows με ελλιπή δεδομένα")
    A("> εκτοπίζουν παίκτες με πλήρη. α≥1.5 επαναφέρει τον αποκλεισμό.")
    A("")

    # ── 2. Corrupt-season contamination ───────────────────────────────────────
    A("## 2. Corrupt-season contamination (2015-16)")
    A("")
    res = find_similar({"deflections": 4.5, "stl": 1.5}, df, matrix, scaler,
                       weights={"deflections": 4}, top_n=10)
    n_2015 = int((res["season"] == "2015-16").sum())
    A(f"High-deflections query → **{n_2015}/10** αποτελέσματα από το 2015-16 "
      "(πριν το fix: 5/10, με Curry/Harden/Butler ως «elite stoppers»).")
    A("")
    A("| # | Player | Season | Pos | Similarity |")
    A("|---|---|---|---|---|")
    for i, (_, r) in enumerate(res.iterrows(), 1):
        A(f"| {i} | {r['player_name']} | {r['season']} | "
          f"{r['position_group']} | {r['similarity']:.4f} |")
    A("")

    # ── 3. def_rating discriminative power ────────────────────────────────────
    A("## 3. Ξεχωρίζει το `def_rating` πραγματικούς αμυντικούς;")
    A("")
    league_mean = float(df["def_rating"].mean())
    A(f"League mean def_rating: **{league_mean:.1f}** (χαμηλό = καλύτερο)")
    A("")
    A("| Query def_rating | Mean def_rating των top-25 | Διαφορά |")
    A("|---|---|---|")
    for target in (98.0, 102.0, 106.0, 110.0):
        r = find_similar({"def_rating": target, "stl": 1.2}, df, matrix, scaler,
                         weights={"def_rating": 3}, top_n=TOP_N)
        got = float(r["def_rating"].mean()) if "def_rating" in r.columns else float("nan")
        if got != got:  # το find_similar δεν επιστρέφει raw stat cols
            ids = set(zip(r["player_name"], r["season"]))
            sub = df[[(n, s) in ids for n, s in zip(df["player_name"], df["season"])]]
            got = float(sub["def_rating"].mean())
        A(f"| {target:.0f} | {got:.1f} | {got - league_mean:+.1f} |")
    A("")
    A("> Μονοτονική σχέση = το feature είναι πραγματικά διακριτικό, όχι noise.")
    A("")

    report = "\n".join(L)
    print(report)
    out = Path(__file__).parent / "DEFENSE_IMPACT.md"
    out.write_text(report + "\n", encoding="utf-8")
    print(f"\n[written] {out}")


if __name__ == "__main__":
    main()
