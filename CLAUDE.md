# NBA Scouting Tool — CLAUDE.md

## Τι είναι το project

Scouting εργαλείο (όχι quiz). Ο χρήστης ορίζει ένα **custom player profile** —
stats + βάρη ανά stat + επιθυμητά traits — και το σύστημα επιστρέφει τους
**πιο όμοιους πραγματικούς παίκτες** από τη βάση, με explainability.

Πτυχιακή. Προτεραιότητα στην **ακρίβεια και τη λογική τεκμηρίωση** κάθε
απόφασης — όχι σε γρήγορες λύσεις χωρίς αιτιολόγηση.

**Scope τώρα:** μόνο NBA. Η επεκτασιμότητα (NCAA, G-League, EuroLeague, EuroCup)
έρχεται αργότερα — το design πρέπει να την επιτρέπει χωρίς rewrite.

## Συνοδευτικά αρχεία τεκμηρίωσης

- `README.md` — human-facing επισκόπηση (στόχοι, status, roadmap).
- `archetype_spec.md` — **ΤΟ ΠΛΗΡΕΣ SPEC των archetypes** (18 primitives + 29 compounds
  με signals & players). Συμβουλέψου το όταν αγγίζεις `src/archetypes.py`.
- `CLAUDE.md` (αυτό) — οδηγίες/context για το Claude Code.

---

## Tech Stack

- **Language:** Python
- **Frontend:** Streamlit
- **Data storage:** CSV flat file (`data/nba_stats_full.csv`) — χωρίς DB προς το παρόν
- **ML/Math:** scikit-learn, pandas, numpy
- **Data sources:** nba_api (Python lib) — box/advanced/scoring/hustle endpoints

> Δεν υπάρχει PostgreSQL/SQLAlchemy στο παρόν στάδιο. Τα `db/` αρχεία είναι
> legacy από πρώιμο design — αγνόησέ τα.

---

## Αρχιτεκτονική — 4 Layers

```
[ Data Layer ]        → nba_api endpoints → CSV
      ↓
[ Processing Layer ]  → normalization, z-scores, tiered MPG filter
      ↓
[ Archetype Layer ]   → 18 primitive traits → classifier → 29 compound presets
      ↓
[ Matching Engine ]   → weighted L2 distance + trait boost + explanations
      ↓
[ Web App Layer ]     → Streamlit UI, stat builder, result cards
```

---

## Project structure (τρέχουσα)

```
BBall-Scout/
├── README.md
├── CLAUDE.md                  ← αυτό
├── archetype_spec.md          ← spec archetypes [DONE]
├── data/
│   └── nba_stats_full.csv     ← merged dataset (~30k rows, δεν είναι στο git)
├── pipeline/
│   └── fetch_nba_data.py      ← 3-phase fetch: base+advanced / scoring / hustle [DONE]
├── src/
│   ├── preprocessing.py       ← load/clean/normalize, FEATURE_COLS, preprocess() [DONE]
│   ├── archetypes.py          ← 18 traits + signals + 29 compound presets + classify() [DONE]
│   └── similarity.py          ← find_similar(), explain_match() [DONE]
└── app/
    └── streamlit_app.py       ← Streamlit UI [DONE]
```

---

## Data pipeline (`pipeline/fetch_nba_data.py`)

3 phases:

**Phase 1a — Base + Advanced** (`LeagueDashPlayerStats`, measure_type="Base" + "Advanced"):
- Box: `pts`, `reb`, `ast`, `stl`, `blk`, `tov`, `oreb`, `dreb`, `min`, `gp`
- Advanced: `ts_pct`, `usg_pct`, `ast_pct`, `oreb_pct`, `dreb_pct`, `net_rating`, `efg_pct`, `ast_to`, `reb_pct`
- `CommonPlayerInfo` → `height_cm`, `weight_lbs`, `position`

**Phase 1b — Scoring** (`LeagueDashPlayerStats`, measure_type="Scoring"):
- `pct_pts_2pt_mr` (API: `PCT_PTS_2PT_MR`) — % points from mid-range, κρίσιμο για midrange_scorer
- `pct_fga_3pt`, `pct_pts_3pt`, `pct_pts_paint`, `pct_pts_ft`, `pct_uast_2pm`

**Phase 1c — Hustle** (`LeagueHustleStatsPlayer`, 2015-16+):
- `deflections`, `charges_drawn`, `box_outs`, `screen_assists`
- Παλαιότερες σεζόν: NaN → group median (z ≈ 0, neutral)

**Rate limiting:** `time.sleep(1.5)` ανά call. Trade dedup: κράτα row με max games.

---

## Data format — ΚΡΙΣΙΜΟ

Τα παρακάτω αποθηκεύονται ως **fractions (0.0–1.0)**, ΟΧΙ percentages:
`usg_pct`, `ts_pct`, `efg_pct`, `fg3_pct`, `ft_pct`, `ast_pct`, `oreb_pct`, `dreb_pct`, `pct_pts_2pt_mr`

Π.χ. `ast_pct = 0.26` (26%). Αν περάσεις `26.0` στο `find_similar()` θα πάρεις z-score ~285.

Το Streamlit UI κάνει τη μετατροπή (×100 slider → ÷100 internal) αυτόματα.

---

## Preprocessing (`src/preprocessing.py`)

**`FEATURE_COLS`** (20 features για similarity):
```
pts, usg_pct, ts_pct, efg_pct,
fg3a, fg3_pct, fta, ft_pct, pct_pts_2pt_mr,
ast_pct, ast_to, tov,
oreb_pct, dreb_pct,
stl, blk, deflections,
net_rating, height_cm, weight_lbs
```

**Tiered MPG filter:**
- 1996–2012: ≥ 20 MPG (pre-tracking era, λείπουν hustle stats)
- 2013+: ≥ 10 MPG (full data, κρατάμε specialists)
- Min games: ≥ 20 GP

**NaN handling:**
- `deflections` κ.α. hustle cols pre-2015: position_group median
- `fg3_pct` / `ft_pct` με 0 attempts: 0.0
- `ast_to` όταν ast=0: 0.0

**Output:** `preprocess()` → `(df_clean, feature_matrix, scaler)` — fitted `StandardScaler`.

---

## ARCHETYPE SYSTEM — compositional

### Τα 18 primitive traits (ομάδες A–H)
- **A. Creation/scoring:** `on_ball_creator`, `slasher`, `midrange_scorer`
- **B. Shooting:** `spot_up_shooter`, `movement_shooter`
- **C. Playmaking:** `lead_playmaker`, `connective_passer`, `playmaking_big`
- **D. Interior offense:** `post_scorer`, `roll_finisher`, `stretch_big`
- **E. Perimeter D:** `point_of_attack_defender`, `versatile_wing_defender`
- **F. Interior D:** `rim_protector`, `help_defender`
- **G. Rebounding:** `defensive_rebounder`, `offensive_rebounder`
- **H. Efficiency:** `efficient_finisher`

Κάθε trait: `positions` (eligibility) + `signals` (stat + weight + κατεύθυνση + `pos_rel`).
- `pos_rel=True` → z-score vs position group (bigs) αντί global — για `ast_pct`, `fg3a`, `stl`, `blk` σε bigs.
- `def_rating` χαμηλό = καλή άμυνα → **αρνητικό** weight.
- `fine=True` → χαμηλότερο threshold (0.35 αντί 0.5) για rarer traits.

### Classifier logic (`classify()`)
1. Z-score ανά feature (global ή position-relative).
2. Trait score = weighted sum των signals.
3. Threshold: score > 0.5 → trait active (fine traits: 0.35).
4. Compound: βρες το preset με τo μεγαλύτερο subset των active traits.
5. Αν κανένα preset → fallback: noun (top score trait) + modifier (2nd).

### PRESET_POSITIONS — position-aware scoring
Κάθε preset έχει επιτρεπτά position groups (`PRESET_POSITIONS` dict, ~27 entries).
Στο `_label_archetype()`, το score είναι tuple `(pos_ok, trait_count)`:
- `pos_ok = 1` αν η θέση του παίκτη είναι στη λίστα, `0` αλλιώς.
- Primary tiebreaker: position match. Secondary: trait count. Tertiary: dict ordering.

Γιατί: χωρίς αυτό, ο Porzingis (F-C) → "Slashing Guard" επειδή τα guard presets ήρθαν πρώτα στο dict με ίσο trait count.

### Dict ordering για τριτεύον tie-breaking
Αν `(pos_ok, trait_count)` ισοπαλούν, κερδίζει το preset που εμφανίζεται **πρώτο** στο dict.
Π.χ. "Point Center" πριν "All-Around Forward" ώστε ο Giannis/Embiid → Point Center.

### Παραδείγματα (validation):
- Curry → Floor General / Two-Way Lead Guard ✓
- Jokić → Point Center ✓
- Draymond → Playmaking Rim Protector ✓
- OG Anunoby → Two-Way Sharpshooter ✓
- Gobert → Rim-Running Anchor ✓
- LeBron → All-Around Forward ✓

---

## Matching Engine (`src/similarity.py`)

**Metric:** Weighted RMS distance (masked):
```
distance = sqrt(Σ w_j × (user_z_j - player_z_j)² / Σ w_j)   [only specified features]
similarity = 1 / (1 + distance)   →   (0, 1]
```

Χρησιμοποιούμε L2 (όχι cosine) γιατί ζητάμε «βρες παίκτες ΚΟΝΤΑ σε αυτές τις τιμές».
Cosine κανονικοποιεί τον |player| vector — τιμωρεί αδίκως extreme players σε unspecified dims.
`1/(1+d)` αντί `exp(-d)` γιατί z-score distances είναι φυσικά μεγάλα (~4-15), το exp(-8)≈0 δεν δίνει range.

**Weighted RMS (scale-invariant):** Διαιρούμε με `Σ w_j` ώστε το distance να μην αυξάνεται
όσο ο χρήστης ορίζει περισσότερα stats. Χωρίς normalization, 6 stats με diff=0.5 δίνουν
`sqrt(6×0.25)≈1.22` αντί `sqrt(0.25)=0.5` → similarity 45% αντί 67%.

**Trait boost:** `+0.004` ανά shared active trait — tiebreaker μόνο, δεν κυριαρχεί.

**Best season:** groupby player_id, κράτα σεζόν με max final_score.

**Season range:** "2010-2025" → φιλτράρει rows κατά start year.

---

## Κατάσταση (τι έχει γίνει)

- [x] Ιδέα & scope
- [x] API exploration
- [x] Archetype design: 18 primitives + 29 compounds + `archetype_spec.md`
- [x] `pipeline/fetch_nba_data.py` — 3-phase fetch (base/advanced/scoring/hustle)
- [x] `src/preprocessing.py` — tiered MPG, NaN handling, z-scores
- [x] `src/archetypes.py` — trait signals + compound presets + classifier + PRESET_POSITIONS
- [x] `src/similarity.py` — weighted RMS matching + pct_cols output + explanations
- [x] `src/preprocessing.py` — percentile matrix (`build_percentile_matrix`, `stat_to_percentile`)
- [x] `app/streamlit_app.py` — Streamlit UI (stat builder + result cards + radar chart)
- [x] Validation: 20 παίκτες (stars + role players)
- [ ] Classifier threshold tuning (precision/recall ανά trait)
- [ ] UI: φίλτρο ανά position, export αποτελεσμάτων σε CSV
- [ ] FastAPI backend (αντί scripts)
- [ ] Multi-league support

---

## Επόμενα βήματα

1. **Threshold tuning** — τρέξε validation set, μέτρα precision/recall ανά trait, adjust.
2. **UI polish** — φίλτρο ανά position, export αποτελεσμάτων σε CSV.
3. **FastAPI backend** — `POST /similar` endpoint αντί direct function calls.
4. **Multi-league** — NCAA, EuroLeague: νέο pipeline, ίδιο `src/`.

---

## Conventions

- Σχόλια & εξηγήσεις: στα Ελληνικά, technical terms στα Αγγλικά.
- Ζητούμενο: **ακρίβεια + αιτιολόγηση**. Εξήγησε το "γιατί" πίσω από κάθε επιλογή.
- Κάθε νέα στήλη/feature/βάρος: σκέψου αν επηρεάζει το matching ή είναι noise.
- Κράτα το design **επεκτάσιμο** (multi-league αργότερα) χωρίς over-engineering τώρα.
- **Άμυνα = αδύναμο σήμα** — τα defensive traits θα έχουν τα περισσότερα λάθη. Αυτό τεκμηριώνεται, δεν κρύβεται.
- Το nba_api ΔΕΝ είναι προσβάσιμο από sandboxed περιβάλλοντα — τρέχει μόνο τοπικά.
- **Πριν κάθε commit:** update README.md + CLAUDE.md να αντικατοπτρίζουν την τρέχουσα κατάσταση.