"""
Primitive trait definitions, compound archetype presets, και trait classifier.

Architecture:
  - TRAITS: 18 primitive traits με signals (weighted stats + κατεύθυνση)
  - COMPOUNDS: 29 named presets ως frozensets of trait combinations
  - classify(df): score κάθε παίκτη σε κάθε trait → compound archetype label
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

ALL_POSITIONS = ["G", "G-F", "F", "F-C", "C"]
BIG_POSITIONS = ["F", "F-C", "C"]   # group για position-relative normalization

# Threshold: score >= TRAIT_THRESHOLD → trait "ανάβει"
# 0.6 από empirical tuning — πιο χαμηλό δίνει ~3.5 traits/παίκτη (πολλά), 0.8+ χάνει Jokić
TRAIT_THRESHOLD = 0.6


@dataclass
class Signal:
    col: str            # column name στο dataset (lowercase)
    weight: float       # + = θέλουμε υψηλό, - = θέλουμε χαμηλό
    pos_rel: bool = False   # True = position-relative z-score (για bigs vs bigs)


@dataclass
class Trait:
    name: str
    positions: list[str]        # eligible position_groups
    signals: list[Signal]
    fine: bool = False          # True = αδύναμο signal, επισημαίνεται στο UI


# ─── 18 Primitive Traits ──────────────────────────────────────────────────────

TRAITS: dict[str, Trait] = {

    # ── A. Creation & on-ball scoring ──────────────────────────────────────────

    "on_ball_creator": Trait(
        name="on_ball_creator",
        positions=["G", "G-F", "F", "F-C"],
        signals=[
            Signal("usg_pct", weight=2.0),
            Signal("pts",     weight=1.5),
            Signal("fta",     weight=0.5),
            Signal("ast_pct", weight=0.5),
        ],
    ),

    "slasher": Trait(
        name="slasher",
        positions=["G", "G-F", "F", "F-C"],
        signals=[
            Signal("fta",    weight=2.0),
            Signal("fg_pct", weight=1.5),
            Signal("pts",    weight=0.5),
            Signal("fg3a",   weight=-1.0),  # slashers αποφεύγουν τα 3s
        ],
    ),

    "midrange_scorer": Trait(
        name="midrange_scorer",
        positions=["G", "G-F", "F", "F-C"],
        signals=[
            # Κύριο signal: % πόντων από mid-range (από Scoring endpoint).
            # Πριν: ορίζαμε αρνητικά (χαμηλό fg3a) — έπιανε bigs, όχι πραγματικούς midrange scorers.
            # Τώρα: θετικό, direct signal. DeRozan ~35%, Curry ~5% → διακρίνει σωστά.
            Signal("pct_pts_midrange", weight=3.0),
            Signal("pts",              weight=0.5),  # χρειάζεται volume για να μετρά
            Signal("fg3a",             weight=-0.5), # αδύνατο backup — διατηρείται για pre-Scoring seasons
        ],
        fine=True,  # εξαρτάται από Scoring endpoint data
    ),

    # ── B. Shooting (off-ball) ─────────────────────────────────────────────────

    "spot_up_shooter": Trait(
        name="spot_up_shooter",
        positions=["G", "G-F", "F", "F-C"],
        signals=[
            Signal("fg3_pct", weight=2.0),
            Signal("fg3a",    weight=1.5),
            Signal("usg_pct", weight=-0.5),  # catch-and-shoot = χαμηλό usage
            Signal("ts_pct",  weight=0.5),
            Signal("tov",     weight=-0.5),
        ],
    ),

    # usg_pct ως proxy για self-creation — χωρίς shot-tracking data δεν ξεχωρίζει πλήρως
    "movement_shooter": Trait(
        name="movement_shooter",
        positions=["G", "G-F"],
        signals=[
            Signal("fg3_pct", weight=2.0),
            Signal("fg3a",    weight=1.5),
            Signal("usg_pct", weight=1.0),  # υψηλότερο από spot_up = self-creation
            Signal("pts",     weight=0.5),
        ],
        fine=True,
    ),

    # ── C. Playmaking ──────────────────────────────────────────────────────────

    "lead_playmaker": Trait(
        name="lead_playmaker",
        positions=["G", "G-F"],
        signals=[
            Signal("ast_pct", weight=3.0),
            Signal("ast_to",  weight=1.5),
            Signal("usg_pct", weight=0.5),
        ],
    ),

    "connective_passer": Trait(
        name="connective_passer",
        positions=["G", "G-F", "F", "F-C"],
        signals=[
            Signal("ast_to",  weight=2.0),
            Signal("ast_pct", weight=1.0),
            Signal("tov",     weight=-1.0),
            Signal("usg_pct", weight=-0.5),  # secondary role = χαμηλό usage
        ],
    ),

    "playmaking_big": Trait(
        name="playmaking_big",
        positions=["F", "F-C", "C"],
        signals=[
            Signal("ast_pct", weight=3.0, pos_rel=True),  # vs άλλα bigs
            Signal("ast_to",  weight=1.5),
            Signal("pts",     weight=0.5),
        ],
    ),

    # ── D. Interior offense ────────────────────────────────────────────────────

    "post_scorer": Trait(
        name="post_scorer",
        positions=["F", "F-C", "C"],
        signals=[
            Signal("usg_pct", weight=2.0, pos_rel=True),
            Signal("pts",     weight=1.5),
            Signal("fta",     weight=1.0),
            Signal("fg3a",    weight=-1.5, pos_rel=True),  # post scorer ≠ perimeter shooter
        ],
    ),

    "roll_finisher": Trait(
        name="roll_finisher",
        positions=["F", "F-C", "C"],
        signals=[
            Signal("fg_pct",   weight=3.0),
            Signal("usg_pct",  weight=-1.0),   # finisher, όχι ball-handler
            Signal("oreb_pct", weight=0.5),
            Signal("fg3a",     weight=-1.5, pos_rel=True),
            Signal("ast_pct",  weight=-0.5),
        ],
    ),

    "stretch_big": Trait(
        name="stretch_big",
        positions=["F", "F-C", "C"],
        signals=[
            Signal("fg3a",    weight=3.0, pos_rel=True),  # κύριο signal: 3PA volume για big
            Signal("fg3_pct", weight=1.5),
            Signal("ts_pct",  weight=0.5),
        ],
    ),

    # ── E. Perimeter defense ───────────────────────────────────────────────────

    "point_of_attack_defender": Trait(
        name="point_of_attack_defender",
        positions=["G", "G-F"],
        signals=[
            Signal("stl",         weight=2.0),
            Signal("deflections", weight=2.0),   # νέο: direct δείκτης ball pressure (2015-16+)
            Signal("def_rating",  weight=-1.5),  # χαμηλό = καλή άμυνα
            Signal("usg_pct",     weight=-0.5),
        ],
        fine=True,  # def_rating team stat · deflections μόνο από 2015-16
    ),

    "versatile_wing_defender": Trait(
        name="versatile_wing_defender",
        positions=["G-F", "F", "F-C"],
        signals=[
            # Deflections: καλύτερος individual proxy για wing defense.
            # OG Anunoby, Mikal Bridges, Kawhi ψηλά → ξεχωρίζουν τώρα.
            Signal("deflections", weight=2.5),
            Signal("def_rating",  weight=-2.0),
            Signal("stl",         weight=1.0),
            Signal("blk",         weight=0.5),
            Signal("reb_pct",     weight=0.5),
            Signal("height_cm",   weight=0.5),
            # wingspan_cm: θα προστεθεί όταν έρθει το Kaggle Draft Combine dataset
        ],
    ),

    # ── F. Interior defense ────────────────────────────────────────────────────

    "rim_protector": Trait(
        name="rim_protector",
        positions=["F-C", "C"],
        signals=[
            Signal("blk",        weight=3.0),
            Signal("def_rating", weight=-1.5),
            Signal("dreb_pct",   weight=0.5),
            Signal("height_cm",  weight=0.5),
            Signal("fg3a",       weight=-0.5, pos_rel=True),
            # wingspan_cm: θα προστεθεί όταν έρθει το Kaggle dataset
        ],
    ),

    "help_defender": Trait(
        name="help_defender",
        positions=["F", "F-C", "C"],
        signals=[
            Signal("deflections",   weight=1.5),  # νέο: help defense = αντίδραση, όχι μόνο block
            Signal("stl",           weight=1.5),
            Signal("blk",           weight=1.5),
            Signal("def_rating",    weight=-2.0),
        ],
        fine=True,  # def_rating εξαρτάται από ομάδα · deflections μόνο 2015-16+
    ),

    # ── G. Rebounding ──────────────────────────────────────────────────────────

    "defensive_rebounder": Trait(
        name="defensive_rebounder",
        positions=["F", "F-C", "C"],
        signals=[
            Signal("dreb_pct",   weight=3.0),
            Signal("reb_pct",    weight=1.0),
            Signal("height_cm",  weight=0.3),
            Signal("weight_lbs", weight=0.3),
        ],
    ),

    "offensive_rebounder": Trait(
        name="offensive_rebounder",
        positions=["F-C", "C"],
        signals=[
            Signal("oreb_pct",   weight=3.0),
            Signal("fg_pct",     weight=0.5),   # putbacks
            Signal("weight_lbs", weight=0.3),
        ],
    ),

    # ── H. Efficiency ──────────────────────────────────────────────────────────

    "efficient_finisher": Trait(
        name="efficient_finisher",
        positions=ALL_POSITIONS,
        signals=[
            # Αφαιρέθηκε usg_pct=-1.0: τιμωρούσε τον Jokić (ψηλό usage αλλά elite efficiency)
            # και μπέρδευε το concept. Το trait τώρα ορίζεται αμιγώς από efficiency metrics.
            Signal("ts_pct",  weight=2.0),
            Signal("efg_pct", weight=1.5),
            Signal("fg_pct",  weight=1.0),
            Signal("tov",     weight=-1.0),
        ],
    ),
}


# ─── 29 Compound Archetypes ──────────────────────────────────────────────────
# Preset match: όταν ΟΛΑ τα traits ενός preset ανάβουν, ο παίκτης παίρνει αυτό το όνομα.
# Αν ταιριάζουν πολλά presets, κρατάμε το πιο συγκεκριμένο (περισσότερα traits).

COMPOUNDS: dict[str, frozenset[str]] = {
    # Guards ──────────────────────────────────────────────────────────────────
    "Floor General":
        frozenset({"lead_playmaker", "movement_shooter"}),
    "Scoring Lead Guard":
        frozenset({"on_ball_creator", "lead_playmaker", "midrange_scorer"}),
    "Two-Way Lead Guard":
        frozenset({"on_ball_creator", "lead_playmaker", "point_of_attack_defender"}),
    "Pure Point Guard":
        frozenset({"lead_playmaker", "connective_passer"}),
    "Bucket-Getter":
        frozenset({"on_ball_creator", "movement_shooter", "slasher"}),
    "Instant Offense":
        frozenset({"on_ball_creator", "movement_shooter"}),
    "Slashing Guard":
        frozenset({"slasher", "on_ball_creator"}),
    "3-and-D Guard":
        frozenset({"spot_up_shooter", "point_of_attack_defender"}),
    "Defensive Playmaker":
        frozenset({"lead_playmaker", "point_of_attack_defender"}),
    "Pure Shooter":
        frozenset({"movement_shooter", "spot_up_shooter"}),
    "Sharpshooter":
        frozenset({"movement_shooter", "spot_up_shooter", "efficient_finisher"}),
    # Wings ───────────────────────────────────────────────────────────────────
    "Two-Way Wing":
        frozenset({"on_ball_creator", "versatile_wing_defender"}),
    "Two-Way Slashing Star":
        frozenset({"on_ball_creator", "slasher", "versatile_wing_defender"}),
    "Wing Scorer":
        frozenset({"on_ball_creator", "midrange_scorer", "movement_shooter"}),
    "3-and-D Wing":
        frozenset({"spot_up_shooter", "versatile_wing_defender"}),
    "Point Forward":
        frozenset({"on_ball_creator", "lead_playmaker", "versatile_wing_defender"}),
    "Connector / Glue Wing":
        frozenset({"connective_passer", "spot_up_shooter", "versatile_wing_defender"}),
    "Athletic Finisher Wing":
        frozenset({"slasher", "versatile_wing_defender", "efficient_finisher"}),
    # Bigs ────────────────────────────────────────────────────────────────────
    "Point Center":
        frozenset({"playmaking_big", "post_scorer", "efficient_finisher"}),
    "Two-Way Scoring Big":
        frozenset({"post_scorer", "rim_protector"}),
    "Stretch Big":
        frozenset({"stretch_big", "efficient_finisher"}),
    "Shooting Stretch Big":
        frozenset({"stretch_big", "spot_up_shooter"}),
    "Stretch Rim Protector":
        frozenset({"stretch_big", "rim_protector"}),
    "Rim-Running Anchor":
        frozenset({"rim_protector", "roll_finisher", "defensive_rebounder"}),
    "Pure Defensive Center":
        frozenset({"rim_protector", "defensive_rebounder"}),
    "Playmaking Rim Protector":
        frozenset({"playmaking_big", "rim_protector", "help_defender"}),
    "Versatile Swiss-Army Big":
        frozenset({"playmaking_big", "versatile_wing_defender", "stretch_big"}),
    "Energy Big":
        frozenset({"offensive_rebounder", "roll_finisher", "help_defender"}),
    "Throwback Post Hub":
        frozenset({"post_scorer", "offensive_rebounder"}),
    "Glass Cleaner":
        frozenset({"defensive_rebounder", "offensive_rebounder"}),
    "Putback Finisher":
        frozenset({"roll_finisher", "offensive_rebounder"}),
    "Stretch Four / Combo Forward":
        frozenset({"stretch_big", "spot_up_shooter", "versatile_wing_defender"}),
    "Modern Two-Way Forward":
        frozenset({"stretch_big", "slasher", "versatile_wing_defender"}),
}


# ─── Naming helpers ───────────────────────────────────────────────────────────

_TRAIT_NOUN: dict[str, str] = {
    "on_ball_creator":          "Creator",
    "slasher":                  "Slasher",
    "midrange_scorer":          "Scorer",
    "spot_up_shooter":          "Shooter",
    "movement_shooter":         "Shooter",
    "lead_playmaker":           "Playmaker",
    "connective_passer":        "Connector",
    "playmaking_big":           "Playmaking Big",
    "post_scorer":              "Post Scorer",
    "roll_finisher":            "Roll Finisher",
    "stretch_big":              "Stretch Big",
    "point_of_attack_defender": "Defender",
    "versatile_wing_defender":  "Wing Defender",
    "rim_protector":            "Rim Protector",
    "help_defender":            "Help Defender",
    "defensive_rebounder":      "Rebounder",
    "offensive_rebounder":      "Offensive Rebounder",
    "efficient_finisher":       "Finisher",
}

_TRAIT_ADJECTIVE: dict[str, str] = {
    "on_ball_creator":          "Creating",
    "slasher":                  "Slashing",
    "midrange_scorer":          "Scoring",
    "spot_up_shooter":          "Shooting",
    "movement_shooter":         "Shooting",
    "lead_playmaker":           "Playmaking",
    "connective_passer":        "Connective",
    "playmaking_big":           "Playmaking",
    "post_scorer":              "Post-Scoring",
    "roll_finisher":            "Roll-Finishing",
    "stretch_big":              "Stretch",
    "point_of_attack_defender": "Defending",
    "versatile_wing_defender":  "Two-Way",
    "rim_protector":            "Rim-Protecting",
    "help_defender":            "Helping",
    "defensive_rebounder":      "Rebounding",
    "offensive_rebounder":      "Crashing",
    "efficient_finisher":       "Efficient",
}


# ─── Classifier ───────────────────────────────────────────────────────────────

def compute_trait_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Υπολογίζει score ανά primitive trait για κάθε παίκτη.
    Επιστρέφει df με score_<trait> columns (NaN για non-eligible positions).

    Position-relative z-scores (pos_rel=True):
    - Bigs (F, F-C, C) κανονικοποιούνται μεταξύ τους για τα ανάλογα signals.
    - Ένα avg ast_pct για Center φαίνεται φυσιολογικό vs guards αλλά ψηλό vs bigs.
    """
    result = df.copy()

    # Columns που χρειάζονται — μόνο όσα υπάρχουν στο df
    sig_cols = list({s.col for t in TRAITS.values() for s in t.signals} & set(df.columns))
    data = df[sig_cols].astype(float)

    # Global z-scores
    mu_g  = data.mean()
    std_g = data.std().replace(0, 1)
    global_z = ((data - mu_g) / std_g).fillna(0.0)

    # Position-relative z-scores για bigs (override global μόνο για big rows)
    big_mask = df["position_group"].isin(BIG_POSITIONS)
    posrel_z = global_z.copy()
    if big_mask.sum() > 1:
        big_data = data.loc[big_mask]
        mu_b  = big_data.mean()
        std_b = big_data.std().replace(0, 1)
        posrel_z.loc[big_mask] = ((big_data - mu_b) / std_b).fillna(0.0)

    for trait_name, trait in TRAITS.items():
        eligible     = df["position_group"].isin(trait.positions)
        eligible_idx = df.index[eligible]
        score        = pd.Series(np.nan, index=df.index, dtype=float)

        total_w = sum(abs(s.weight) for s in trait.signals if s.col in sig_cols)
        if total_w == 0 or not eligible.any():
            result[f"score_{trait_name}"] = score
            continue

        s_acc = pd.Series(0.0, index=eligible_idx)
        for sig in trait.signals:
            if sig.col not in sig_cols:
                continue
            z     = (posrel_z if sig.pos_rel else global_z)[sig.col]
            s_acc = s_acc + sig.weight * z.loc[eligible_idx]

        score.loc[eligible_idx] = s_acc / total_w
        result[f"score_{trait_name}"] = score

    return result


def assign_archetypes(
    df: pd.DataFrame,
    threshold: float = TRAIT_THRESHOLD,
) -> pd.DataFrame:
    """
    score >= threshold → trait active → compound archetype label.
    Προσθέτει: active_<trait>, active_traits (list), compound_archetype.
    """
    result      = df.copy()
    trait_names = list(TRAITS.keys())

    for t in trait_names:
        col = f"score_{t}"
        result[f"active_{t}"] = (result[col] >= threshold) if col in result.columns else False

    result["active_traits"] = result.apply(
        lambda row: [t for t in trait_names if row.get(f"active_{t}", False)],
        axis=1,
    )
    result["compound_archetype"] = result.apply(
        lambda row: _label_archetype(row, trait_names), axis=1
    )
    return result


def _label_archetype(row: pd.Series, trait_names: list[str]) -> str:
    active = frozenset(t for t in trait_names if row.get(f"active_{t}", False))

    if not active:
        return "Unclassified"

    # Πιο συγκεκριμένο preset (περισσότερα traits) που είναι υποσύνολο των active
    best_name, best_count = None, 0
    for name, preset in COMPOUNDS.items():
        if preset <= active and len(preset) > best_count:
            best_name  = name
            best_count = len(preset)

    if best_name:
        return best_name

    # Fallback: noun = κορυφαίο trait, modifier = δεύτερο
    sorted_active = sorted(
        active,
        key=lambda t: row.get(f"score_{t}", float("-inf")),
        reverse=True,
    )
    noun = _TRAIT_NOUN.get(sorted_active[0], sorted_active[0].replace("_", " ").title())
    if len(sorted_active) >= 2:
        modifier = _TRAIT_ADJECTIVE.get(
            sorted_active[1], sorted_active[1].replace("_", " ").title()
        )
        return f"{modifier} {noun}"
    return noun


def classify(df: pd.DataFrame, threshold: float = TRAIT_THRESHOLD) -> pd.DataFrame:
    """
    Κεντρική συνάρτηση.
    Input : cleaned df από preprocessing.load_and_clean()
    Output: df με score_*, active_*, active_traits, compound_archetype columns
    """
    df_scored = compute_trait_scores(df)
    return assign_archetypes(df_scored, threshold=threshold)
