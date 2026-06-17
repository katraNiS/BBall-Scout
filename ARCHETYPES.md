# NBA Scouting Tool — Archetype Specification

Primitive Traits & Compound Archetypes

---

## 1. Σύστημα: compositional archetypes

Αντί για fixed, αλληλοαποκλειόμενα archetypes, ο κάθε παίκτης περιγράφεται ως **συνδυασμός ατομικών δεξιοτήτων** (primitive traits). Κάθε trait είναι ένα μετρήσιμο profile από weighted signals πάνω σε διαθέσιμα stats. Ο classifier δίνει σε κάθε παίκτη ένα score ανά trait· όσα ξεπερνούν ένα threshold "ανάβουν", και ο συνδυασμός τους σχηματίζει το compound archetype.

**Πλεονεκτήματα:** ταιριάζει με την πραγματικότητα (οι παίκτες είναι πολυδιάστατοι), δεν υπάρχει combinatorial explosion (N traits → 2^N συνδυασμοί δωρεάν), και δίνει το ίδιο feature space για το matching engine.

---

## 2. Τα 18 primitive traits

**Κατεύθυνση:** ↑ = θέλουμε υψηλό, ↓ = θέλουμε χαμηλό. `pos-rel` = κρίνεται position-relative (π.χ. υψηλό _για center_). Τα αριθμητικά βάρη συντονίζονται με το validation set.

### A. Creation & on-ball scoring

| Trait | Positions | Primary signals | Secondary signals |
|---|---|---|---|
| `on_ball_creator` | PG/SG/SF/PF | `usg_pct`↑, `pts`↑ | `fta`↑, `ast`↑ |
| `slasher` | PG/SG/SF/PF | `fta`↑, `fg_pct`↑ | `pts`↑, `fg3a`↓ |
| `midrange_scorer` *(fine)* | SG/SF/PF | `pts`↑, `fg3a`↓ | `efg_pct` ~avg, `fta` ~mid · weak signal |

### B. Shooting (off-ball)

| Trait | Positions | Primary signals | Secondary signals |
|---|---|---|---|
| `spot_up_shooter` | SG/SF/PF | `fg3_pct`↑, `fg3a`↑ | `usg_pct`↓, `ts_pct`↑, `tov`↓ |
| `movement_shooter` *(fine)* | PG/SG | `fg3_pct`↑, `fg3a`↑ | `usg_pct`↑ (self-created) |

### C. Playmaking

| Trait | Positions | Primary signals | Secondary signals |
|---|---|---|---|
| `lead_playmaker` | PG/SG | `ast_pct`↑↑, `ast_to_ratio`↑ | `usg_pct`↑, `ast`↑ |
| `connective_passer` | SG/SF/PF | `ast_to_ratio`↑, `ast_pct` ~mid | `usg_pct` low-mid, `tov`↓ |
| `playmaking_big` | PF/C | `ast_pct`↑ (pos-rel), `ast_to_ratio`↑ | `pts`, `reb_pct` |

### D. Interior offense

| Trait | Positions | Primary signals | Secondary signals |
|---|---|---|---|
| `post_scorer` | PF/C | `usg_pct`↑ (big), `pts`↑ | `fta`↑, `fg3a`↓ |
| `roll_finisher` | C/PF | `fg_pct`↑↑ | `usg_pct`↓, `oreb`↑, `fg3a`↓, `ast_pct`↓ |
| `stretch_big` | PF/C | `fg3a`↑ (pos-rel), `fg3_pct`↑ | `ts_pct`↑ |

### E. Perimeter defense

| Trait | Positions | Primary signals | Secondary signals |
|---|---|---|---|
| `point_of_attack_defender` | PG/SG | `stl`↑, `def_rating`↓ | `usg_pct`↓ · defense = weak signal |
| `versatile_wing_defender` | SG/SF/PF | `def_rating`↓, `stl`+`blk` both | `wingspan_cm`↑, `height_cm`↑, `reb_pct` |

### F. Interior defense

| Trait | Positions | Primary signals | Secondary signals |
|---|---|---|---|
| `rim_protector` | C/PF | `blk`↑↑, `def_rating`↓ | `reb_pct`↑, `height_cm`↑, `wingspan_cm`↑, `fg3a`↓ |
| `help_defender` *(fine)* | SF/PF/C | `stl`+`blk`↑ (pos-rel), `def_rating`↓ | hardest to isolate · overlaps E/F |

### G. Rebounding

| Trait | Positions | Primary signals | Secondary signals |
|---|---|---|---|
| `defensive_rebounder` | PF/C/SF | `dreb_pct`↑ | `reb_pct`↑, `height_cm`/`weight_lbs`↑ |
| `offensive_rebounder` | C/PF | `oreb_pct`↑ | `fg_pct` (putbacks), `weight_lbs`↑ |

### H. Efficiency

| Trait | Positions | Primary signals | Secondary signals |
|---|---|---|---|
| `efficient_finisher` | any | `ts_pct`↑, `usg_pct`↓ | `fg_pct`↑, `tov`↓ |

---

## 3. Schema προσθήκες που χρειάζονται

Για να δουλέψουν σωστά κάποια signals, χρειάζονται τρεις επιπλέον στήλες στο `player_seasons`:

- **`oreb_pct` & `dreb_pct`** (χωριστά) — για διαχωρισμό `offensive_rebounder` από `defensive_rebounder`. Υπάρχουν στο Advanced API (`OREB_PCT`, `DREB_PCT`).
— για υπολογισμό **3PA rate** (`fg3a/fga`) και **FT rate** (`fta/fga`), πιο σωστοί δείκτες από τα raw νούμερα. Κρίσιμο για τον διαχωρισμό `slasher` από shooters.

---

## 4. Compound archetypes

~29 σύνθετα archetypes που καλύπτουν guards, wings και bigs, και στις δύο άκρες. Λειτουργούν ως **named presets**: όταν τα traits ενός preset ανάβουν μαζί, ο παίκτης παίρνει το αντίστοιχο όνομα.

### Guards

| Archetype | Trait combination | Real players |
|---|---|---|
| Floor General | `lead_playmaker` + `movement_shooter` | Haliburton, Chris Paul, Trae Young |
| Scoring Lead Guard | `on_ball_creator` + `lead_playmaker` + `midrange_scorer` | Luka Dončić, LaMelo Ball, Cade Cunningham |
| Two-Way Lead Guard | `on_ball_creator` + `lead_playmaker` + `point_of_attack_defender` | Shai Gilgeous-Alexander, Jrue Holiday |
| Pure Point Guard | `lead_playmaker` + `connective_passer` | Mike Conley, Tyus Jones, late Chris Paul |
| Bucket-Getter (combo guard) | `on_ball_creator` + `movement_shooter` + `slasher` | Donovan Mitchell, Devin Booker |
| Instant Offense (6th man) | `on_ball_creator` + `movement_shooter` | Tyler Herro, Malik Monk, Norman Powell |
| Slashing Guard | `slasher` + `on_ball_creator` | Ja Morant, De'Aaron Fox, Anthony Edwards |
| 3-and-D Guard | `spot_up_shooter` + `point_of_attack_defender` | Derrick White, Marcus Smart, Lu Dort |
| Defensive Playmaker | `lead_playmaker` + `point_of_attack_defender` | Jrue Holiday, Derrick White |
| Sharpshooter | `movement_shooter` + `spot_up_shooter` + `efficient_finisher` | Stephen Curry, Klay Thompson, Damian Lillard |

### Wings

| Archetype | Trait combination | Real players |
|---|---|---|
| Two-Way Wing | `on_ball_creator` + `versatile_wing_defender` | Kawhi Leonard, Jayson Tatum, Paul George |
| Two-Way Slashing Star | `on_ball_creator` + `slasher` + `versatile_wing_defender` | Jaylen Brown, Anthony Edwards, Jimmy Butler |
| Wing Scorer / 3-Level Scorer | `on_ball_creator` + `midrange_scorer` + `movement_shooter` | Kevin Durant, DeMar DeRozan, Brandon Ingram |
| 3-and-D Wing | `spot_up_shooter` + `versatile_wing_defender` | OG Anunoby, Mikal Bridges, Herbert Jones, Jaden McDaniels |
| Point Forward | `on_ball_creator` + `lead_playmaker` + `versatile_wing_defender` | LeBron James, Scottie Barnes |
| Connector / Glue Wing | `connective_passer` + `spot_up_shooter` + `versatile_wing_defender` | Josh Hart, Andrew Nembhard, Royce O'Neale |
| Athletic Finisher Wing | `slasher` + `versatile_wing_defender` + `efficient_finisher` | Aaron Gordon, Andrew Wiggins |

### Bigs

| Archetype | Trait combination | Real players |
|---|---|---|
| Point Center | `playmaking_big` + `post_scorer` + `efficient_finisher` | Nikola Jokić, Domantas Sabonis, Alperen Şengün |
| Two-Way Scoring Big | `post_scorer` + `rim_protector` | Joel Embiid, Anthony Davis |
| Stretch Big | `stretch_big` + `efficient_finisher` | Karl-Anthony Towns, Lauri Markkanen, Kristaps Porziņģis |
| Stretch Rim Protector | `stretch_big` + `rim_protector` | Brook Lopez, Jaren Jackson Jr., Myles Turner |
| Rim-Running Anchor | `rim_protector` + `roll_finisher` + `defensive_rebounder` | Rudy Gobert, Walker Kessler, Daniel Gafford, Clint Capela |
| Pure Defensive Center | `rim_protector` + `defensive_rebounder` | Jakob Poeltl, Mitchell Robinson |
| Playmaking Rim Protector | `playmaking_big` + `rim_protector` + `help_defender` | Draymond Green, Bam Adebayo |
| Versatile / Swiss-Army Big | `playmaking_big` + `versatile_wing_defender` + `stretch_big` | Bam Adebayo, Al Horford |
| Energy Big | `offensive_rebounder` + `roll_finisher` + `help_defender` | Steven Adams, Nic Claxton, Isaiah Hartenstein |
| Throwback Post Hub | `post_scorer` + `offensive_rebounder` | Jonas Valančiūnas, Nikola Vučević |
| Stretch Four / Combo Forward | `stretch_big` + `spot_up_shooter` + `versatile_wing_defender` | Aaron Gordon, Naz Reid, Grant Williams |
| Modern Two-Way Forward | `stretch_big` + `slasher` + `versatile_wing_defender` | Pascal Siakam, Julius Randle, Paolo Banchero |

---

## 5. Naming logic & unicorns

Αν ένας παίκτης ταιριάζει σε named preset, παίρνει το όνομά του. Αλλιώς πέφτει στο γενικό **compound naming**: noun = το trait με το υψηλότερο score, modifier = το δεύτερο (σε επιθετική μορφή).

> Παράδειγμα: Draymond Green → `rim_protector` (noun) + `playmaker` (→ "Playmaking") = **"Playmaking Rim Protector"**

**Unicorns:** παίκτες με 3+ traits να ανάβουν ταυτόχρονα. Ο Victor Wembanyama είναι `stretch_big` + `rim_protector` + `on_ball_creator` — σχεδόν μοναδικός συνδυασμός. Αυτό είναι feature: ο classifier τον δείχνει με πολλαπλά ενεργά traits.

---

## 6. Σημειώσεις & περιορισμοί

- **Άμυνα = αδύναμο σήμα.** Τα `stl`/`blk`/`def_rating` πιάνουν φτωχά την πραγματική αμυντική αξία. Τα defensive traits (`point_of_attack_defender`, `versatile_wing_defender`, `rim_protector`, `help_defender`) θα έχουν τα περισσότερα λάθη.
- **Position-relative normalization.** Για bigs, το `ast_pct`/`fg3a` κρίνεται ως προς τη θέση — αλλιώς κανένας big δεν φαίνεται "shooter".
- **Threshold tuning.** Το όριο ενεργοποίησης ενός trait είναι παράμετρος: πολύ χαμηλό → όλοι έχουν 5 traits· πολύ υψηλό → οι μισοί κανένα. Συντονίζεται εμπειρικά.
- **Validation = multi-label.** Για κάθε γνωστό παίκτη ορίζεται το σετ traits που πρέπει να ανάψουν· μετράμε precision & recall ανά trait.
