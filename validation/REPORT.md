# Classifier Validation Report

- Labeled players resolved: **72/72**
- Current threshold (src): **0.6** — macro-F1 **0.600**, archetype top-1 **21/72 (0.292)**
- Best global threshold (macro-F1): **0.9** — macro-F1 **0.622**, archetype top-1 **20/72 (0.278)**

## Per-trait metrics @ threshold 0.6 (worst F1 first)

| Trait | Precision | Recall | F1 | Support | Best thr (F1) |
|---|---|---|---|---|---|
| help_defender | 0.250 | 0.600 | 0.353 | 5 | 0.9 (0.429) |
| slasher | 0.400 | 0.333 | 0.364 | 12 | 0.4 (0.581) |
| point_of_attack_defender | 0.238 | 1.000 | 0.385 | 5 | 0.95 (0.421) |
| efficient_finisher | 0.385 | 0.417 | 0.400 | 12 | 0.8 (0.588) |
| midrange_scorer | 0.667 | 0.333 | 0.444 | 6 | 0.3 (0.600) |
| connective_passer | 0.333 | 1.000 | 0.500 | 4 | 0.5 (0.500) |
| versatile_wing_defender | 0.692 | 0.450 | 0.545 | 20 | 0.3 (0.684) |
| movement_shooter | 0.458 | 0.917 | 0.611 | 12 | 0.9 (0.625) |
| post_scorer | 0.667 | 0.571 | 0.615 | 7 | 0.75 (0.727) |
| spot_up_shooter | 0.556 | 0.714 | 0.625 | 14 | 0.8 (0.667) |
| lead_playmaker | 0.458 | 1.000 | 0.629 | 11 | 0.95 (0.667) |
| stretch_big | 0.462 | 1.000 | 0.632 | 12 | 0.9 (0.706) |
| on_ball_creator | 0.579 | 0.957 | 0.721 | 23 | 0.4 (0.721) |
| offensive_rebounder | 0.625 | 1.000 | 0.769 | 5 | 0.75 (0.909) |
| roll_finisher | 0.636 | 1.000 | 0.778 | 7 | 0.95 (0.875) |
| defensive_rebounder | 0.667 | 1.000 | 0.800 | 6 | 0.75 (1.000) |
| rim_protector | 0.706 | 0.923 | 0.800 | 13 | 0.6 (0.800) |
| playmaking_big | 0.833 | 0.833 | 0.833 | 6 | 0.8 (0.909) |

## Threshold sweep

Οι δύο πρώτες στήλες μετρώνται στα 72 labeled stars· οι υπόλοιπες σε ΟΛΟ
το dataset. Τα stars έχουν 6-10 active traits και δεν γίνονται ποτέ
Unclassified, οπότε το macro-F1 από μόνο του **δεν βλέπει** το κόστος ενός
υψηλού threshold στους role players.

| Threshold | Macro-F1 | Archetype top-1 | Traits/row | Unclassified | Fallback | Presets |
|---|---|---|---|---|---|---|
| 0.3 | 0.559 | 13/72 (0.181) | 4.09 | 4.5% | 18.3% | 36 |
| 0.35 | 0.561 | 13/72 (0.181) | 3.82 | 5.8% | 20.6% | 36 |
| 0.4 | 0.568 | 14/72 (0.194) | 3.56 | 7.1% | 22.7% | 36 |
| 0.45 | 0.573 | 15/72 (0.208) | 3.32 | 8.8% | 24.3% | 36 |
| 0.5 | 0.584 | 18/72 (0.250) | 3.08 | 10.5% | 26.4% | 36 |
| 0.55 | 0.593 | 18/72 (0.250) | 2.86 | 12.6% | 28.2% | 36 |
| 0.6 ⬅ current | 0.600 | 21/72 (0.292) | 2.65 | 15.0% | 29.0% | 36 |
| 0.65 | 0.604 | 20/72 (0.278) | 2.45 | 17.6% | 30.1% | 35 |
| 0.7 | 0.609 | 20/72 (0.278) | 2.26 | 20.4% | 30.8% | 35 |
| 0.75 | 0.616 | 20/72 (0.278) | 2.10 | 23.2% | 31.5% | 34 |
| 0.8 | 0.619 | 20/72 (0.278) | 1.94 | 26.0% | 31.8% | 33 |
| 0.85 | 0.618 | 20/72 (0.278) | 1.78 | 29.0% | 31.8% | 32 |
| 0.9 ⬅ best F1 | 0.622 | 20/72 (0.278) | 1.64 | 31.8% | 31.8% | 31 |
| 0.95 | 0.621 | 18/72 (0.250) | 1.51 | 35.2% | 31.4% | 31 |

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
- **LaMelo Ball**: expected `Scoring Lead Guard` → got `Two-Way Lead Guard`
- **Cade Cunningham**: expected `Scoring Lead Guard` → got `Floor General`
- **Jrue Holiday**: expected `Two-Way Lead Guard` → got `Pure Point Guard`
- **Donovan Mitchell**: expected `Bucket-Getter` → got `Two-Way Lead Guard`
- **Tyler Herro**: expected `Instant Offense` → got `Floor General`
- **Malik Monk**: expected `Instant Offense` → got `Floor General`
- **Norman Powell**: expected `Instant Offense` → got `Sharpshooter`
- **Ja Morant**: expected `Slashing Guard` → got `Two-Way Lead Guard`
- **De'Aaron Fox**: expected `Slashing Guard` → got `Two-Way Lead Guard`
- **Derrick White**: expected `3-and-D Guard` → got `Sharpshooter`
- **Marcus Smart**: expected `3-and-D Guard` → got `Defensive Playmaker`
- **Stephen Curry**: expected `Sharpshooter` → got `Two-Way Lead Guard`
- **Klay Thompson**: expected `Sharpshooter` → got `Pure Shooter`
- **Damian Lillard**: expected `Sharpshooter` → got `Two-Way Lead Guard`
- **Jayson Tatum**: expected `Two-Way Wing` → got `Two-Way Lead Guard`
- **Paul George**: expected `Two-Way Wing` → got `Defensive Playmaking Big`
- **Jaylen Brown**: expected `Two-Way Slashing Star` → got `Instant Offense`
- **Anthony Edwards**: expected `Two-Way Slashing Star` → got `Instant Offense`
- **Kevin Durant**: expected `Wing Scorer` → got `Point Center`
- **DeMar DeRozan**: expected `Wing Scorer` → got `Scoring Lead Guard`
- **Brandon Ingram**: expected `Wing Scorer` → got `All-Around Forward`
- **Mikal Bridges**: expected `3-and-D Wing` → got `Sharpshooter`
- **Herbert Jones**: expected `3-and-D Wing` → got `Helping Wing Defender`
- **Jaden McDaniels**: expected `3-and-D Wing` → got `Two-Way Help Defender`
- **Scottie Barnes**: expected `Point Forward` → got `Two-Way Lead Guard`
- **Josh Hart**: expected `Connector / Glue Wing` → got `Pure Point Guard`
- **Royce O'Neale**: expected `Connector / Glue Wing` → got `Stretch Big`
- **Aaron Gordon**: expected `Athletic Finisher Wing` → got `Stretch Big`
- **Andrew Wiggins**: expected `Athletic Finisher Wing` → got `Shooting Stretch Big`
- **Domantas Sabonis**: expected `Point Center` → got `All-Around Forward`
- **Alperen Sengun**: expected `Point Center` → got `Playmaking Rim Protector`
- **Joel Embiid**: expected `Two-Way Scoring Big` → got `Point Center`
- **Lauri Markkanen**: expected `Stretch Big` → got `Shooting Stretch Big`
- **Brook Lopez**: expected `Stretch Rim Protector` → got `Stretch Big`
- **Jaren Jackson Jr.**: expected `Stretch Rim Protector` → got `Modern Two-Way Forward`
- **Myles Turner**: expected `Stretch Rim Protector` → got `Stretch Big`
- **Jakob Poeltl**: expected `Pure Defensive Center` → got `Rim-Running Anchor`
- **Mitchell Robinson**: expected `Pure Defensive Center` → got `Rim-Running Anchor`
- **Al Horford**: expected `Versatile Swiss-Army Big` → got `Shooting Stretch Big`
- **Steven Adams**: expected `Energy Big` → got `Rim-Running Anchor`
- **Isaiah Hartenstein**: expected `Energy Big` → got `Rim-Running Anchor`
- **Nic Claxton**: expected `Energy Big` → got `Rim-Running Anchor`
- **Jonas Valanciunas**: expected `Throwback Post Hub` → got `Glass Cleaner`
- **Nikola Vucevic**: expected `Throwback Post Hub` → got `Stretch Big`
- **Naz Reid**: expected `Stretch Four / Combo Forward` → got `Shooting Stretch Big`
- **Grant Williams**: expected `Stretch Four / Combo Forward` → got `Shooting Stretch Big`
- **Pascal Siakam**: expected `Modern Two-Way Forward` → got `Versatile Swiss-Army Big`
- **Julius Randle**: expected `Modern Two-Way Forward` → got `Creating Playmaking Big`
- **Paolo Banchero**: expected `Modern Two-Way Forward` → got `All-Around Forward`

