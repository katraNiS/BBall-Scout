"""
Pydantic schemas για request/response validation.

Τα responses παραμένουν loosely-typed (dict) όπου το serialization γίνεται στο
engine — δεν επιβάλλουμε strict output models για να μη διπλασιάζουμε τη λογική.
Τα request models όμως τα validate-άρουμε αυστηρά.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


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
