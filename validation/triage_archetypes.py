"""
Triage των archetype misclassifications: ποια είναι bug και ποια είναι κρίση.

Τρέξε από repo root:
    python validation/triage_archetypes.py

Το REPORT.md δίνει 52 misses ως επίπεδη λίστα, που δεν λέει πού να δουλέψεις.
Εδώ κατηγοριοποιούνται ώστε να ξεχωρίζει η **τεχνική** δουλειά (ο classifier
έχασε trait) από την **απόφαση ground truth** (και τα δύο labels είναι έγκυρα).

Τρία outputs:
  1. Shadowed presets — presets που είναι subset άλλων, άρα δύσκολα/ποτέ δεν
     κερδίζουν το `_label_archetype` (κρατά το preset με τα περισσότερα traits)
  2. Triage των misses σε 5 κατηγορίες
  3. Ranking των traits κατά το πόσα misses θα ξεκλείδωναν αν διορθώνονταν

ΜΟΝΟ measurement — δεν αλλάζει τίποτα στο src/.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd  # noqa: E402

from archetypes import (COMPOUNDS, PRESET_POSITIONS,  # noqa: E402
                        TRAIT_THRESHOLD, assign_archetypes,
                        compute_trait_scores)
from evaluate import TRAIT_NAMES  # noqa: E402
from labels import LABELS  # noqa: E402
from matching import build_resolver  # noqa: E402
from preprocessing import load_and_clean  # noqa: E402

# Κατηγορίες, με σειρά προτεραιότητας δουλειάς
CATEGORIES = {
    "missing_trait": (
        "A. ΛΕΙΠΕΙ TRAIT — τεχνικό, ΔΙΟΡΘΩΣΙΜΟ",
        "Ο classifier δεν άναψε trait που το expected preset απαιτεί. "
        "Δούλεψε στα signals του trait, όχι στο ground truth.",
    ),
    "more_specific": (
        "B. ΠΙΟ ΣΥΓΚΕΚΡΙΜΕΝΟ LABEL — ΑΠΟΦΑΣΗ GROUND TRUTH",
        "Το expected είναι subset του got: ο classifier βρήκε ΠΕΡΙΣΣΟΤΕΡΑ traits. "
        "Συχνά το got είναι σωστότερο → σκέψου `accept_also` στο labels.py.",
    ),
    "less_specific": (
        "C. ΛΙΓΟΤΕΡΟ ΣΥΓΚΕΚΡΙΜΕΝΟ — τεχνικό",
        "Το got είναι subset του expected: έλειψε ένα trait για το πλήρες preset.",
    ),
    "position": (
        "D. POSITION MISMATCH — design gap στο PRESET_POSITIONS",
        "Κανένα position-valid preset δεν ταίριαξε, οπότε κέρδισε ένα άκυρο.",
    ),
    "different_branch": (
        "E. ΑΛΛΟΣ ΚΛΑΔΟΣ — ανά περίπτωση",
        "Καμία subset σχέση· ο classifier πήγε σε τελείως άλλη οικογένεια.",
    ),
}


def _fmt_traits(ts) -> str:
    return ", ".join(sorted(ts)) if ts else "—"


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    df = load_and_clean()
    scored = compute_trait_scores(df)
    res = assign_archetypes(scored, threshold=TRAIT_THRESHOLD)
    resolve = build_resolver(res)

    L: list[str] = []
    A = L.append

    A("# Archetype Triage")
    A("")
    A(f"Threshold: **{TRAIT_THRESHOLD}** · dataset rows: **{len(df)}** · "
      f"labels: **{len(LABELS)}**")
    A("")

    # ── 1. Shadowed presets ───────────────────────────────────────────────────
    A("## 1. Shadowed presets")
    A("")
    A("Το `_label_archetype()` κρατά το preset με τα **περισσότερα** traits.")
    A("Αν το preset A είναι subset του B, τότε όποιος ενεργοποιεί το A συνήθως")
    A("ενεργοποιεί και το B — και το A δεν εμφανίζεται ποτέ.")
    A("")
    A("| Preset | Φορές σε χρήση | Σκιάζεται από |")
    A("|---|---|---|")
    rows = []
    for a_name, a in COMPOUNDS.items():
        sups = [b for b, bs in COMPOUNDS.items() if b != a_name and a < bs]
        if sups:
            rows.append((int((res["compound_archetype"] == a_name).sum()), a_name, sups))
    for used, name, sups in sorted(rows):
        mark = " ⚠️ **ΠΟΤΕ**" if used == 0 else ""
        A(f"| `{name}` | {used}{mark} | {', '.join(f'`{s}`' for s in sups)} |")
    dead = [n for u, n, _ in rows if u == 0]
    A("")
    if dead:
        A(f"> **{len(dead)} preset(s) είναι δομικά απρόσιτα**: "
          + ", ".join(f"`{d}`" for d in dead) + ". Κάθε label που τα περιμένει "
          "είναι εγγυημένα λάθος — δεν διορθώνεται με tuning.")
    else:
        A("> Κανένα preset δεν είναι εντελώς απρόσιτο.")
    A("")

    # ── 2. Triage ─────────────────────────────────────────────────────────────
    buckets: dict[str, list] = {k: [] for k in CATEGORIES}
    unlock: Counter = Counter()

    for lab in LABELS:
        idx = resolve(lab.name, lab.season)
        if idx is None:
            continue
        row = res.loc[idx]
        got = row["compound_archetype"]
        # Ίδιος κανόνας με το evaluate.py — το accept_also μετράει ως σωστό
        if got == lab.archetype or got in lab.accept_also:
            continue

        exp_set = COMPOUNDS.get(lab.archetype)
        got_set = COMPOUNDS.get(got)
        active  = set(row["active_traits"])
        pos     = row.get("position_group", "?")
        if exp_set is None:
            continue

        missing = exp_set - active
        # Ξεχωρίζουμε τα structural (position-ineligible → score NaN) από τα
        # threshold misses: τα πρώτα δεν διορθώνονται με signal tuning.
        struct = {t for t in missing if pd.isna(row.get(f"score_{t}"))}
        thresh = missing - struct
        allowed = PRESET_POSITIONS.get(got)
        pos_bad = allowed is not None and pos not in allowed

        entry = {
            "player": lab.name, "expected": lab.archetype, "got": got,
            "pos": pos, "missing": thresh, "structural": struct,
        }
        if got_set is not None and exp_set < got_set:
            buckets["more_specific"].append(entry)
        elif got_set is not None and got_set < exp_set:
            buckets["less_specific"].append(entry)
            unlock.update(thresh)
        elif pos_bad:
            buckets["position"].append(entry)
        elif missing:
            buckets["missing_trait"].append(entry)
            unlock.update(thresh)
        else:
            buckets["different_branch"].append(entry)

    total = sum(len(v) for v in buckets.values())
    A(f"## 2. Triage των {total} misses")
    A("")
    A("| Κατηγορία | Πλήθος | Είδος δουλειάς |")
    A("|---|---|---|")
    KIND = {
        "missing_trait": "τεχνικό", "less_specific": "τεχνικό",
        "more_specific": "**ground truth**", "position": "design",
        "different_branch": "ανά περίπτωση",
    }
    for key, (title, _) in CATEGORIES.items():
        A(f"| {title.split('—')[0].strip()} | {len(buckets[key])} | {KIND[key]} |")
    A("")

    for key, (title, blurb) in CATEGORIES.items():
        items = buckets[key]
        A(f"### {title}  ({len(items)})")
        A("")
        A(f"_{blurb}_")
        A("")
        if not items:
            A("_(καμία)_")
            A("")
            continue
        A("| Παίκτης | Θέση | Expected | Got | Λείπουν traits |")
        A("|---|---|---|---|---|")
        for e in items:
            miss = _fmt_traits(e["missing"])
            if e["structural"]:
                miss += f" _(structural: {_fmt_traits(e['structural'])})_"
            A(f"| {e['player']} | {e['pos']} | `{e['expected']}` | `{e['got']}` | {miss} |")
        A("")

    # ── 3. Ranking traits ─────────────────────────────────────────────────────
    A("## 3. Ποιο trait ξεκλειδώνει τα περισσότερα misses")
    A("")
    A("Πόσα misses θα διορθώνονταν αν το trait έπιανε σωστά (κατηγορίες A + C).")
    A("Αυτή είναι η σειρά προτεραιότητας για τεχνική δουλειά.")
    A("")
    if unlock:
        A("| Trait | Misses που ξεκλειδώνει |")
        A("|---|---|")
        for t, n in unlock.most_common():
            A(f"| `{t}` | {n} |")
    else:
        A("_(κανένα)_")
    A("")
    A("> Προσοχή: ένα miss μπορεί να χρειάζεται **περισσότερα** από ένα traits,")
    A("> οπότε τα νούμερα δεν αθροίζονται στο σύνολο των misses.")
    A("")

    report = "\n".join(L)
    print(report)
    out = Path(__file__).parent / "TRIAGE.md"
    out.write_text(report + "\n", encoding="utf-8")
    print(f"\n[written] {out}")


if __name__ == "__main__":
    main()
