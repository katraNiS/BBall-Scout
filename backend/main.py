"""
ProspectMatch API — FastAPI wrapper γύρω από το similarity engine.

Endpoints:
  GET  /health        — liveness + dataset stats
  GET  /stats         — feature metadata (ranges/labels/groups) + traits
  GET  /archetypes    — τα 29 compound presets
  GET  /players       — autocomplete ονομάτων (?q=)
  POST /similar       — top-N όμοιοι παίκτες για user profile
  POST /classify      — archetype ενός πραγματικού παίκτη

Το dataset φορτώνεται μία φορά στο startup (lifespan) και μένει in-memory.
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

# backend/ στο path ώστε τα intra-package imports (engine/schemas/metadata) να δουλέψουν
# είτε τρέχει ως `uvicorn main:app` μέσα στο backend/ είτε ως module απ' έξω.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from engine import engine  # noqa: E402
from schemas import SimilarRequest, ClassifyRequest  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: φόρτωσε το dataset μία φορά (preprocess + classify + percentiles)
    print("[ProspectMatch] Loading dataset...", flush=True)
    engine.load()
    print(
        f"[ProspectMatch] Ready — {engine.n_players} players, {engine.n_rows} rows.",
        flush=True,
    )
    yield
    # Shutdown: τίποτα να καθαρίσουμε (in-memory only)


app = FastAPI(
    title="ProspectMatch API",
    description="NBA player similarity & archetype engine.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — dev: Vite (5173) + Electron (file://). Prod: το bundle μιλάει localhost.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
    ],
    allow_origin_regex=r"^(file://|app://).*",  # Electron packaged origins
    allow_methods=["*"],
    allow_headers=["*"],
)


def _require_ready() -> None:
    if not engine.ready:
        raise HTTPException(status_code=503, detail="Dataset ακόμα φορτώνεται.")


# ── Health / metadata ──────────────────────────────────────────────────────────

# GET + HEAD: το `wait-on` (dev orchestration) κάνει HEAD· χωρίς αυτό → 405 → hang.
@app.api_route("/health", methods=["GET", "HEAD"])
def health() -> dict:
    return {
        "status": "ok" if engine.ready else "loading",
        "players": engine.n_players,
        "rows": engine.n_rows,
    }


@app.get("/stats")
def get_stats() -> dict:
    """Feature metadata για το stat builder + διαθέσιμα traits."""
    return engine.stats_meta()


@app.get("/archetypes")
def get_archetypes() -> dict:
    """Τα 29 compound archetype presets (traits + eligible positions)."""
    return engine.archetypes_meta()


@app.get("/players")
def get_players(q: str = Query(..., min_length=1), limit: int = Query(20, ge=1, le=50)) -> dict:
    """Autocomplete — ονόματα παικτών που ταιριάζουν στο q."""
    _require_ready()
    return {"players": engine.player_names(q, limit)}


# ── Core ────────────────────────────────────────────────────────────────────────

@app.post("/similar")
def post_similar(req: SimilarRequest) -> dict:
    """Top-N πιο όμοιοι παίκτες για το user-defined profile."""
    _require_ready()
    if not req.stats:
        raise HTTPException(status_code=400, detail="Όρισε τουλάχιστον ένα stat.")

    unknown = [k for k in req.stats if k not in _valid_keys()]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Άγνωστα stat keys: {unknown}")

    return engine.similar(
        stats=req.stats,
        weights=req.weights,
        top_n=req.top_n,
        active_traits=req.active_traits,
        season_range=req.season_range,
    )


@app.post("/classify")
def post_classify(req: ClassifyRequest) -> dict:
    """Archetype + active traits ενός πραγματικού παίκτη."""
    _require_ready()
    result = engine.classify_player(req.player_name, req.season)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Δεν βρέθηκε παίκτης για '{req.player_name}'"
            + (f" ({req.season})" if req.season else ""),
        )
    return result


def _valid_keys() -> set[str]:
    from preprocessing import FEATURE_COLS
    return set(FEATURE_COLS)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
