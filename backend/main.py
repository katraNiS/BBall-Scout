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

import store  # noqa: E402
from engine import engine  # noqa: E402
from schemas import (  # noqa: E402
    SimilarRequest,
    ClassifyRequest,
    ProspectCreate,
    ProspectUpdate,
    CompCreate,
)
from preprocessing import FEATURE_COLS  # noqa: E402 (src/ ήδη στο sys.path από το engine import)

_VALID_STAT_KEYS = set(FEATURE_COLS)


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

@app.get("/health")
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

    unknown = [k for k in req.stats if k not in _VALID_STAT_KEYS]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Άγνωστα stat keys: {unknown}")

    result = engine.similar(
        stats=req.stats,
        weights=req.weights,
        top_n=req.top_n,
        active_traits=req.active_traits,
        season_range=req.season_range,
    )

    # Καταγραφή στο search history για το home screen (Phase 4) — ΠΟΤΕ δεν πρέπει
    # μια αποτυχία εδώ να χαλάσει το ίδιο το search, οπότε swallow + log only.
    try:
        store.add_search({
            "query": {
                "stats": req.stats,
                "weights": req.weights,
                "season_range": req.season_range,
                "active_traits": req.active_traits,
            },
            "top_n": req.top_n,
            "top_results": [
                {
                    "player_name": r["player_name"],
                    "season": r["season"],
                    "similarity": r["similarity"],
                }
                for r in result.get("results", [])[:3]
            ],
            "prospect_id": req.prospect_id,
        })
    except Exception as e:  # noqa: BLE001
        print(f"[ProspectMatch] Αποτυχία καταγραφής search history: {e}", flush=True)

    return result


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


# ── Prospects ───────────────────────────────────────────────────────────────────
# Ανεξάρτητο από το NBA dataset — δεν καλούν _require_ready(), ώστε το roster να
# μένει χρηστικό ενώ το dataset ακόμα φορτώνεται. Ονομάζονται /prospects (όχι
# /players) για να μη συγκρούονται με το υπάρχον GET /players (autocomplete).


@app.get("/prospects")
def list_prospects() -> list[dict]:
    return store.list_all()


@app.get("/prospects/{prospect_id}")
def get_prospect(prospect_id: str) -> dict:
    record = store.get(prospect_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Prospect δεν βρέθηκε.")
    return record


@app.post("/prospects", status_code=201)
def create_prospect(req: ProspectCreate) -> dict:
    return store.create(req.model_dump(mode="json"))


@app.patch("/prospects/{prospect_id}")
def patch_prospect(prospect_id: str, req: ProspectUpdate) -> dict:
    patch = req.model_dump(mode="json", exclude_unset=True)
    record = store.update(prospect_id, patch)
    if record is None:
        raise HTTPException(status_code=404, detail="Prospect δεν βρέθηκε.")
    return record


@app.delete("/prospects/{prospect_id}", status_code=204)
def delete_prospect(prospect_id: str) -> None:
    if not store.delete(prospect_id):
        raise HTTPException(status_code=404, detail="Prospect δεν βρέθηκε.")


# ── Prospect comps (αποθηκευμένα σύνολα NBA comps) ───────────────────────────────


@app.post("/prospects/{prospect_id}/comps", status_code=201)
def add_prospect_comp(prospect_id: str, req: CompCreate) -> dict:
    record = store.add_comp(prospect_id, req.model_dump(mode="json"))
    if record is None:
        raise HTTPException(status_code=404, detail="Prospect δεν βρέθηκε.")
    return record


@app.delete("/prospects/{prospect_id}/comps/{comp_id}", status_code=204)
def delete_prospect_comp(prospect_id: str, comp_id: str) -> None:
    if not store.delete_comp(prospect_id, comp_id):
        raise HTTPException(status_code=404, detail="Prospect ή comp δεν βρέθηκε.")


# ── Search history (για το home screen) ──────────────────────────────────────────
# Ίδια λογική με τα /prospects — ανεξάρτητο από το dataset, όχι _require_ready().


@app.get("/searches")
def list_searches() -> list[dict]:
    return store.list_searches()


@app.delete("/searches", status_code=204)
def clear_searches() -> None:
    store.clear_searches()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
