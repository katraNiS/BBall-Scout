"""
Pydantic schemas για request/response validation.

Τα responses παραμένουν loosely-typed (dict) όπου το serialization γίνεται στο
engine — δεν επιβάλλουμε strict output models για να μη διπλασιάζουμε τη λογική.
Τα request models όμως τα validate-άρουμε αυστηρά.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

# Ίδιο vocabulary με το position_group / ALL_POSITIONS στο src/archetypes.py —
# όχι PG/SG/SF/PF/C. Έτσι η θέση ενός prospect μπορεί αργότερα να τροφοδοτήσει
# trait eligibility / position filtering στο engine χωρίς mapping table.
ProspectPosition = Literal["G", "G-F", "F", "F-C", "C"]


class SimilarRequest(BaseModel):
    """Request body για POST /similar."""

    # Display-unit values ανά feature key (π.χ. {"ts_pct": 60.0, "pts": 25}).
    # Η μετατροπή display→internal (÷100 για pct) γίνεται server-side.
    stats: dict[str, float] = Field(
        ...,
        description="Feature key → display value. Τουλάχιστον ένα stat.",
    )
    weights: dict[str, float] | None = Field(
        default=None,
        description="Feature key → βάρος (0.1–5). Missing → 1.0.",
    )
    top_n: int = Field(default=10, ge=1, le=50)
    active_traits: list[str] | None = Field(
        default=None,
        description="Traits για boost (tiebreaker, όχι hard filter).",
    )
    season_range: str | None = Field(
        default=None,
        description='π.χ. "2010-2025" — φιλτράρει κατά start year.',
        examples=["2010-2025"],
    )
    # Δεν πάει στο matching engine — μόνο tag πάνω στην καταγραφή search history
    # (Phase 4) ώστε το home screen να ξέρει ποιο search ξεκίνησε από prefill.
    prospect_id: str | None = Field(
        default=None,
        description="Αν το search ξεκίνησε με prefill από prospect, το id του.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "stats": {"ts_pct": 62.0, "fg3a": 8.0, "ast_pct": 30.0},
                "weights": {"ast_pct": 2.0},
                "top_n": 10,
                "active_traits": ["lead_playmaker"],
                "season_range": "2015-2025",
            }
        }
    }


class ClassifyRequest(BaseModel):
    """Request body για POST /classify."""

    player_name: str = Field(..., min_length=1, description="Πλήρες ή μερικό όνομα.")
    season: str | None = Field(
        default=None,
        description='Συγκεκριμένη σεζόν "2020-21". Αλλιώς η πιο χαρακτηριστική.',
    )


# ── Prospects ───────────────────────────────────────────────────────────────────
# Χειρόγραφες εγγραφές scouted παικτών — ανεξάρτητες από το NBA dataset.


class ProspectBase(BaseModel):
    """Κοινά πεδία — χρησιμοποιείται μόνο ως βάση, όχι απευθείας ως request model."""

    first_name: str = Field(..., min_length=1, max_length=60)
    last_name: str = Field(..., min_length=1, max_length=60)
    # birth_date προτιμάται από αποθηκευμένη ηλικία — μια αποθηκευμένη ηλικία
    # γίνεται λάθος μετά από έναν χρόνο. Το age_manual υπάρχει μόνο για όταν η
    # ημερομηνία γέννησης πραγματικά δεν είναι γνωστή· η ηλικία υπολογίζεται
    # στο render, όχι εδώ.
    birth_date: date | None = None
    age_manual: int | None = Field(default=None, ge=14, le=50)
    # cm/kg (όχι cm/lbs όπως το FEATURE_COLS του engine) — το tool στοχεύει
    # Ευρωπαίους prospects και ο χρήστης σκέφτεται σε kg. Η μετατροπή kg→lbs
    # γίνεται σε ένα και μόνο σημείο στο frontend (Phase 3), ίδιο pattern με
    # το to_internal/to_display στο metadata.py.
    height_cm: float | None = Field(default=None, ge=150, le=250)
    weight_kg: float | None = Field(default=None, ge=50, le=180)
    nationality: str | None = None
    team: str | None = None
    league: str | None = None
    position: ProspectPosition | None = None
    notes: str | None = Field(default=None, max_length=2000)


class ProspectCreate(ProspectBase):
    """Request body για POST /prospects."""


class ProspectUpdate(BaseModel):
    """Request body για PATCH /prospects/{id} — όλα optional (partial update)."""

    first_name: str | None = Field(default=None, min_length=1, max_length=60)
    last_name: str | None = Field(default=None, min_length=1, max_length=60)
    birth_date: date | None = None
    age_manual: int | None = Field(default=None, ge=14, le=50)
    height_cm: float | None = Field(default=None, ge=150, le=250)
    weight_kg: float | None = Field(default=None, ge=50, le=180)
    nationality: str | None = None
    team: str | None = None
    league: str | None = None
    position: ProspectPosition | None = None
    notes: str | None = Field(default=None, max_length=2000)


class CompQuery(BaseModel):
    """Το query που παρήγαγε ένα saved comp set.

    Αποθηκεύεται μαζί με τα results γιατί ένα comp set χωρίς αυτό είναι
    αναγνώσιμο ("Luka, 87%") αλλά όχι ερμηνεύσιμο — δεν ξέρεις ποια stats/βάρη
    οδήγησαν σε αυτό το ταίριασμα.
    """

    stats: dict[str, float]
    weights: dict[str, float] | None = None
    season_range: str | None = None
    active_traits: list[str] | None = None


class CompResultSummary(BaseModel):
    """Slim αντίγραφο ενός MatchResult — όχι το πλήρες payload.

    Το radar και τα matching/diverging arrays είναι derived data που ξαναφτιάχνεται
    on-demand· το να τα αποθηκεύουμε θα φούσκωνε το JSON store χωρίς όφελος.
    """

    player_name: str
    season: str
    similarity: float
    compound_archetype: str
    position_group: str


class CompCreate(BaseModel):
    """Request body για POST /prospects/{id}/comps."""

    label: str | None = Field(default=None, max_length=200)
    query: CompQuery
    results: list[CompResultSummary]


class Comp(CompCreate):
    """Το stored σχήμα ενός comp set — id/created_at server-set."""

    id: str
    created_at: datetime


class SearchTopResult(BaseModel):
    """Slim αντίγραφο — μόνο τα top 3 αποτελέσματα, όχι όλο το MatchResult."""

    player_name: str
    season: str
    similarity: float


class SearchHistoryEntry(BaseModel):
    """Καταγράφεται αυτόματα μέσα στο POST /similar — ποτέ client-submitted.

    Ίδιο query σχήμα με το CompQuery + top_n (η κάθε αναζήτηση έχει top_n, ενώ
    ένα saved comp set δεν το χρειάζεται γιατί τα results ήδη το αντανακλούν).
    """

    id: str
    created_at: datetime
    query: CompQuery
    top_n: int
    top_results: list[SearchTopResult]
    prospect_id: str | None = None


class Prospect(ProspectBase):
    """Το stored/returned σχήμα — server-set id + timestamps."""

    id: str
    created_at: datetime
    updated_at: datetime
    comps: list[Comp] = Field(default_factory=list)
