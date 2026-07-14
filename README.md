# ProspectMatch

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
                                         (18 primitives → 36 compound presets)
                                                    ↓
                                         src/similarity.py
                                         (weighted L2 matching + explanations)
                                                    ↓
                         ┌──────────────────────────┴──────────────────────────┐
                         ↓                                                       ↓
            backend/ (FastAPI API)                              app/streamlit_app.py
            /similar /classify /stats ...                       (legacy UI, λειτουργικό)
                         ↓
            frontend/ (React + Recharts)  ←  wrapped σε  →  electron/ (desktop app)
```

Το **desktop app** (Electron + FastAPI + React) είναι η κύρια κατεύθυνση· το Streamlit
UI παραμένει λειτουργικό και καταναλώνει το `src/` απευθείας. Ο πυρήνας `src/`
(preprocessing/archetypes/similarity) είναι κοινός και **αμετάβλητος** — ο FastAPI
backend τον _wrap-άρει_, δεν τον ξαναγράφει.

**Compositional archetypes:** αντί για ~10 fixed κουτιά, ορίζουμε **18 primitive traits** (π.χ. `slasher`, `rim_protector`, `lead_playmaker`) που συνδυάζονται αυτόματα σε **36 σύνθετα archetypes** (π.χ. `playmaking_big` + `rim_protector` + `help_defender` = "Playmaking Rim Protector"). Ο ίδιος feature space χρησιμοποιείται και για το matching.

**Similarity metric:** weighted L2 distance στο z-score space, masked μόνο στα stats που ο χρήστης όρισε. `1/(1+distance)` → score (0, 1].

Πλήρεις ορισμοί traits/compounds στο [`ARCHETYPES.md`](./ARCHETYPES.md).

---

## Tech stack

| Layer | Επιλογή |
|---|---|
| Core / Language | Python (`src/` — preprocessing, archetypes, similarity) |
| Backend API | FastAPI + uvicorn |
| Frontend | React 18 + TypeScript + Vite + Recharts |
| Desktop shell | Electron + electron-builder |
| Legacy UI | Streamlit (`app/streamlit_app.py`) |
| Data storage | CSV flat file (`data/nba_stats_full.csv`) |
| Data sources | nba_api (box + advanced + scoring + hustle), Kaggle (wingspan) |
| ML / Math | scikit-learn, pandas, numpy |

> Δεν χρησιμοποιούμε βάση δεδομένων στο παρόν στάδιο — το CSV είναι αρκετό.
> PostgreSQL/SQLAlchemy παραμένει επιλογή για αργότερα.
>
> Πλήρες setup/run/build του desktop stack: **[`DEVELOPMENT.md`](./DEVELOPMENT.md)**.

---

## Κατάσταση project

- [x] Ορισμός ιδέας & scope (NBA-only πρώτα)
- [x] API exploration — ξέρουμε ακριβώς τι fields δίνει το `nba_api`
- [x] Archetype design: 18 primitives + 36 compound presets (`src/archetypes.py`· spec `ARCHETYPES.md`)
- [x] Data pipeline — box/advanced + scoring (PCT_PTS_2PT_MR κ.α.) + hustle (deflections κ.α.)
- [x] `src/preprocessing.py` — normalization, tiered MPG filter, z-scores
- [x] `src/archetypes.py` — trait signals + compound presets + classifier
- [x] `src/similarity.py` — weighted L2 matching, trait boost, explanations
- [x] `app/streamlit_app.py` — working Streamlit UI
- [x] Validation: 20 γνωστοί παίκτες (stars + role players) — archetypes & similarity
- [x] Position-aware preset matching (`PRESET_POSITIONS`) — διορθώνει misclassification (π.χ. Porzingis → "Slashing Guard")
- [x] Scale-invariant similarity — weighted RMS αντί raw sum, αποφεύγει compression με πολλά stats
- [x] Radar chart (percentile 0–100) — StatsBomb-style, player vs user target, `plotly`
- [x] Validation harness (`validation/`) — 72 labeled παίκτες, per-trait precision/recall/F1, threshold sweep → `REPORT.md`
- [x] **FastAPI backend** (`backend/`) — 6 endpoints (`/similar`, `/classify`, `/stats`, `/archetypes`, …), wrap-άρει το `src/` αμετάβλητο
- [x] **React frontend** (`frontend/`) — stat builder + result cards + Recharts radar (TypeScript)
- [x] **Electron desktop app** (`electron/`) — `npm run dev` (backend+frontend+electron μαζί), `npm run dist`
- [ ] Classifier tuning (structural eligibility bugs → trait over-firing weights → eval hardening)
- [ ] UI: φίλτρο ανά position, export αποτελεσμάτων σε CSV
- [ ] Sync `ARCHETYPES.md` (29) με τον κώδικα (36 presets)
- [ ] Self-contained bundle (PyInstaller backend exe)
- [ ] Multi-league support (NCAA, EuroLeague κ.α.)

---

## Δομή αρχείων

```
ProspectMatch/
├── README.md                  ← αυτό το αρχείο
├── CLAUDE.md                  ← context/οδηγίες για το Claude Code
├── ARCHETYPES.md              ← πλήρες spec των archetypes (traits + compounds)
├── DEVELOPMENT.md             ← setup/run/build του desktop stack
├── package.json               ← root: npm run dev / npm run dist
├── data/
│   └── nba_stats_full.csv     ← merged dataset (δεν είναι στο git)
├── pipeline/
│   └── fetch_nba_data.py      ← fetch nba_api → CSV  [DONE]
├── src/                       ← κοινός πυρήνας, ΑΜΕΤΑΒΛΗΤΟΣ
│   ├── preprocessing.py       ← load, clean, normalize  [DONE]
│   ├── archetypes.py          ← trait signals + presets + classifier  [DONE]
│   └── similarity.py          ← matching engine  [DONE]
├── backend/                   ← FastAPI API (wrap-άρει το src/)  [DONE]
├── frontend/                  ← React + TS + Vite + Recharts  [DONE]
├── electron/                  ← desktop shell (spawn backend + load UI)  [DONE]
└── app/
    └── streamlit_app.py       ← Streamlit UI (legacy, λειτουργικό)  [DONE]
```

---

## Setup

**Data (μία φορά, τρέχει μόνο τοπικά — nba_api δεν λειτουργεί σε sandbox):**
```bash
pip install nba_api pandas scikit-learn numpy
python pipeline/fetch_nba_data.py     # → data/nba_stats_full.csv
```

**Desktop app (Electron + FastAPI + React) — κύρια κατεύθυνση:**
```bash
pip install -r backend/requirements.txt
npm install            # root: electron toolchain + (postinstall) frontend deps
npm run dev            # backend + Vite + Electron μαζί (concurrently)
```
Λεπτομέρειες, build & troubleshooting: **[`DEVELOPMENT.md`](./DEVELOPMENT.md)**.

**Ή μόνο το backend API:**
```bash
cd backend && uvicorn main:app --reload      # → http://127.0.0.1:8000/docs
```

**Ή το legacy Streamlit UI:**
```bash
pip install streamlit plotly
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