"""
JSON-backed repository για τα user-created prospect records.

Ανεξάρτητο από το src/ dataset — οι prospects είναι χειρόγραφες εγγραφές του
χρήστη, όχι NBA δεδομένα. Persistence:

  - Ένα αρχείο `prospects.json` μέσα στον resolved data dir (βλ. `_data_dir()`).
  - Atomic write: serialize σε temp file στον ΙΔΙΟ φάκελο, μετά `os.replace()`
    πάνω στο target. Ένα crash στη μέση ενός write δεν πρέπει ποτέ να αφήσει
    μισογραμμένο JSON πίσω — θα κατέστρεφε όλο το roster. Το `os.replace` είναι
    atomic τόσο σε Windows όσο και σε POSIX.
  - Load μία φορά στο πρώτο use, in-memory list ως πηγή αλήθειας, flush σε κάθε
    mutation.
  - `threading.Lock` γύρω από κάθε read-modify-write: ο uvicorn τρέχει sync
    endpoints σε threadpool, άρα δύο ταυτόχρονα writes είναι πραγματικό ρίσκο.

Data dir resolution:
  1. `PROSPECTMATCH_DATA_DIR` env var, αν έχει οριστεί (το θέτει το Electron
     main process στο `app.getPath("userData")` για packaged builds).
  2. Αλλιώς `./.prospectmatch-data/` (dev convenience) — repo-local, ΟΧΙ μέσα
     στο install dir (που σε Windows είναι συνήθως Program Files, μη εγγράψιμο).

Το JSON file format μπορεί να αλλάξει σε SQLite αργότερα χωρίς να αλλάξουν οι
callers — όλη η persistence λογική μένει πίσω από αυτές τις plain functions.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_lock = threading.Lock()
_prospects: list[dict[str, Any]] | None = None


def _data_dir() -> Path:
    override = os.environ.get("PROSPECTMATCH_DATA_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent / ".prospectmatch-data"


def _prospects_path() -> Path:
    return _data_dir() / "prospects.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_MAX_COMPS = 20


def _ensure_loaded() -> None:
    global _prospects
    if _prospects is not None:
        return
    path = _prospects_path()
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            _prospects = json.load(f)
        # Backfill: prospects γραμμένοι πριν το Phase 3 δεν έχουν "comps".
        for p in _prospects:
            p.setdefault("comps", [])
    else:
        _prospects = []
        _flush()


def _flush() -> None:
    """Atomic write: γράψε σε temp file στον ίδιο φάκελο, μετά os.replace()."""
    path = _prospects_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f".tmp-{uuid.uuid4().hex}")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(_prospects, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


# ── Public API ──────────────────────────────────────────────────────────────────

def list_all() -> list[dict[str, Any]]:
    """Όλοι οι prospects, πιο πρόσφατα ενημερωμένοι πρώτα."""
    with _lock:
        _ensure_loaded()
        return sorted(_prospects, key=lambda p: p["updated_at"], reverse=True)


def get(prospect_id: str) -> dict[str, Any] | None:
    with _lock:
        _ensure_loaded()
        return next((p for p in _prospects if p["id"] == prospect_id), None)


def create(data: dict[str, Any]) -> dict[str, Any]:
    """data: το validated .model_dump() ενός ProspectCreate. Το id είναι πάντα server-generated."""
    with _lock:
        _ensure_loaded()
        now = _now()
        record = {
            "id": uuid.uuid4().hex,
            **data,
            "comps": [],
            "created_at": now,
            "updated_at": now,
        }
        _prospects.append(record)
        _flush()
        return record


def update(prospect_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    """patch: μόνο τα πεδία που δόθηκαν (ProspectUpdate .model_dump(exclude_unset=True))."""
    with _lock:
        _ensure_loaded()
        record = next((p for p in _prospects if p["id"] == prospect_id), None)
        if record is None:
            return None
        record.update(patch)
        record["updated_at"] = _now()
        _flush()
        return record


def delete(prospect_id: str) -> bool:
    with _lock:
        _ensure_loaded()
        before = len(_prospects)
        _prospects[:] = [p for p in _prospects if p["id"] != prospect_id]
        if len(_prospects) == before:
            return False
        _flush()
        return True


# ── Comps (saved NBA comp sets πάνω σε ένα prospect) ─────────────────────────────

def add_comp(prospect_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    """data: {label, query, results} — id/created_at πάντα server-generated.

    Νεότερα πρώτα (insert στην αρχή) και cap στα πιο πρόσφατα _MAX_COMPS ώστε ένας
    heavy user να μη μεγαλώνει απεριόριστα το αρχείο.
    """
    with _lock:
        _ensure_loaded()
        record = next((p for p in _prospects if p["id"] == prospect_id), None)
        if record is None:
            return None
        comp = {"id": uuid.uuid4().hex, "created_at": _now(), **data}
        comps = record.setdefault("comps", [])
        comps.insert(0, comp)
        del comps[_MAX_COMPS:]
        record["updated_at"] = _now()
        _flush()
        return record


def delete_comp(prospect_id: str, comp_id: str) -> bool:
    with _lock:
        _ensure_loaded()
        record = next((p for p in _prospects if p["id"] == prospect_id), None)
        if record is None:
            return False
        comps = record.get("comps", [])
        before = len(comps)
        record["comps"] = [c for c in comps if c["id"] != comp_id]
        if len(record["comps"]) == before:
            return False
        record["updated_at"] = _now()
        _flush()
        return True


# ── Search history (ξεχωριστό αρχείο, searches.json) ─────────────────────────────
# Ίδιο pattern με τα prospects (atomic write, in-memory + lock) — ξεχωριστό αρχείο
# γιατί είναι διαφορετική συλλογή, όχι πεδίο πάνω σε prospect.

_MAX_SEARCHES = 20
_searches: list[dict[str, Any]] | None = None


def _searches_path() -> Path:
    return _data_dir() / "searches.json"


def _ensure_searches_loaded() -> None:
    global _searches
    if _searches is not None:
        return
    path = _searches_path()
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            _searches = json.load(f)
    else:
        _searches = []
        _flush_searches()


def _flush_searches() -> None:
    path = _searches_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f".tmp-{uuid.uuid4().hex}")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(_searches, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def list_searches() -> list[dict[str, Any]]:
    """Νεότερες πρώτα — ήδη insert-αρισμένες έτσι στο add_search()."""
    with _lock:
        _ensure_searches_loaded()
        return list(_searches)


def add_search(data: dict[str, Any]) -> dict[str, Any]:
    """data: {query, top_results, prospect_id}. Cap στις πιο πρόσφατες _MAX_SEARCHES."""
    with _lock:
        _ensure_searches_loaded()
        record = {"id": uuid.uuid4().hex, "created_at": _now(), **data}
        _searches.insert(0, record)
        del _searches[_MAX_SEARCHES:]
        _flush_searches()
        return record


def clear_searches() -> None:
    with _lock:
        _ensure_searches_loaded()
        _searches.clear()
        _flush_searches()
