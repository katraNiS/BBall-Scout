# BBall Scout

Ένα **scouting εργαλείο** που βρίσκει πραγματικούς παίκτες με βάση ένα custom στατιστικό/χαρακτηριστικό προφίλ — όχι quiz τύπου "ποιος παίκτης είμαι", αλλά πραγματικό εργαλείο ανάλυσης για scouting και roster building.

> Project στο πλαίσιο πτυχιακής. Προτεραιότητα στην **ακρίβεια** και στην **τεκμηρίωση** κάθε σχεδιαστικής απόφασης.

---

## Τι κάνει

Ο χρήστης (scout) ορίζει ένα **player profile**: στατιστικά + βάρη ανά stat. Το σύστημα επιστρέφει τους **πιο όμοιους πραγματικούς παίκτες** από τη βάση, με **explainability** — δηλαδή _γιατί_ ταιριάζει ο καθένας (ποια stats συμπίπτουν, ποια αποκλίνουν, και κατά πόσο).

Ο χρήστης μπορεί επίσης να επιλέξει **traits** (π.χ. `lead_playmaker`, `spot_up_shooter`) για να δώσει μικρό boost σε παίκτες με αυτό το profile, χωρίς να αποκλείει κανέναν.

---

## Πώς δουλεύει (high-level)

```
nba_api  →  pipeline/fetch_nba_data.py  →  data/nba_stats_full.csv
                                                    ↓
                                         src/preprocessing.py
                                         (normalization, z-scores)
                                                    ↓
                                         src/archetypes.py
                                         (18 primitives → 29 compound presets)
                                                    ↓
                                         src/similarity.py
                                         (weighted L2 matching + explanations)
                                                    ↓
                                         app/streamlit_app.py  ←  χρήστης
```

**Compositional archetypes:** αντί για ~10 fixed κουτιά, ορίζουμε **18 primitive traits** (π.χ. `slasher`, `rim_protector`, `lead_playmaker`) που συνδυάζονται αυτόματα σε **~29 σύνθετα archetypes** (π.χ. `playmaking_big` + `rim_protector` + `help_defender` = "Playmaking Rim Protector"). Ο ίδιος feature space χρησιμοποιείται και για το matching.

**Similarity metric:** weighted L2 distance στο z-score space, masked μόνο στα stats που ο χρήστης όρισε. `1/(1+distance)` → score (0, 1].

Πλήρεις ορισμοί traits/compounds στο [`archetype_spec.md`](./archetype_spec.md).

---

## Tech stack

| Layer | Επιλογή |
|---|---|
| Language | Python |
| Data storage | CSV flat file (`data/nba_stats_full.csv`) |
| Data sources | nba_api (box + advanced + scoring + hustle), Kaggle (wingspan) |
| ML / Math | scikit-learn, pandas, numpy |
| Web UI | Streamlit |

> Δεν χρησιμοποιούμε βάση δεδομένων στο παρόν στάδιο — το CSV είναι αρκετό για ~30k rows.
> PostgreSQL/SQLAlchemy παραμένει επιλογή για αργότερα.

---

## Κατάσταση project

- [x] Ορισμός ιδέας & scope (NBA-only πρώτα)
- [x] API exploration — ξέρουμε ακριβώς τι fields δίνει το `nba_api`
- [x] Archetype design: 18 primitives + 29 compound presets (`archetype_spec.md`)
- [x] Data pipeline — box/advanced + scoring (PCT_PTS_2PT_MR κ.α.) + hustle (deflections κ.α.)
- [x] `src/preprocessing.py` — normalization, tiered MPG filter, z-scores
- [x] `src/archetypes.py` — trait signals + compound presets + classifier
- [x] `src/similarity.py` — weighted L2 matching, trait boost, explanations
- [x] `app/streamlit_app.py` — working Streamlit UI
- [x] Validation: 20 γνωστοί παίκτες (stars + role players) — archetypes & similarity
- [x] Position-aware preset matching (`PRESET_POSITIONS`) — διορθώνει misclassification (π.χ. Porzingis → "Slashing Guard")
- [x] Scale-invariant similarity — weighted RMS αντί raw sum, αποφεύγει compression με πολλά stats
- [x] Radar chart (percentile 0–100) — StatsBomb-style, player vs user target, `plotly`
- [ ] Classifier threshold tuning (precision/recall ανά trait)
- [ ] UI: φίλτρο ανά position, export αποτελεσμάτων σε CSV
- [ ] FastAPI backend (αντικατάσταση scripts)
- [ ] Multi-league support (NCAA, EuroLeague κ.α.)

---

## Δομή αρχείων

```
BBall-Scout/
├── README.md                  ← αυτό το αρχείο
├── CLAUDE.md                  ← context/οδηγίες για το Claude Code
├── archetype_spec.md          ← πλήρες spec των archetypes (traits + compounds)
├── data/
│   └── nba_stats_full.csv     ← merged dataset (δεν είναι στο git)
├── pipeline/
│   └── fetch_nba_data.py      ← fetch nba_api → CSV  [DONE]
├── src/
│   ├── preprocessing.py       ← load, clean, normalize  [DONE]
│   ├── archetypes.py          ← trait signals + presets + classifier  [DONE]
│   └── similarity.py          ← matching engine  [DONE]
└── app/
    └── streamlit_app.py       ← Streamlit UI  [DONE]
```

---

## Setup

```bash
pip install nba_api pandas scikit-learn streamlit numpy

# 1. Fetch data (τρέχει μόνο τοπικά — nba_api δεν λειτουργεί σε sandbox)
python pipeline/fetch_nba_data.py

# 2. Εκκίνηση UI
streamlit run app/streamlit_app.py
```

---

## Data sources

**nba_api** — box score + advanced stats (1996–σήμερα), scoring profile (2013-14+), hustle stats (2015-16+).

**Kaggle (NBA Draft Combine)** — `wingspan` (2000+), που δεν υπάρχει στο API.

Τι **δεν** έχουμε (συνειδητές αποφάσεις):
- `VORP`, `PER`, `WS/48` — Basketball-Reference exclusive· limitation που τεκμηριώνεται.
- Wingspan μόνο 2000+· athleticism/vertical εκτός scope.

---

## Σχεδιαστικές αρχές

- **Ακρίβεια + αιτιολόγηση** — κάθε feature/βάρος έχει λόγο ύπαρξης.
- **Masked similarity** — stats που ο χρήστης δεν ορίζει δεν επηρεάζουν το score.
- **Honest limitations** — η άμυνα πιάνεται αδύναμα από box-score stats· τα defensive traits έχουν τα περισσότερα λάθη, και αυτό τεκμηριώνεται αντί να κρύβεται.
- **Επεκτασιμότητα χωρίς over-engineering** — multi-league αργότερα, καθαρά, χωρίς να περιπλέκουμε το τώρα.