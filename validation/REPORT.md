# Classifier Validation Report

- Labeled players resolved: **72/72**
- Current threshold (src): **0.6** — macro-F1 **0.601**, archetype top-1 **21/72 (0.292)**
- Best global threshold (macro-F1): **0.75** — macro-F1 **0.607**, archetype top-1 **18/72 (0.250)**

## Per-trait metrics @ threshold 0.6 (worst F1 first)

| Trait | Precision | Recall | F1 | Support | Best thr (F1) |
|---|---|---|---|---|---|
| slasher | 0.400 | 0.333 | 0.364 | 12 | 0.4 (0.581) |
| efficient_finisher | 0.385 | 0.417 | 0.400 | 12 | 0.8 (0.588) |
| versatile_wing_defender | 0.538 | 0.350 | 0.424 | 20 | 0.3 (0.486) |
| midrange_scorer | 0.667 | 0.333 | 0.444 | 6 | 0.3 (0.600) |
| point_of_attack_defender | 0.308 | 0.800 | 0.444 | 5 | 0.55 (0.444) |
| help_defender | 0.375 | 0.600 | 0.462 | 5 | 0.55 (0.462) |
| connective_passer | 0.333 | 1.000 | 0.500 | 4 | 0.5 (0.500) |
| movement_shooter | 0.458 | 0.917 | 0.611 | 12 | 0.9 (0.625) |
| post_scorer | 0.667 | 0.571 | 0.615 | 7 | 0.75 (0.727) |
| spot_up_shooter | 0.556 | 0.714 | 0.625 | 14 | 0.8 (0.667) |
| lead_playmaker | 0.458 | 1.000 | 0.629 | 11 | 0.95 (0.667) |
| stretch_big | 0.462 | 1.000 | 0.632 | 12 | 0.9 (0.706) |
| on_ball_creator | 0.579 | 0.957 | 0.721 | 23 | 0.4 (0.721) |
| rim_protector | 0.769 | 0.769 | 0.769 | 13 | 0.3 (0.828) |
| offensive_rebounder | 0.625 | 1.000 | 0.769 | 5 | 0.75 (0.909) |
| roll_finisher | 0.636 | 1.000 | 0.778 | 7 | 0.95 (0.875) |
| defensive_rebounder | 0.667 | 1.000 | 0.800 | 6 | 0.75 (1.000) |
| playmaking_big | 0.833 | 0.833 | 0.833 | 6 | 0.8 (0.909) |

## Threshold sweep

| Threshold | Macro-F1 | Archetype top-1 |
|---|---|---|
| 0.3 | 0.562 | 12/72 (0.167) |
| 0.35 | 0.567 | 14/72 (0.194) |
| 0.4 | 0.570 | 15/72 (0.208) |
| 0.45 | 0.575 | 16/72 (0.222) |
| 0.5 | 0.587 | 19/72 (0.264) |
| 0.55 | 0.596 | 18/72 (0.250) |
| 0.6 ⬅ current | 0.601 | 21/72 (0.292) |
| 0.65 | 0.603 | 19/72 (0.264) |
| 0.7 | 0.601 | 18/72 (0.250) |
| 0.75 ⬅ best | 0.607 | 18/72 (0.250) |
| 0.8 | 0.606 | 17/72 (0.236) |
| 0.85 | 0.596 | 17/72 (0.236) |
| 0.9 | 0.600 | 17/72 (0.236) |
| 0.95 | 0.594 | 16/72 (0.222) |

## Structural misses @ 0.6 — expected trait είναι position-ineligible (5)

_Δεν διορθώνονται με threshold tuning — είναι θέμα trait eligibility/preset design._

- **Anthony Edwards** — expected `versatile_wing_defender` (μη eligible για τη θέση του)
- **Kevin Durant** — expected `movement_shooter` (μη eligible για τη θέση του)
- **Brandon Ingram** — expected `movement_shooter` (μη eligible για τη θέση του)
- **LeBron James** — expected `lead_playmaker` (μη eligible για τη θέση του)
- **Josh Hart** — expected `versatile_wing_defender` (μη eligible για τη θέση του)

## Archetype misclassifications @ 0.6 (51/72)

- **Tyrese Haliburton**: expected `Floor General` → got `Two-Way Lead Guard`
- **Luka Doncic**: expected `Scoring Lead Guard` → got `Two-Way Lead Guard`
- **LaMelo Ball**: expected `Scoring Lead Guard` → got `Floor General`
- **Cade Cunningham**: expected `Scoring Lead Guard` → got `Floor General`
- **Jrue Holiday**: expected `Two-Way Lead Guard` → got `Pure Point Guard`
- **Donovan Mitchell**: expected `Bucket-Getter` → got `Two-Way Lead Guard`
- **Tyler Herro**: expected `Instant Offense` → got `Floor General`
- **Malik Monk**: expected `Instant Offense` → got `Floor General`
- **Norman Powell**: expected `Instant Offense` → got `Sharpshooter`
- **Ja Morant**: expected `Slashing Guard` → got `Bucket-Getter`
- **De'Aaron Fox**: expected `Slashing Guard` → got `Two-Way Lead Guard`
- **Derrick White**: expected `3-and-D Guard` → got `Sharpshooter`
- **Marcus Smart**: expected `3-and-D Guard` → got `Defensive Playmaker`
- **Klay Thompson**: expected `Sharpshooter` → got `Pure Shooter`
- **Damian Lillard**: expected `Sharpshooter` → got `Two-Way Lead Guard`
- **Jayson Tatum**: expected `Two-Way Wing` → got `Floor General`
- **Paul George**: expected `Two-Way Wing` → got `Defensive Playmaking Big`
- **Jaylen Brown**: expected `Two-Way Slashing Star` → got `Instant Offense`
- **Anthony Edwards**: expected `Two-Way Slashing Star` → got `Instant Offense`
- **Kevin Durant**: expected `Wing Scorer` → got `Point Center`
- **DeMar DeRozan**: expected `Wing Scorer` → got `Scoring Lead Guard`
- **Brandon Ingram**: expected `Wing Scorer` → got `All-Around Forward`
- **Mikal Bridges**: expected `3-and-D Wing` → got `Sharpshooter`
- **Herbert Jones**: expected `3-and-D Wing` → got `Helping Wing Defender`
- **Jaden McDaniels**: expected `3-and-D Wing` → got `Helping Wing Defender`
- **Scottie Barnes**: expected `Point Forward` → got `Two-Way Lead Guard`
- **Josh Hart**: expected `Connector / Glue Wing` → got `Pure Point Guard`
- **Royce O'Neale**: expected `Connector / Glue Wing` → got `Stretch Big`
- **Aaron Gordon**: expected `Athletic Finisher Wing` → got `Stretch Big`
- **Andrew Wiggins**: expected `Athletic Finisher Wing` → got `Shooting Stretch Big`
- **Domantas Sabonis**: expected `Point Center` → got `All-Around Forward`
- **Alperen Sengun**: expected `Point Center` → got `Throwback Post Hub`
- **Joel Embiid**: expected `Two-Way Scoring Big` → got `Point Center`
- **Lauri Markkanen**: expected `Stretch Big` → got `Shooting Stretch Big`
- **Brook Lopez**: expected `Stretch Rim Protector` → got `Stretch Big`
- **Jaren Jackson Jr.**: expected `Stretch Rim Protector` → got `Modern Two-Way Forward`
- **Myles Turner**: expected `Stretch Rim Protector` → got `Stretch Big`
- **Clint Capela**: expected `Rim-Running Anchor` → got `Glass Cleaner`
- **Jakob Poeltl**: expected `Pure Defensive Center` → got `Rim-Running Anchor`
- **Mitchell Robinson**: expected `Pure Defensive Center` → got `Glass Cleaner`
- **Al Horford**: expected `Versatile Swiss-Army Big` → got `Shooting Stretch Big`
- **Steven Adams**: expected `Energy Big` → got `Glass Cleaner`
- **Isaiah Hartenstein**: expected `Energy Big` → got `Athletic Finisher Wing`
- **Nic Claxton**: expected `Energy Big` → got `Rim-Running Anchor`
- **Jonas Valanciunas**: expected `Throwback Post Hub` → got `Glass Cleaner`
- **Nikola Vucevic**: expected `Throwback Post Hub` → got `Stretch Big`
- **Naz Reid**: expected `Stretch Four / Combo Forward` → got `Shooting Stretch Big`
- **Grant Williams**: expected `Stretch Four / Combo Forward` → got `Shooting Stretch Big`
- **Pascal Siakam**: expected `Modern Two-Way Forward` → got `Stretch Big`
- **Julius Randle**: expected `Modern Two-Way Forward` → got `Creating Playmaking Big`
- **Paolo Banchero**: expected `Modern Two-Way Forward` → got `All-Around Forward`

