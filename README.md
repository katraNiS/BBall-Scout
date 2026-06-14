# BBall Scout

Ένα **scouting εργαλείο** που βρίσκει πραγματικούς παίκτες με βάση ένα custom στατιστικό/χαρακτηριστικό προφίλ — όχι quiz τύπου "ποιος παίκτης είμαι", αλλά πραγματικό εργαλείο ανάλυσης για scouting και roster building.

> Project στο πλαίσιο πτυχιακής. Προτεραιότητα στην **ακρίβεια** και στην **τεκμηρίωση** κάθε σχεδιαστικής απόφασης.

---

## Τι κάνει

Ο χρήστης (scout) ορίζει ένα **player profile**: στατιστικά, physical attributes, και επιθυμητό archetype (π.χ. "3-and-D wing"). Το σύστημα επιστρέφει τους **πιο όμοιους πραγματικούς παίκτες** από τη βάση, με **explainability** — δηλαδή _γιατί_ ταιριάζει ο καθένας.

Ο χρήστης μπορεί επίσης να δώσει **βάρη** (π.χ. "το 3P% μετράει 3× περισσότερο από το FT%"), ώστε το matching να αντικατοπτρίζει τις δικές του προτεραιότητες.

---

## Στόχοι

- **Similarity search** πάνω σε πραγματικά NBA δεδομένα, με κανονικοποιημένα stats.
- **Compositional archetype system** — κάθε παίκτης περιγράφεται ως συνδυασμός ατομικών δεξιοτήτων (traits), όχι ως ένα κουτί.
- **Weighted, user-driven matching** — ο scout ελέγχει τι μετράει.
- **Explainable αποτελέσματα** — κάθε match συνοδεύεται από το _γιατί_.
- **Επεκτάσιμη αρχιτεκτονική** — αρχικά NBA, με δυνατότητα προσθήκης NCAA, G-League, EuroLeague, EuroCup χωρίς rewrite.

---

## Πώς δουλεύει (high-level)

```
Δεδομένα (NBA API + Kaggle)
      ↓
Normalization & feature engineering
      ↓
Trait scoring  →  compound archetype ανά παίκτη
      ↓
Matching engine (similarity + weights + archetype filter)
      ↓
Web UI: input profile → ranked όμοιοι παίκτες + explanations
```

Το **compositional** κομμάτι είναι ο πυρήνας: αντί για ~10 fixed archetypes, ορίζουμε **18 primitive traits** (π.χ. `slasher`, `rim_protector`, `lead_playmaker`) που **συνδυάζονται** σε ~29 σύνθετα archetypes (π.χ. `playmaking_big` + `rim_protector` = "Playmaking Rim Protector", όπως ο Draymond Green). Έτσι N traits δίνουν 2^N δυνατούς συνδυασμούς δωρεάν. Πλήρεις ορισμοί στο [`archetype_spec.md`](./archetype_spec.md).

---

## Tech stack

| Layer | Επιλογή |
|---|---|
| Language | Python |
| Database | PostgreSQL + SQLAlchemy ORM |
| Data | nba_api, Kaggle (NBA Draft Combine) |
| ML / Math | scikit-learn, pandas, numpy |
| Web UI | Streamlit (πρώτο prototype) |

---

## Κατάσταση project

- [x] Ορισμός ιδέας & scope (NBA-only πρώτα)
- [x] API exploration — ξέρουμε ακριβώς τι fields δίνει το `nba_api`
- [x] Database schema design (normalized, 4 tables)
- [x] `db/models.py` — SQLAlchemy models
- [x] `db/init_db.py` — δημιουργία tables + seed builds
- [x] `engine/validation_set.py` — ground truth παικτών για testing
- [x] Σχεδιασμός archetype system (18 primitives + 29 compounds)
- [x] `archetype_spec.md` — πλήρες spec των archetypes
- [ ] Schema update: προσθήκη `oreb_pct`, `dreb_pct`, `fga`
- [ ] `engine/traits.py` — τα 18 primitives ως κώδικας
- [ ] `engine/presets.py` — τα 29 compounds
- [ ] Data pipeline (fetch NBA API + merge Kaggle + load DB)
- [ ] Trait classifier + multi-label validation
- [ ] Matching engine
- [ ] Streamlit UI

---

## Δομή αρχείων

```
scouting_tool/
├── README.md                  ← αυτό το αρχείο (επισκόπηση project)
├── CLAUDE.md                  ← context/οδηγίες για το Claude Code
├── archetype_spec.md          ← πλήρες spec των archetypes (traits + compounds)
├── db/
│   ├── models.py              ← SQLAlchemy models (4 tables)          [DONE]
│   └── init_db.py             ← table creation + seed                 [DONE]
├── data_exploration/
│   └── explore_nba_api.py     ← exploration του API                   [DONE]
├── engine/
│   ├── validation_set.py      ← ground truth για testing             [DONE]
│   ├── archetypes.py          ← 1η έκδοση (fixed) — προς αντικατάσταση
│   ├── traits.py              ← 18 primitives                          [TODO]
│   ├── presets.py             ← 29 compound archetypes                 [TODO]
│   ├── classifier.py          ← trait scoring & assignment            [TODO]
│   └── matcher.py             ← similarity + weights + filter         [TODO]
├── pipeline/
│   └── fetch_nba_data.py      ← fetch + merge + load                   [TODO]
└── app/
    └── streamlit_app.py       ← UI                                     [TODO]
```

---

## Data sources

**nba_api** — box score + advanced stats, season-by-season, physical (height/weight).

**Kaggle (NBA Draft Combine)** — `wingspan` (2000+), που δεν υπάρχει στο API.

Τι **δεν** έχουμε (συνειδητές αποφάσεις):
- `VORP`, `PER`, `WS/48` — Basketball-Reference exclusive· τα παραλείπουμε (limitation στη διπλωματική).
- Wingspan μόνο 2000+· athleticism/vertical εκτός scope (κρατάμε μόνο wingspan από το Combine).

---

## Setup

```bash
# 1. Dependencies
pip install nba_api pandas sqlalchemy psycopg2-binary scikit-learn streamlit

# 2. PostgreSQL
psql -U postgres -c "CREATE DATABASE nba_scouting;"

# 3. Άλλαξε το DATABASE_URL στο db/models.py (username:password)

# 4. Στήσιμο βάσης
python db/init_db.py
```

> Σημείωση: το `nba_api` δεν λειτουργεί σε sandboxed περιβάλλοντα — τρέχει μόνο τοπικά.

---

## Roadmap

1. **Schema update** — προσθήκη `oreb_pct`, `dreb_pct`, `fga`.
2. **Traits & presets σε κώδικα** — `traits.py`, `presets.py` από το spec.
3. **Data pipeline** — fetch NBA API, parse height "6-9"→cm, merge wingspan, load DB (με rate limiting ~1.5s/call).
4. **Classifier** — trait scoring με z-scores (position-relative για bigs), threshold tuning στο validation set.
5. **Matching engine** — cosine similarity + user weights + archetype filtering, με explanations.
6. **Streamlit UI** — input form, ranked αποτελέσματα, radar charts, export.

---

## Σχεδιαστικές αρχές

- **Normalized data** — κανένα διπλό δεδομένο (ο LeBron μία φορά, τα stats του ανά σεζόν χωριστά).
- **Ακρίβεια + αιτιολόγηση** — κάθε στήλη/feature/βάρος έχει λόγο ύπαρξης.
- **Honest limitations** — η άμυνα πιάνεται αδύναμα από τα box-score stats· τα defensive traits θα έχουν τα περισσότερα λάθη, και αυτό τεκμηριώνεται αντί να κρύβεται.
- **Επεκτασιμότητα χωρίς over-engineering** — multi-league αργότερα, καθαρά, χωρίς να περιπλέκουμε το τώρα.
