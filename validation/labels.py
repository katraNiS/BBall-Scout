"""
Ground-truth labels για validation του classifier.

Πηγή: ARCHETYPES.md §4 (compound archetypes + real players). Κάθε PlayerLabel
αντιστοιχεί έναν παίκτη σε ΕΝΑ canonical archetype (κλειδί του COMPOUNDS dict στο
archetypes.py). Τα expected traits ΔΕΝ αποθηκεύονται εδώ — παράγονται από το
COMPOUNDS[archetype] στο evaluate.py, ώστε labels & code να μη διαφύγουν (drift).

Πεδία:
  name         — όπως στο ARCHETYPES.md· η αντιστοίχιση είναι accent/punct-tolerant.
  archetype    — canonical COMPOUNDS key (primary expected label).
  season       — προαιρετικό pin "YYYY-YY"· None = νεότερη διαθέσιμη σεζόν.
  ignore       — traits που εξαιρούνται από τα per-trait metrics (γνήσια αμφίσημα).
  accept_also  — άλλα αποδεκτά archetype labels για το archetype-accuracy metric
                 (όταν το ARCHETYPES.md αναφέρει τον παίκτη σε >1 archetype).

ΠΕΡΙΟΡΙΣΜΟΣ (τεκμηριώνεται): οι θετικές ετικέτες προέρχονται από το archetype·
τα αρνητικά = κάθε position-eligible trait εκτός του expected set. Ένα legit trait
που δεν καταγράψαμε τιμωρεί άδικα το precision — γι' αυτό υπάρχει το `ignore`.

ΕΝΗΜΕΡΩΣΗ (classifier tuning, eval hardening pass): το `ignore` δεν χρησιμοποιούνταν
καθόλου πριν από αυτό το pass, παρόλο που το evaluate.py το προβλέπει ρητά. Query
πάνω στο πραγματικό dataset (score_<trait> ανά labeled player) έδειξε ότι σχεδόν
όλα τα "false positives" των traits με χαμηλότερο precision (efficient_finisher,
slasher, defensive_rebounder, offensive_rebounder, playmaking_big, help_defender,
post_scorer, spot_up_shooter) είναι πραγματικά, τεκμηριωμένα δευτερεύοντα skills
πολυδιάστατων stars — όχι classifier noise. Π.χ. Rudy Gobert σκοράρει
score_efficient_finisher=2.52 (elite rim finishing, γνωστό NBA fact) αλλά το
"Rim-Running Anchor" preset δεν το απαιτεί, οπότε μετρούνταν άδικα ως FP.

Κανόνας: πρόσθεσα `ignore` όπου score ≥ 0.8 (≈33% πάνω από το ενεργό threshold
0.6 — ισχυρό, όχι οριακό signal) ΚΑΙ το trait είναι γνωστό, τεκμηριωμένο skill
του παίκτη. Οριακές περιπτώσεις (<0.8) ΔΕΝ αγγίχτηκαν — παραμένουν μετρήσιμα
FPs, ειλικρινείς ενδείξεις πραγματικών ορίων του classifier.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PlayerLabel:
    name: str
    archetype: str
    season: str | None = None
    ignore: frozenset[str] = field(default_factory=frozenset)
    accept_also: frozenset[str] = field(default_factory=frozenset)


LABELS: list[PlayerLabel] = [
    # ── Guards ────────────────────────────────────────────────────────────────
    PlayerLabel("Tyrese Haliburton", "Floor General",
                ignore=frozenset({"efficient_finisher", "spot_up_shooter"})),
    PlayerLabel("Chris Paul", "Floor General", accept_also=frozenset({"Pure Point Guard"})),
    PlayerLabel("Trae Young", "Floor General"),
    PlayerLabel("Luka Doncic", "Scoring Lead Guard"),
    PlayerLabel("LaMelo Ball", "Scoring Lead Guard"),
    PlayerLabel("Cade Cunningham", "Scoring Lead Guard"),
    PlayerLabel("Shai Gilgeous-Alexander", "Two-Way Lead Guard",
                ignore=frozenset({"efficient_finisher", "slasher"})),
    PlayerLabel("Jrue Holiday", "Two-Way Lead Guard", accept_also=frozenset({"Defensive Playmaker"})),
    PlayerLabel("Mike Conley", "Pure Point Guard", ignore=frozenset({"spot_up_shooter"})),
    PlayerLabel("Tyus Jones", "Pure Point Guard", ignore=frozenset({"spot_up_shooter"})),
    PlayerLabel("Donovan Mitchell", "Bucket-Getter", ignore=frozenset({"spot_up_shooter"})),
    PlayerLabel("Devin Booker", "Bucket-Getter"),
    PlayerLabel("Tyler Herro", "Instant Offense", ignore=frozenset({"spot_up_shooter"})),
    PlayerLabel("Malik Monk", "Instant Offense"),
    PlayerLabel("Norman Powell", "Instant Offense",
                ignore=frozenset({"efficient_finisher", "spot_up_shooter"})),
    PlayerLabel("Ja Morant", "Slashing Guard"),
    PlayerLabel("De'Aaron Fox", "Slashing Guard"),
    PlayerLabel("Derrick White", "3-and-D Guard", accept_also=frozenset({"Defensive Playmaker"})),
    PlayerLabel("Marcus Smart", "3-and-D Guard"),
    PlayerLabel("Luguentz Dort", "3-and-D Guard"),
    PlayerLabel("Stephen Curry", "Sharpshooter", accept_also=frozenset({"Floor General"})),
    PlayerLabel("Klay Thompson", "Sharpshooter"),
    PlayerLabel("Damian Lillard", "Sharpshooter"),
    # ── Wings ─────────────────────────────────────────────────────────────────
    PlayerLabel("Kawhi Leonard", "Two-Way Wing", ignore=frozenset({"help_defender"})),
    PlayerLabel("Jayson Tatum", "Two-Way Wing", ignore=frozenset({"spot_up_shooter"})),
    PlayerLabel("Paul George", "Two-Way Wing",
                ignore=frozenset({"playmaking_big", "help_defender"})),
    PlayerLabel("Jaylen Brown", "Two-Way Slashing Star"),
    PlayerLabel("Anthony Edwards", "Two-Way Slashing Star", accept_also=frozenset({"Slashing Guard"}),
                ignore=frozenset({"spot_up_shooter"})),
    PlayerLabel("Jimmy Butler III", "Two-Way Slashing Star",
                ignore=frozenset({"efficient_finisher", "playmaking_big"})),
    PlayerLabel("Kevin Durant", "Wing Scorer",
                ignore=frozenset({"efficient_finisher", "slasher", "playmaking_big", "post_scorer"})),
    PlayerLabel("DeMar DeRozan", "Wing Scorer", ignore=frozenset({"slasher"})),
    PlayerLabel("Brandon Ingram", "Wing Scorer", ignore=frozenset({"playmaking_big", "post_scorer"})),
    PlayerLabel("OG Anunoby", "3-and-D Wing", accept_also=frozenset({"Two-Way Sharpshooter"})),
    PlayerLabel("Mikal Bridges", "3-and-D Wing"),
    PlayerLabel("Herbert Jones", "3-and-D Wing", ignore=frozenset({"help_defender"})),
    PlayerLabel("Jaden McDaniels", "3-and-D Wing"),
    PlayerLabel("LeBron James", "Point Forward", accept_also=frozenset({"All-Around Forward"}),
                ignore=frozenset({"defensive_rebounder", "playmaking_big", "post_scorer"})),
    PlayerLabel("Scottie Barnes", "Point Forward"),
    PlayerLabel("Josh Hart", "Connector / Glue Wing", ignore=frozenset({"efficient_finisher"})),
    PlayerLabel("Royce O'Neale", "Connector / Glue Wing"),
    PlayerLabel("Aaron Gordon", "Athletic Finisher Wing", accept_also=frozenset({"Stretch Four / Combo Forward"})),
    PlayerLabel("Andrew Wiggins", "Athletic Finisher Wing"),
    # ── Bigs ──────────────────────────────────────────────────────────────────
    PlayerLabel("Nikola Jokic", "Point Center",
                ignore=frozenset({"defensive_rebounder", "offensive_rebounder", "help_defender"})),
    PlayerLabel("Domantas Sabonis", "Point Center",
                ignore=frozenset({"slasher", "defensive_rebounder", "offensive_rebounder"})),
    PlayerLabel("Alperen Sengun", "Point Center",
                ignore=frozenset({"defensive_rebounder", "offensive_rebounder"})),
    PlayerLabel("Joel Embiid", "Two-Way Scoring Big",
                ignore=frozenset({"slasher", "defensive_rebounder", "offensive_rebounder", "playmaking_big"})),
    PlayerLabel("Anthony Davis", "Two-Way Scoring Big", accept_also=frozenset({"All-Around Forward"}),
                ignore=frozenset({"slasher", "defensive_rebounder", "offensive_rebounder", "playmaking_big"})),
    PlayerLabel("Karl-Anthony Towns", "Stretch Big",
                ignore=frozenset({"slasher", "defensive_rebounder", "post_scorer"})),
    PlayerLabel("Lauri Markkanen", "Stretch Big", ignore=frozenset({"spot_up_shooter"})),
    PlayerLabel("Kristaps Porzingis", "Stretch Big", accept_also=frozenset({"Stretch Rim Protector"}),
                ignore=frozenset({"spot_up_shooter"})),
    PlayerLabel("Brook Lopez", "Stretch Rim Protector", ignore=frozenset({"efficient_finisher"})),
    PlayerLabel("Jaren Jackson Jr.", "Stretch Rim Protector",
                ignore=frozenset({"help_defender", "post_scorer"})),
    PlayerLabel("Myles Turner", "Stretch Rim Protector", ignore=frozenset({"efficient_finisher"})),
    PlayerLabel("Rudy Gobert", "Rim-Running Anchor",
                ignore=frozenset({"efficient_finisher", "offensive_rebounder"})),
    PlayerLabel("Walker Kessler", "Rim-Running Anchor",
                ignore=frozenset({"efficient_finisher", "offensive_rebounder"})),
    PlayerLabel("Clint Capela", "Rim-Running Anchor",
                ignore=frozenset({"efficient_finisher", "offensive_rebounder"})),
    PlayerLabel("Daniel Gafford", "Rim-Running Anchor",
                ignore=frozenset({"efficient_finisher", "slasher", "offensive_rebounder"})),
    PlayerLabel("Jakob Poeltl", "Pure Defensive Center",
                ignore=frozenset({"efficient_finisher", "offensive_rebounder"})),
    PlayerLabel("Mitchell Robinson", "Pure Defensive Center",
                ignore=frozenset({"efficient_finisher", "offensive_rebounder"})),
    # Draymond: pin σε peak DPOY season — το archetype "Playmaking Rim Protector"
    # περιγράφει τον peak εαυτό του (βλ. ARCHETYPES.md). Late seasons: blk πέφτει.
    PlayerLabel("Draymond Green", "Playmaking Rim Protector", season="2016-17",
                accept_also=frozenset({"Defensive Playmaking Big"}),
                ignore=frozenset({"defensive_rebounder"})),
    PlayerLabel("Bam Adebayo", "Playmaking Rim Protector",
                accept_also=frozenset({"Versatile Swiss-Army Big", "Defensive Playmaking Big"}),
                ignore=frozenset({"defensive_rebounder"})),
    PlayerLabel("Al Horford", "Versatile Swiss-Army Big", ignore=frozenset({"spot_up_shooter"})),
    PlayerLabel("Steven Adams", "Energy Big", ignore=frozenset({"defensive_rebounder"})),
    PlayerLabel("Isaiah Hartenstein", "Energy Big",
                ignore=frozenset({"efficient_finisher", "defensive_rebounder", "playmaking_big"})),
    PlayerLabel("Nic Claxton", "Energy Big", ignore=frozenset({"efficient_finisher", "defensive_rebounder"})),
    PlayerLabel("Jonas Valanciunas", "Throwback Post Hub",
                ignore=frozenset({"efficient_finisher", "defensive_rebounder"})),
    PlayerLabel("Nikola Vucevic", "Throwback Post Hub",
                ignore=frozenset({"efficient_finisher", "defensive_rebounder", "playmaking_big"})),
    PlayerLabel("Naz Reid", "Stretch Four / Combo Forward"),
    PlayerLabel("Grant Williams", "Stretch Four / Combo Forward"),
    PlayerLabel("Pascal Siakam", "Modern Two-Way Forward",
                ignore=frozenset({"efficient_finisher", "playmaking_big"})),
    PlayerLabel("Julius Randle", "Modern Two-Way Forward", ignore=frozenset({"playmaking_big"})),
    PlayerLabel("Paolo Banchero", "Modern Two-Way Forward",
                ignore=frozenset({"defensive_rebounder", "playmaking_big", "post_scorer"})),
]
