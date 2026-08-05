# ProspectMatch — Electron + FastAPI + React

Desktop migration του Streamlit scouting tool. Τρία layers:

```
┌─────────────────────────────┐
│  Electron (electron/)        │  desktop shell — spawn-άρει τον backend,
│  main.cjs · preload.cjs      │  φορτώνει το React UI
└──────────────┬──────────────┘
               │ loads
┌──────────────▼──────────────┐        HTTP :8000
│  React SPA (frontend/)       │ ─────────────────────► ┌──────────────────────┐
│  Vite + TS (SVG radar)       │ ◄───────────────────── │  FastAPI (backend/)   │
└─────────────────────────────┘   /stats /similar ...   │  wraps src/ engine    │
                                                          └──────────┬───────────┘
                                                                     │ imports
                                                          ┌──────────▼───────────┐
                                                          │  src/ (ΑΜΕΤΑΒΛΗΤΟ)    │
                                                          │  preprocessing        │
                                                          │  archetypes           │
                                                          │  similarity           │
                                                          └──────────────────────┘
```

Ο υπάρχων κώδικας στο `src/` **δεν άλλαξε** — ο backend τον φορτώνει προσθέτοντας
το `src/` στο `sys.path` (βλ. `backend/engine.py`). Ο Streamlit app (`app/`)
συνεχίζει να δουλεύει ανεξάρτητα.

---

## Backend (FastAPI)

### Endpoints

| Method | Path          | Περιγραφή |
|--------|---------------|-----------|
| GET    | `/health`     | liveness + πλήθος παικτών/rows |
| GET    | `/stats`      | feature metadata (ranges/labels/groups) + traits — ο client χτίζει το stat builder από αυτό |
| GET    | `/archetypes` | τα compound archetype presets (traits + eligible positions) |
| GET    | `/players?q=` | autocomplete ονομάτων (diacritic-insensitive) |
| POST   | `/similar`    | top-N όμοιοι παίκτες για user profile (καταγράφει και search history entry) |
| POST   | `/classify`   | archetype + trait scores ενός πραγματικού παίκτη |
| GET    | `/prospects`  | λίστα prospects, πιο πρόσφατα ενημερωμένοι πρώτα |
| GET    | `/prospects/{id}` | ένας prospect, ή 404 |
| POST   | `/prospects`  | νέος prospect (μόνο first/last name υποχρεωτικά) |
| PATCH  | `/prospects/{id}` | partial update |
| DELETE | `/prospects/{id}` | διαγραφή, 204 |
| POST   | `/prospects/{id}/comps` | αποθήκευση ενός NBA comp set πάνω στον prospect |
| DELETE | `/prospects/{id}/comps/{comp_id}` | διαγραφή ενός αποθηκευμένου comp set |
| GET    | `/searches`   | search history, πιο πρόσφατα πρώτα (max 20) |
| DELETE | `/searches`   | καθαρισμός όλου του search history |

Τα `/prospects*` και `/searches*` **δεν** περιμένουν να φορτωθεί το NBA dataset
(όχι `_require_ready()`) — μένουν χρηστικά ενώ το `/health` ακόμα δείχνει `loading`.

### Prospect & search history storage

`backend/store.py` κρατά δύο JSON flat files, `prospects.json` και `searches.json`,
σε φάκελο που αποφασίζεται έτσι:

1. `PROSPECTMATCH_DATA_DIR` env var, αν υπάρχει (το θέτει το `electron/main.cjs`
   στο `app.getPath("userData")` όταν spawn-άρει τον packaged backend).
2. Αλλιώς `./.prospectmatch-data/` — repo-local, μόνο για dev (gitignored).

Κάθε write είναι atomic (temp file → `os.replace()`) και προστατεύεται από
`threading.Lock`, γιατί ο uvicorn τρέχει sync handlers σε threadpool. Τα comps
πάνω σε κάθε prospect και το search history είναι capped στα πιο πρόσφατα 20.

### Data format (ΚΡΙΣΙΜΟ)

Το `/similar` δέχεται **display-unit** τιμές (π.χ. `ts_pct: 62.0` = 62%).
Η μετατροπή display→internal (÷100 για τα pct cols) γίνεται server-side στο
`backend/metadata.py::to_internal` — έτσι η λογική ×100/÷100 ζει σε ΕΝΑ σημείο
και ο client δεν χρειάζεται να ξέρει ποια stats είναι fractions (το `/stats`
εκθέτει `is_pct` για το formatting).

### Τοπικά (standalone)

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# → http://127.0.0.1:8000/docs  (Swagger UI)
```

---

## Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev      # → http://localhost:5173
npm run build    # → frontend/dist/ (base "./" ώστε να τρέχει με file:// στο Electron)
```

Το API base URL είναι το `http://127.0.0.1:8000` (override με `VITE_API_BASE`).

### Routing & screens

`react-router-dom` v6 με **`HashRouter`** — ΟΧΙ `BrowserRouter`. Το packaged app
φορτώνει το UI με `loadFile()` πάνω από `file://`· το `BrowserRouter` στηρίζεται στο
History API πάνω σε πραγματικό origin και δίνει λευκή οθόνη εκεί, ενώ δουλεύει
κανονικά σε dev (Vite σερβίρει πάνω από `http://localhost:5173`). Το `HashRouter`
δουλεύει και στις δύο περιπτώσεις.

- `App.tsx` — shell: `MetaProvider` + `HashRouter` + persistent nav + `<Routes>`.
- `MetaContext.tsx` — το `/stats` fetch-άρεται μία φορά στο mount (`useMeta()` hook)·
  χωρίς αυτό, κάθε screen θα το ξαναφόρτωνε.
- `screens/HomeScreen.tsx`, `SearchScreen.tsx`, `ProspectsScreen.tsx`,
  `ProspectFormScreen.tsx` — μία οθόνη ανά route.
- Prefill mechanism (prospect → search, ή search-history → search): router **state**
  (όχι query params), εφαρμόζεται μία φορά στο mount μέσω ref-guarded `useEffect`
  ώστε να μη σβήνει τις αλλαγές του χρήστη σε επόμενα renders.

---

## Full dev stack (backend + frontend + Electron μαζί)

Από το **root** του project:

```bash
npm install       # εγκαθιστά electron toolchain + (postinstall) τα frontend deps
npm run dev       # concurrently: backend --reload + Vite + Electron
```

Το `npm run dev` κάνει:
0. `predev` → `scripts/preflight-ports.cjs` ελευθερώνει τις πόρτες 8000/5173
   (σκοτώνει ό,τι τις κρατά από προηγούμενο run — αλλιώς ο strictPort Vite / το
   single-bind uvicorn θα αποτύγχαναν σιωπηλά).
1. `dev:backend` → `uvicorn main:app --reload` στο :8000
2. `dev:frontend` → Vite στο 127.0.0.1:5173
3. `dev:electron` → `wait-on` (GET) μέχρι να απαντήσουν και τα δύο, μετά ανοίγει το
   Electron window με `ELECTRON_START_URL=http://127.0.0.1:5173` (hot reload).

Στο dev mode το Electron **δεν** spawn-άρει backend (το κάνει το concurrently).

> **Preflight override:** `PROSPECTMATCH_NO_KILL=1 npm run dev` → το preflight απλώς
> αναφέρει τι τρέχει στις πόρτες και κάνει fail-fast αντί να σκοτώσει διεργασίες
> (χρήσιμο αν κάτι σημαντικό ακούει εκεί).

---

## Packaging (production build)

```bash
npm run dist      # build:frontend + electron-builder → release/
```

**Backend στο packaged app:** ο FastAPI κώδικας (`backend/`, `src/`) και το
`data/nba_stats_full.csv` πακετάρονται ως `extraResources` (βλ. `build.extraResources`
στο `package.json`). Στην εκκίνηση το `electron/main.cjs`:

1. Ψάχνει bundled exe `resources/backend/prospectmatch-backend[.exe]` (PyInstaller).
2. Αλλιώς κάνει fallback σε **system Python**:
   `python run_server.py --host 127.0.0.1 --port 8000`.
3. Περιμένει το `/health` και μετά φορτώνει το `frontend/dist/index.html`.

> Το fallback απαιτεί εγκατεστημένη Python + `pip install -r backend/requirements.txt`
> στο μηχάνημα του χρήστη. Για fully self-contained bundle, χτίσε PyInstaller exe
> με entry το `backend/run_server.py` και βάλ' το στο `resources/backend/`
> (future work — δες `run_server.py`).

---

## Troubleshooting

**Electron: "failed to install correctly"** — το binary download του `electron`
npm package μπορεί να αποτύχει/κολλήσει (extract-zip σε Windows). Η cache του zip
είναι στο `%LOCALAPPDATA%\electron\Cache`. Fix: extract-αρε το zip χειροκίνητα στο
`node_modules/electron/dist/` και γράψε `node_modules/electron/path.txt` με
περιεχόμενο `electron.exe`.

**"Δεν βρέθηκε ο server"** στο UI — ο backend δεν τρέχει στο :8000. Δες αν το
`dev:backend` ξεκίνησε (Swagger στο `/docs`).

**Το Electron window δεν ανοίγει** — σχεδόν πάντα το `wait-on` κόλλησε επειδή μια
πόρτα ήταν κατειλημμένη ή το `/health` δεν απάντησε 2xx. Το `predev` preflight
ελευθερώνει τις πόρτες αυτόματα· αν επιμένει, τρέξε χειροκίνητα:
`netstat -ano | findstr "8000 5173"` και `taskkill /F /PID <pid>`.
