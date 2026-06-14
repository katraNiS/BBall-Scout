# NBA Scouting Tool

## Τι είναι το project

Scouting εργαλείο (όχι quiz). Ο χρήστης ορίζει ένα **custom player profile** —
stats + physical attributes + archetype — και το σύστημα επιστρέφει τους
**πιο όμοιους πραγματικούς παίκτες** από τη βάση, με explainability (γιατί ταιριάζει).
Ο χρήστης μπορεί να δώσει και **βάρη** (π.χ. 3P% × 3).

Πιθανή πτυχιακή. Προτεραιότητα στην **ακρίβεια και τη λογική τεκμηρίωση** κάθε
απόφασης — όχι σε γρήγορες λύσεις χωρίς αιτιολόγηση.

**Scope τώρα:** μόνο NBA. Η επεκτασιμότητα (NCAA, G-League, EuroLeague, EuroCup)
έρχεται αργότερα — το design πρέπει να την επιτρέπει χωρίς rewrite.

## Συνοδευτικά αρχεία τεκμηρίωσης

- `README.md` — human-facing επισκόπηση (στόχοι, status, roadmap).
- `archetype_spec.md` — **ΤΟ ΠΛΗΡΕΣ SPEC των archetypes** (18 primitives + 29 compounds
  με signals & players). Συμβουλέψου το όταν φτιάχνεις `traits.py` / `presets.py`.
- `CLAUDE.md` (αυτό) — οδηγίες/context για το Claude Code.

---

## Tech Stack

- **Language:** Python
- **Backend:** FastAPI (αργότερα) — προς το παρόν scripts
- **Frontend:** Streamlit (πρώτο prototype)
- **Database:** PostgreSQL + SQLAlchemy ORM
- **ML/Math:** scikit-learn, pandas, numpy
- **Data sources:** nba_api (Python lib) + Kaggle NBA Draft Combine dataset

---

## Αρχιτεκτονική — 4 Layers

```
[ Data Layer ]        → nba_api, Kaggle CSV
      ↓
[ Processing Layer ]  → normalization, feature engineering, trait scoring
      ↓
[ Matching Engine ]   → cosine similarity + weighted scoring + archetype filter
      ↓
[ Web App Layer ]     → Streamlit UI, αποτελέσματα + explanations
```

---

## Database Schema (NBA-only, τρέχουσα έκδοση)

Normalized σχεδιασμός — δεν επαναλαμβάνουμε δεδομένα. 4 tables.

### `players` — βιογραφικά + physical (ένα row ανά παίκτη)
- `id` PK, `nba_api_id` (unique), `full_name`
- `height_cm` (μετατροπή από string "6-9"), `weight_lbs`, `wingspan_cm` (από Kaggle)
- `primary_position`, `secondary_position` (2 ξεχωριστές στήλες)
- `nationality`, `birth_date`, `draft_year`, `draft_round`, `draft_pick`

### `teams`
- `id` PK, `nba_team_id` (unique), `name`, `abbreviation`, `city`

### `builds` — (legacy metadata πίνακας· βλ. σημείωση archetypes παρακάτω)
- `id` PK, `name`, `display_name`, `description`, `position_profile`

### `player_seasons` — κεντρικός πίνακας (row ανά παίκτη × σεζόν × ομάδα)
- FKs: `player_id`, `team_id`, `build_id`
- `season`, `age`, `games_played`, `games_started`, `minutes_pg`
- Box: `pts`, `reb`, `ast`, `stl`, `blk`, `tov`, `oreb`, `dreb`, `plus_minus`
- Shooting: `fg_pct`, `fg3_pct`, `fg3a`, `ft_pct`, `fta`
- Advanced: `ts_pct`, `usg_pct`, `ast_pct`, `reb_pct`, `off_rating`,
  `def_rating`, `net_rating`, `pie`, `efg_pct`
- Computed: `build_archetype`, `versatility_score`
- UniqueConstraint: (`player_id`, `season`, `team_id`)

### ⚠️ SCHEMA ADDITIONS ΠΟΥ ΧΡΕΙΑΖΟΝΤΑΙ (αποφασισμένο, μη υλοποιημένο)
Για να δουλέψουν τα trait signals, πρόσθεσε στο `player_seasons`:
- `oreb_pct` & `dreb_pct` (χωριστά) — για διαχωρισμό offensive/defensive rebounder.
  Υπάρχουν στο Advanced API (`OREB_PCT`, `DREB_PCT`).
- `fga` — για 3PA rate (`fg3a/fga`) & FT rate (`fta/fga`). Κρίσιμο για slasher vs shooters.

---

## ARCHETYPE SYSTEM — compositional (ΤΟ ΚΕΝΤΡΙΚΟ DESIGN)

> ⚠️ ΕΞΕΛΙΞΗ: Το αρχικό design είχε ~10 fixed, αλληλοαποκλειόμενα archetypes
> (στο `engine/archetypes.py`, 1η έκδοση). ΑΥΤΟ ΑΝΤΙΚΑΘΙΣΤΑΤΑΙ από το παρακάτω
> compositional σύστημα. Πλήρεις ορισμοί με signals & players στο `archetype_spec.md`.

### Η ιδέα
Κάθε παίκτης = **συνδυασμός ατομικών δεξιοτήτων** (primitive traits), όχι ένα κουτί.
Κάθε trait έχει profile από weighted signals πάνω σε stats. Ο classifier δίνει
score ανά trait· όσα ξεπερνούν threshold "ανάβουν"· ο συνδυασμός = compound archetype.
N traits → 2^N συνδυασμοί δωρεάν. Ίδιο feature space με το matching engine.

### Τα 18 primitive traits (ομάδες A–H)
- **A. Creation/scoring:** `on_ball_creator`, `slasher`, `midrange_scorer`(fine)
- **B. Shooting:** `spot_up_shooter`, `movement_shooter`(fine)
- **C. Playmaking:** `lead_playmaker`, `connective_passer`, `playmaking_big`
- **D. Interior offense:** `post_scorer`, `roll_finisher`, `stretch_big`
- **E. Perimeter D:** `point_of_attack_defender`, `versatile_wing_defender`
- **F. Interior D:** `rim_protector`, `help_defender`(fine)
- **G. Rebounding:** `defensive_rebounder`, `offensive_rebounder`
- **H. Efficiency:** `efficient_finisher`

Κάθε trait: positions (eligibility) + signals (stat→weight, πρόσημο=κατεύθυνση).
ΠΡΟΣΟΧΗ: `def_rating` χαμηλό = καλή άμυνα (άρα αρνητικό weight όπου θέλουμε D).
Για bigs, `ast_pct`/`fg3a` κρίνονται **position-relative**. (Σήματα ανά trait: `archetype_spec.md`.)

### Compound archetypes (~29 named presets)
Συνδυασμοί 2-3 traits που αντιστοιχούν σε πραγματικούς τύπους. Παραδείγματα:
- Floor General = `lead_playmaker` + `movement_shooter` (Haliburton)
- 3-and-D Wing = `spot_up_shooter` + `versatile_wing_defender` (OG Anunoby)
- Point Center = `playmaking_big` + `post_scorer` + `efficient_finisher` (Jokić)
- Playmaking Rim Protector = `playmaking_big` + `rim_protector` + `help_defender` (Draymond)
- Rim-Running Anchor = `rim_protector` + `roll_finisher` + `defensive_rebounder` (Gobert)
(Πλήρης λίστα guards/wings/bigs στο `archetype_spec.md`.)

### Naming logic
Αν ταιριάζει σε preset → όνομα preset. Αλλιώς: noun = trait με υψηλότερο score,
modifier = #2 (επιθετική μορφή). Π.χ. Draymond → "Playmaking Rim Protector".
Unicorns = 3+ traits μαζί (π.χ. Wembanyama: stretch_big + rim_protector + on_ball_creator).

---

## Matching Engine (design — δεν έχει υλοποιηθεί)

Συνδυασμός 3 μεθόδων:
1. **Cosine similarity** σε normalized stats/trait vector.
2. **Weighted scoring** από τον χρήστη (weights πριν το similarity).
3. **Archetype filter/boost** βάσει trait match.
Κάθε αποτέλεσμα → **explanation** (ποια features οδήγησαν στο match).

---

## Project structure

```
scouting_tool/
├── README.md                  ← επισκόπηση project              [DONE]
├── CLAUDE.md                  ← αυτό το αρχείο
├── archetype_spec.md          ← πλήρες spec archetypes          [DONE]
├── db/
│   ├── models.py              ← SQLAlchemy models               [DONE]
│   └── init_db.py             ← create tables + seed            [DONE]
├── data_exploration/
│   └── explore_nba_api.py     ← API exploration                 [DONE]
├── engine/
│   ├── validation_set.py      ← ground truth για testing        [DONE]
│   ├── archetypes.py          ← 1η έκδοση (fixed) — LEGACY
│   ├── traits.py              ← 18 primitives                   [TODO]
│   ├── presets.py             ← 29 compounds                    [TODO]
│   ├── classifier.py          ← trait scoring & assignment      [TODO]
│   └── matcher.py             ← similarity + weights + filter   [TODO]
├── pipeline/
│   └── fetch_nba_data.py      ← fetch + merge + load            [TODO]
└── app/
    └── streamlit_app.py       ← UI                              [TODO]
```

---

## Κατάσταση (τι έχει γίνει)

- [x] Ιδέα & scope (NBA-only πρώτα)
- [x] API exploration — ξέρουμε τι δίνει το nba_api
- [x] Schema design (4 tables, normalized)
- [x] `db/models.py`, `db/init_db.py`
- [x] `engine/validation_set.py` — ground truth παικτών
- [x] Archetype design: 18 primitives + 29 compounds (compositional)
- [x] `archetype_spec.md`, `README.md`
- [ ] Schema update: `oreb_pct`, `dreb_pct`, `fga`
- [ ] `engine/traits.py` (από το spec)
- [ ] `engine/presets.py` (από το spec)
- [ ] Data pipeline (fetch + merge + load)
- [ ] Trait classifier + multi-label validation
- [ ] Matching engine
- [ ] Streamlit UI

---

## Επόμενα βήματα (σειρά)

1. **Schema update** — πρόσθεσε `oreb_pct`, `dreb_pct`, `fga` στο `models.py`.
2. **`traits.py`** — κωδικοποίησε τα 18 primitives από το `archetype_spec.md`
   (positions + signals με πρόσημο=κατεύθυνση).
3. **`presets.py`** — τα 29 compounds (σετ traits → όνομα).
4. **Pipeline** — fetch (CommonPlayerInfo + LeagueDashPlayerStats Base & Advanced),
   parse height "6-9"→cm, merge wingspan από Kaggle, load DB.
   **Rate limiting: `time.sleep(~1.5s)` ανά API call.**
5. **Classifier** — z-score normalization (position-relative για bigs), trait scoring,
   threshold tuning στο `validation_set.py` (multi-label: precision/recall ανά trait).
6. **Matcher → Streamlit UI.**

---

## Συμβάσεις / Conventions

- Σχόλια & εξηγήσεις: στα Ελληνικά, technical terms στα Αγγλικά.
- Ζητούμενο: **ακρίβεια + αιτιολόγηση**. Εξήγησε το "γιατί" πίσω από κάθε επιλογή.
- Κάθε νέα στήλη/feature/βάρος: σκέψου αν επηρεάζει το matching ή είναι noise.
- Κράτα το design **επεκτάσιμο** (multi-league αργότερα) χωρίς over-engineering τώρα.
- **Άμυνα = αδύναμο σήμα** (stl/blk/def_rating). Τα defensive traits θα έχουν τα
  περισσότερα λάθη — αυτό τεκμηριώνεται, δεν κρύβεται.
- Το nba_api ΔΕΝ είναι προσβάσιμο από sandboxed περιβάλλοντα — τρέχει μόνο τοπικά.
