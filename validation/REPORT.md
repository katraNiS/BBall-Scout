# Classifier Validation Report

- Labeled players resolved: **72/72**
- Current threshold (src): **0.6** — macro-F1 **0.494**, archetype top-1 **21/72 (0.292)**
- Best global threshold (macro-F1): **0.55** — macro-F1 **0.495**, archetype top-1 **18/72 (0.250)**

## Per-trait metrics @ threshold 0.6 (worst F1 first)

| Trait | Precision | Recall | F1 | Support | Best thr (F1) |
|---|---|---|---|---|---|
| efficient_finisher | 0.156 | 0.417 | 0.227 | 12 | 0.9 (0.333) |
| slasher | 0.222 | 0.333 | 0.267 | 12 | 0.4 (0.462) |
| help_defender | 0.231 | 0.600 | 0.333 | 5 | 0.55 (0.333) |
| defensive_rebounder | 0.250 | 1.000 | 0.400 | 6 | 0.85 (0.462) |
| playmaking_big | 0.278 | 0.833 | 0.417 | 6 | 0.95 (0.476) |
| offensive_rebounder | 0.263 | 1.000 | 0.417 | 5 | 0.75 (0.455) |
| post_scorer | 0.333 | 0.571 | 0.421 | 7 | 0.95 (0.571) |
| versatile_wing_defender | 0.538 | 0.350 | 0.424 | 20 | 0.3 (0.486) |
| midrange_scorer | 0.667 | 0.333 | 0.444 | 6 | 0.3 (0.600) |
| point_of_attack_defender | 0.308 | 0.800 | 0.444 | 5 | 0.55 (0.444) |
| spot_up_shooter | 0.345 | 0.714 | 0.465 | 14 | 0.95 (0.500) |
| connective_passer | 0.333 | 1.000 | 0.500 | 4 | 0.5 (0.500) |
| movement_shooter | 0.458 | 0.917 | 0.611 | 12 | 0.9 (0.625) |
| lead_playmaker | 0.458 | 1.000 | 0.629 | 11 | 0.95 (0.667) |
| stretch_big | 0.462 | 1.000 | 0.632 | 12 | 0.9 (0.706) |
| on_ball_creator | 0.579 | 0.957 | 0.721 | 23 | 0.4 (0.721) |
| rim_protector | 0.769 | 0.769 | 0.769 | 13 | 0.3 (0.828) |
| roll_finisher | 0.636 | 1.000 | 0.778 | 7 | 0.95 (0.875) |

## Threshold sweep

| Threshold | Macro-F1 | Archetype top-1 |
|---|---|---|
| 0.3 | 0.486 | 12/72 (0.167) |
| 0.35 | 0.485 | 14/72 (0.194) |
| 0.4 | 0.486 | 15/72 (0.208) |
| 0.45 | 0.485 | 16/72 (0.222) |
| 0.5 | 0.491 | 19/72 (0.264) |
| 0.55 ⬅ best | 0.495 | 18/72 (0.250) |
| 0.6 ⬅ current | 0.494 | 21/72 (0.292) |
| 0.65 | 0.493 | 19/72 (0.264) |
| 0.7 | 0.483 | 18/72 (0.250) |
| 0.75 | 0.473 | 18/72 (0.250) |
| 0.8 | 0.465 | 17/72 (0.236) |
| 0.85 | 0.461 | 17/72 (0.236) |
| 0.9 | 0.473 | 17/72 (0.236) |
| 0.95 | 0.480 | 16/72 (0.222) |

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

