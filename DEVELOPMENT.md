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
│  Vite + TS + Recharts        │ ◄───────────────────── │  FastAPI (backend/)   │
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
| POST   | `/similar`    | top-N όμοιοι παίκτες για user profile |
| POST   | `/classify`   | archetype + trait scores ενός πραγματικού παίκτη |

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
