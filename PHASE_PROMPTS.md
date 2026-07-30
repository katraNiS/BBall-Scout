# Implementation Prompts — Prospects & Home Screen

Five self-contained prompts, one per phase. Each assumes a **fresh chat with no prior context**.
Run them in order — each builds on the last. Copy from the phase heading down to the `---` divider.

| Phase | What it delivers | User-visible? |
|-------|------------------|---------------|
| 0 | Router + screen extraction | No (refactor) |
| 1 | Backend prospect storage | No (API only) |
| 2 | Prospect list + form UI | Yes |
| 3 | Prospect → NBA comps link | Yes |
| 4 | Home screen | Yes |

---

## PHASE 0 — Router & screen extraction

**Project: ProspectMatch — navigation refactor**

I have a working Electron + FastAPI + React desktop app (NBA scouting tool). Right now the React
frontend is a **single screen** and I need to add more, so this task is a pure refactor: introduce
routing and split the monolithic `App.tsx` into screens. **No new user-facing features.**

### Current state

- `frontend/` — React 18 + TypeScript + Vite + Recharts. No router installed.
- `frontend/src/App.tsx` (243 lines) — holds *everything*: `/stats` metadata fetch, stat-builder
  control state, season range, trait multiselect, top-N, the search call, and result rendering.
  It renders a two-column layout: `<aside className="sidebar">` + `<main className="main">`.
- `frontend/src/api.ts` — typed fetch client. Exports `api` (with `.base`, `.health`, `.statsMeta`,
  `.archetypes`, `.similar`, `.classify`, `.players`) and `ApiError`.
- `frontend/src/types.ts` — `StatMeta`, `StatsMetaResponse`, `MatchResult`, `SimilarRequest`, etc.
- `frontend/src/components/` — `StatBuilder.tsx` (exports `Control` and `Controls` types),
  `ResultCard.tsx`, `RadarChart.tsx`.
- `frontend/src/styles.css` — dark theme, CSS custom properties on `:root`:
  `--bg #0e1117`, `--bg-card #161b22`, `--bg-card-2 #1c2230`, `--border #2a3140`,
  `--text #e5e7eb`, `--text-dim #9ca3af`, `--text-dim2 #6b7280`, `--accent #3b82f6`,
  `--accent-2 #f97316`, `--green`, `--amber`, `--red`, `--pos`, `--pos-bg`, `--arch`, `--arch-bg`.
- `electron/main.cjs` — in production loads the UI with
  `mainWindow.loadFile(path.join(__dirname, "..", "frontend", "dist", "index.html"))`.

### What to build

**1. Install and wire `react-router-dom` (v6) using `HashRouter` — NOT `BrowserRouter`.**

This is non-negotiable and it's the whole reason to be careful here: the packaged app loads the UI
over `file://` via `loadFile()`. `BrowserRouter` relies on the History API against a real origin and
will render a blank window in the packaged build while working fine in `npm run dev` (which serves
over `http://localhost:5173`). Use `HashRouter` so routes survive both. Add a comment saying why.

**2. Extract the current search UI into `frontend/src/screens/SearchScreen.tsx`.**

Move it verbatim — same JSX, same state, same behaviour, same CSS classes. This phase must not
change a single pixel of the search experience. The sidebar (season range, trait boost, top-N,
backend status line) moves with it, since those controls belong to search, not to the app shell.

**3. Create a metadata context at `frontend/src/MetaContext.tsx`.**

Currently `App.tsx` fetches `/stats` in a `useEffect` on mount. Once there are multiple screens,
navigating away and back would refetch it every time, and Phase 2 needs the same metadata in a
different screen. Lift it into a provider that fetches once and exposes:

```ts
{ stats: StatMeta[]; traits: string[]; traitLabels: Record<string, string>;
  loading: boolean; error: string | null; backendOk: boolean | null }
```

Expose a `useMeta()` hook. Keep the existing "backend offline" full-screen error card, but render it
from the shell so *every* route gets it, not just search.

**4. Reduce `App.tsx` to a shell:** `<MetaProvider>` + `<HashRouter>` + persistent nav + `<Routes>`.

Routes to register now (placeholders are fine for the not-yet-built ones — a heading and a
"coming soon" line):

| Path | Screen |
|------|--------|
| `/` | `HomeScreen` (placeholder — Phase 4) |
| `/search` | `SearchScreen` (the real, moved code) |
| `/prospects` | `ProspectsScreen` (placeholder — Phase 2) |

**5. Add a nav element** — a slim top bar or left rail with links to Home / Search / Prospects, using
`<NavLink>` so the active route can be styled. Style it with the existing CSS variables listed above;
do not introduce a new color palette or a CSS framework.

### Constraints

- **Do not touch `src/`, `backend/`, or `electron/`.** This phase is frontend-only.
- Code comments in **Greek**, technical terms in English (existing convention — match the tone of the
  comments already in `api.ts` and `StatBuilder.tsx`).
- Keep TypeScript strict; `npm --prefix frontend run build` must pass with no errors.
- No new dependencies beyond `react-router-dom`.

### Done when

- `npm run dev` opens the app, nav works, `/search` behaves *identically* to before the refactor.
- `npm run build:frontend` passes.
- `App.tsx` is under ~60 lines and contains no search logic.
- `/stats` is fetched exactly once per app launch (verify in the Network tab — navigate away from
  search and back, confirm no second request).

---

## PHASE 1 — Prospect persistence (backend)

**Project: ProspectMatch — prospect storage API**

I have a working Electron + FastAPI + React desktop NBA scouting app. I want to add user-created
**prospect** records (scouted players the user tracks by hand — distinct from the NBA players in the
dataset). This phase is **backend + Electron only**; no UI.

### Current state

- `backend/main.py` — FastAPI app. Loads the NBA dataset once at startup via a `lifespan` context
  manager (`engine.load()`), CORS configured for Vite dev origins plus `file://`/`app://`.
  Has a `_require_ready()` guard that raises 503 while the dataset loads.
  **Existing endpoints:** `GET /health`, `GET /stats`, `GET /archetypes`, `GET /players?q=`,
  `POST /similar`, `POST /classify`.
- `backend/engine.py` — wraps the untouched `src/` engine, adds `src/` to `sys.path`.
- `backend/schemas.py` — Pydantic **request** models only (`SimilarRequest`, `ClassifyRequest`).
  Responses stay loosely typed as dicts by deliberate convention — don't change that.
- `backend/metadata.py` — UI metadata + the `to_internal` / `to_display` unit-conversion helpers.
- `electron/main.cjs` — spawns the backend as a subprocess in production:
  `backendProc = spawn(cmd, args, { cwd, env: process.env })`. In dev it does **not** spawn
  (the root `npm run dev` script runs uvicorn separately via `concurrently`).
- Root `package.json` — electron-builder config with `extraResources` copying `backend/`, `src/`,
  and `data/nba_stats_full.csv` into the packaged app's `resources/`.

### Critical: where the data is written

**Do not write into the app's install directory.** On Windows the packaged app lands in
`Program Files`, which is not user-writable, so anything written next to `resources/backend/` will
fail at runtime for a real installed build while working fine in dev. Resolve the store path like this:

1. `PROSPECTMATCH_DATA_DIR` environment variable, if set.
2. Otherwise fall back to a repo-local `./.prospectmatch-data/` (dev convenience).

Then in `electron/main.cjs`, set that variable when spawning the backend:

```js
env: { ...process.env, PROSPECTMATCH_DATA_DIR: app.getPath("userData") }
```

Add `.prospectmatch-data/` to `.gitignore`. This keeps user data out of both the repo and the
install dir, and survives app updates.

### What to build

**1. `backend/store.py` — a small JSON-backed repository.**

- Single file `prospects.json` inside the resolved data dir; create dir and file on first use.
- **Atomic writes**: serialize to a temp file in the same directory, then `os.replace()` onto the
  target. A half-written JSON file from a mid-write crash would destroy the whole roster, and
  `os.replace` is atomic on both Windows and POSIX.
- Load once into memory at startup, keep an in-memory list as the source of truth, flush on mutation.
- Guard concurrent writes with a `threading.Lock` (uvicorn runs sync endpoints in a threadpool, so
  two writes really can overlap).
- **IDs are server-generated `uuid4` strings.** Never accept a client-supplied id and never
  interpolate any client string into a filesystem path — the store is one fixed file, so keep it
  that way.
- Keep all persistence logic in this module behind plain functions (`list_all`, `get`, `create`,
  `update`, `delete`) so the JSON file can be swapped for SQLite later without touching the routes.

**2. `Prospect` model in `backend/schemas.py`.**

```
id           str            server-generated uuid4, never from client
first_name   str            required, 1–60 chars
last_name    str            required, 1–60 chars
birth_date   date | None    ISO date
age_manual   int | None     14–50, fallback when birth_date is unknown
height_cm    float | None   150–250
weight_kg    float | None   50–180
nationality  str | None     free text for now
team         str | None     free text
league       str | None     free text
position     str | None     one of: "G", "G-F", "F", "F-C", "C"
notes        str | None     up to ~2000 chars
created_at   datetime       server-set
updated_at   datetime       server-set
```

Three schema decisions to implement exactly as written, each with a reason worth a comment:

- **`position` must use `G / G-F / F / F-C / C`**, not `PG/SG/SF/PF/C`. This is the same vocabulary as
  `position_group` in `src/archetypes.py` (`ALL_POSITIONS`). Using the engine's own vocabulary means
  a prospect's position can later feed trait eligibility and position filtering with no mapping table.
  Validate with a `Literal` so a bad value is a 422, not silent corruption.
- **`birth_date` is preferred over a stored age.** A saved age is wrong a year later; derive age at
  render time instead. `age_manual` exists only for when the birth date genuinely isn't known.
- **Height in cm, weight in kg.** The engine's `FEATURE_COLS` use `height_cm` and `weight_lbs`, but
  this tool is aimed at European prospects and the user thinks in kg. Store kg; the kg→lbs conversion
  happens at exactly one boundary (Phase 3), mirroring how `metadata.py` already isolates the
  display↔internal conversion in `to_internal`/`to_display`.

Use separate models for create/update (`ProspectCreate`, `ProspectUpdate` with all-optional fields
for PATCH semantics) versus the stored/returned shape.

**3. Routes in `backend/main.py`.**

| Method | Path | Behaviour |
|--------|------|-----------|
| GET | `/prospects` | list all, newest-updated first |
| GET | `/prospects/{id}` | one, or 404 |
| POST | `/prospects` | create from `ProspectCreate`, return 201 + the record |
| PATCH | `/prospects/{id}` | partial update, bump `updated_at`, or 404 |
| DELETE | `/prospects/{id}` | 204, or 404 |

**Name them `/prospects`, not `/players`** — `GET /players` already exists and returns NBA-dataset
name autocomplete. Reusing the word would collide in both the API surface and in conversation.

These routes must **not** call `_require_ready()` — prospect storage is independent of the NBA
dataset, so the roster should stay usable during the several seconds the dataset takes to load.

### Constraints

- **`src/` is off-limits.** It's tested and working; the backend wraps it, never edits it.
- Follow the existing style in `backend/`: module docstring in Greek, `from __future__ import annotations`,
  type hints throughout. Comments in Greek, technical terms in English.
- No new Python dependencies — stdlib `json`, `uuid`, `threading`, `pathlib` plus the Pydantic
  already in use.
- Update `backend/requirements.txt` only if something genuinely new is needed (it shouldn't be).

### Done when

- With the backend running, this round-trips: create a prospect, list it, patch one field, delete it.
- Restarting the backend preserves the data.
- The file lands in `PROSPECTMATCH_DATA_DIR` when set, `./.prospectmatch-data/` when not.
- `GET /prospects` returns 200 (not 503) while the dataset is still loading.
- Show me the actual curl/HTTPie commands you used and their real output — don't just assert it works.

---

## PHASE 2 — Prospect list & form UI

**Project: ProspectMatch — prospect management screens**

Electron + FastAPI + React desktop NBA scouting app. The backend already exposes prospect CRUD; this
phase builds the React UI for it.

### Current state

- **Routing exists** (Phase 0): `react-router-dom` v6 with `HashRouter`. `App.tsx` is a shell with a
  nav and `<Routes>`. Screens live in `frontend/src/screens/`. `/prospects` currently renders a
  placeholder.
- **Metadata context exists**: `frontend/src/MetaContext.tsx` exposes `useMeta()`.
- **Backend endpoints ready** (Phase 1): `GET /prospects`, `GET /prospects/{id}`,
  `POST /prospects`, `PATCH /prospects/{id}`, `DELETE /prospects/{id}`.

  The `Prospect` shape: `id`, `first_name`, `last_name`, `birth_date` (ISO date | null),
  `age_manual` (int | null), `height_cm` (float | null), `weight_kg` (float | null),
  `nationality`, `team`, `league` (strings | null), `position` (`"G"|"G-F"|"F"|"F-C"|"C"` | null),
  `notes` (string | null), `created_at`, `updated_at`.

- `frontend/src/api.ts` — typed client with a private `request<T>(path, init)` helper that throws
  `ApiError` (with `.status`) and turns network failure into a Greek "backend not running" message.
- `frontend/src/types.ts` — API response interfaces.
- `frontend/src/styles.css` — dark theme via CSS custom properties: `--bg #0e1117`,
  `--bg-card #161b22`, `--bg-card-2 #1c2230`, `--border #2a3140`, `--text #e5e7eb`,
  `--text-dim #9ca3af`, `--text-dim2 #6b7280`, `--accent #3b82f6`, `--accent-2 #f97316`,
  `--green`, `--amber`, `--red`, `--pos`, `--pos-bg`, `--arch`, `--arch-bg`.
  Existing classes worth matching: `.stat-group`, `.stat-row`, `.error-box`, `.state-msg`,
  `.run-btn`, `.spinner`, `.divider`, `.summary-pills`.

### What to build

**1. `Prospect` types in `types.ts`** — the stored shape plus `ProspectCreate` / `ProspectUpdate`
(the latter all-optional). Mirror the backend exactly.

**2. `api.ts` methods** — `prospects.list()`, `.get(id)`, `.create(body)`, `.update(id, patch)`,
`.remove(id)`. Reuse the existing `request<T>` helper and its error handling; don't write a second
fetch path.

**3. `frontend/src/screens/ProspectsScreen.tsx`** — the list.

- Card grid. Each card: full name, position badge, age, height/weight, team · league, nationality.
- **Derive age from `birth_date`** when present (floor of years since birth date, accounting for
  whether the birthday has passed this year), falling back to `age_manual`, falling back to `—`.
  Put this in a shared helper — Phase 4 needs it too.
- Style the position badge with the existing `--pos` / `--pos-bg` variables (the result cards already
  use these for `position_group`, so prospects will read as the same kind of object).
- Empty state: a clear "no prospects yet" card with a primary action to add the first one. This is
  the first thing the user will see, so make it inviting rather than a bare message.
- Sort control: recently updated / last name / position.
- Each card links to `/prospects/:id/edit`; a delete action asks for confirmation first.

**4. `frontend/src/screens/ProspectFormScreen.tsx`** — create and edit in one component.

- Routes: `/prospects/new` and `/prospects/:id/edit`. On edit, load via `api.prospects.get(id)` and
  show a loading state; 404 renders a "not found" card with a link back to the list.
- Fields: first name, last name, birth date (`<input type="date">`), age fallback, height cm,
  weight kg, nationality, team, league, position (`<select>` with the five values), notes
  (`<textarea>`).
- **Only first and last name are required.** A scouting record gets filled in over time — do not
  block saving on an incomplete profile.
- Label height and weight with their units (`cm`, `kg`) directly in the field label.
- Client-side validation matching the backend bounds (height 150–250, weight 50–180, age 14–50) so
  the user gets an inline message instead of a 422. Still surface a server 422 in an `.error-box`
  if one slips through.
- Show the age derived from `birth_date` live next to the date field as confirmation.
- Save → navigate back to `/prospects`. Cancel → back with no write.
- Guard against double-submit while the request is in flight.

**5. Register the routes** in `App.tsx` and make the nav's "Prospects" link active for all
`/prospects*` paths.

### Constraints

- **Frontend only.** Don't touch `backend/`, `src/`, or `electron/`.
- Match the existing dark theme using the CSS variables above — no new palette, no CSS framework, no
  component library.
- Comments in Greek, technical terms in English (match `StatBuilder.tsx`).
- TypeScript strict; `npm --prefix frontend run build` must pass.
- No new dependencies.

### Done when

- I can create, edit, and delete a prospect end-to-end in the running app.
- Data survives an app restart.
- The empty state, loading state, not-found state, and a validation error each render sensibly.
- Actually run the app and confirm the flow before telling me it's done.

---

## PHASE 3 — Prospect → NBA comps

**Project: ProspectMatch — connect prospects to the similarity engine**

Electron + FastAPI + React desktop NBA scouting app. Prospect CRUD works (backend + UI). This phase
builds the link that makes prospects actually useful: **from a prospect, find their NBA comparables**,
and save the result back onto the prospect.

Without this, the prospect list is a notebook. With it, it's a scouting tool. This is the highest-value
phase — treat the two directions below as the core deliverable.

### Current state

- `frontend/src/screens/SearchScreen.tsx` — the similarity search. Owns a `Controls` state object
  (`Record<string, { enabled: boolean; value: number; weight: number }>`, one entry per stat, values
  in **display units**), plus `selectedTraits`, `yearRange`, `topN`. Initialised from `/stats`
  metadata (`StatMeta[]`: `key`, `label`, `group`, `min`, `max`, `step`, `default`, `is_pct`, `unit`).
  Calls `api.similar({ stats, weights, top_n, active_traits, season_range })` and renders
  `MatchResult[]` through `ResultCard`.
- `MatchResult` includes: `rank`, `player_name`, `season`, `position_group`, `compound_archetype`,
  `height_cm`, `weight_lbs`, `similarity`, `final_score`, `active_traits`, `matching`, `diverging`,
  `radar`.
- Prospects store `height_cm` and `weight_kg`; positions use `G / G-F / F / F-C / C`.
- Backend: `backend/store.py` (JSON repo, atomic writes, in-memory + lock), prospect routes in
  `backend/main.py`, models in `backend/schemas.py`.
- `backend/metadata.py` owns unit conversion (`to_internal` / `to_display`) — the established pattern
  for keeping a conversion in exactly one place.

### What to build

**Direction 1 — prospect → prefilled search.**

Add a **"Find NBA comps"** action on each prospect (list card and form screen). It navigates to the
search screen with the prospect's physicals pre-enabled and pre-set:

- `height_cm` → enable the `height_cm` control at the prospect's value.
- `weight_kg` → **convert to lbs** (`kg * 2.20462`) → enable the `weight_lbs` control.
  The engine's `FEATURE_COLS` use `weight_lbs`; prospects store kg. Put this conversion in **one**
  helper (e.g. `frontend/src/units.ts`), the way `metadata.py` isolates `to_internal`/`to_display`.
  Round to the nearest step from the `weight_lbs` `StatMeta` (step is 5) and clamp to its min/max, so
  the slider lands on a legal value.
- Skip any field the prospect hasn't filled in — never substitute a default and present it as if it
  came from the record.
- Show a dismissible banner on the search screen: "Prefilled from {name}" with a link back to the
  prospect, so it's obvious where those values came from.

Pass the prospect through router state (`navigate("/search", { state: { fromProspect: ... } })`)
rather than query params, and make `SearchScreen` read it on mount. Guard the effect so it applies
once and doesn't stomp the user's edits on re-render.

**Direction 2 — save results back onto the prospect.**

After a search that was prefilled from a prospect, offer **"Save these comps to {name}"**.

Backend — extend the prospect record with a `comps` list. Each saved entry:

```
id          str        server-generated uuid4
created_at  datetime   server-set
label       str|None   optional user note
query       {stats, weights, season_range, active_traits}   what was searched
results     list of {player_name, season, similarity, compound_archetype, position_group}
```

Store **only that slim result summary** — not the full `MatchResult`. The radar payload and the
matching/diverging explanation arrays are large, and they're derived data that regenerates on demand;
persisting them would bloat the JSON store for no benefit.

New routes:

| Method | Path | Behaviour |
|--------|------|-----------|
| POST | `/prospects/{id}/comps` | append a saved comp set, return the updated prospect |
| DELETE | `/prospects/{id}/comps/{comp_id}` | remove one, 204 |

Cap the stored list (keep the most recent ~20) so a heavy user can't grow the file without bound.

Frontend — on the prospect form/detail screen, render saved comp sets newest-first: date, the top few
matched players with similarity, and the query that produced them. Deleting one asks for confirmation.

The point of persisting the query alongside the results is that a comp set is only interpretable if
you can see what was asked. "Luka, 87%" means nothing without knowing which stats were weighted.

### Constraints

- **`src/` stays untouched.** The similarity engine is tested and working.
- Keep the kg↔lbs conversion in exactly one place; no ad-hoc `* 2.2` sprinkled through components.
- Phase 0's rule still holds: `HashRouter`, since the packaged app loads over `file://`.
- Comments in Greek, technical terms in English.
- TypeScript strict; `npm --prefix frontend run build` must pass. No new dependencies.

### Done when

- From a prospect with height and weight set, "Find NBA comps" lands on search with exactly those two
  controls enabled at the right converted values, and the banner names the prospect.
- A prospect missing weight prefills only height, with no phantom default.
- Saving comps persists across an app restart and renders with its query intact.
- Walk me through the round trip you actually ran, with the real numbers — e.g. 91 kg showing up as
  200 lbs on the slider.

---

## PHASE 4 — Home screen

**Project: ProspectMatch — home screen**

Electron + FastAPI + React desktop NBA scouting app. Search, prospect CRUD, and prospect→comps all
work. `/` currently renders a placeholder. This phase makes it a real landing screen.

### Current state

- Routing: `react-router-dom` v6, `HashRouter`, screens in `frontend/src/screens/`
  (`HomeScreen` placeholder, `SearchScreen`, `ProspectsScreen`, `ProspectFormScreen`).
- `MetaContext` exposes `useMeta()` with stats metadata and `backendOk`.
- `api.ts` has `health()`, `statsMeta()`, `archetypes()`, `similar()`, `classify()`, `players(q)`,
  and the `prospects.*` methods.
- `GET /health` returns `{ status, players, rows }` — the loaded dataset's player and row counts.
- Prospects carry `comps` (saved comp sets with `created_at`, `query`, `results`).
- Theme variables in `styles.css`: `--bg #0e1117`, `--bg-card #161b22`, `--bg-card-2 #1c2230`,
  `--border #2a3140`, `--text #e5e7eb`, `--text-dim #9ca3af`, `--text-dim2 #6b7280`,
  `--accent #3b82f6`, `--accent-2 #f97316`, `--green`, `--amber`, `--red`, `--pos`, `--pos-bg`,
  `--arch`, `--arch-bg`.

### What to build

**1. Search history (backend).**

The home screen needs something recent to show, and nothing currently records searches. Extend
`backend/store.py` with a second collection in the same data dir (`searches.json`), holding a
**capped ring of the last 20** searches:

```
id          str        uuid4
created_at  datetime
query       {stats, weights, season_range, active_traits, top_n}
top_results list of {player_name, season, similarity}   just the top 3
prospect_id str | None  set when the search was prefilled from a prospect
```

Routes: `GET /searches` (newest first) and `DELETE /searches` (clear all).

Record an entry inside the existing `POST /similar` handler — after the engine returns, before
responding. Two things matter here: a history-write failure must **never** break a search (wrap it and
log), and the cap must be enforced on write so the file can't grow without bound.

Like the prospect routes, `/searches` should not require the dataset to be loaded.

**2. `frontend/src/screens/HomeScreen.tsx`.**

A landing screen with four regions:

- **Header** — app name, one-line description, and dataset status: player count and row count from
  `/health`, plus a clear "backend offline" treatment when it isn't up.
- **Quick actions** — two prominent cards: "New search" → `/search`, "Add prospect" →
  `/prospects/new`. These are the two things the user starts a session with; make them the visually
  dominant elements.
- **Your prospects** — count, plus the 4–6 most recently updated as compact cards linking to their
  edit screen, and a "see all" link. Reuse the age-derivation helper from Phase 2 rather than
  reimplementing it.
- **Recent searches** — the last ~5 from `GET /searches`: relative timestamp, the stats that were
  specified (name + value, like the existing `.summary-pills` row on the search screen), and the top
  3 matched players. Clicking one re-runs it by navigating to `/search` with those controls restored —
  reuse the Phase 3 prefill mechanism (router state, applied once on mount) instead of building a
  second path for it.

**3. Empty states that teach.**

On a fresh install both lists are empty, and this is the user's actual first screen. Instead of "no
data", each empty region should say what the thing is and offer the action that creates it. Design
this deliberately — a first-run screen that explains itself is worth more than a dense dashboard.

**4. Loading and failure.** Home fetches `/health`, `/prospects`, and `/searches`. Fetch them in
parallel, render each region independently, and let one failure degrade only its own region — a
missing search history should not blank out the prospect list.

### Constraints

- Match the existing dark theme via the CSS variables above; no new palette, no CSS framework, no
  component library, no new dependencies.
- Backend work stays in `backend/` — **`src/` is untouched.**
- Reuse `store.py`'s existing atomic-write and locking approach for `searches.json`; don't invent a
  second persistence mechanism.
- Comments in Greek, technical terms in English.
- TypeScript strict; `npm --prefix frontend run build` must pass.

### Done when

- Fresh launch shows a coherent home screen with working quick actions.
- Running a search then returning home shows it under recent searches; clicking it restores the query.
- Deleting all prospects returns that region to its empty state without errors.
- Stopping the backend degrades home gracefully instead of crashing the renderer.
- Run it and show me what it looks like before calling it done.

---

## After all five

Update `README.md`, `CLAUDE.md`, and `DEVELOPMENT.md` to reflect the new endpoints, screens, and the
`PROSPECTMATCH_DATA_DIR` convention — `CLAUDE.md` already requires docs to be current before a commit.
