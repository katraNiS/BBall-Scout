// App shell: title bar + dataset status strip + tab bar, γύρω από τα routes.
//
// HashRouter (ΟΧΙ BrowserRouter): το packaged app φορτώνει το UI με loadFile()
// πάνω από file://. Το BrowserRouter στηρίζεται στο History API πάνω σε ένα
// πραγματικό origin και δίνει λευκή οθόνη στο packaged build (ενώ δουλεύει
// κανονικά σε dev, όπου το Vite σερβίρει πάνω από http://localhost:5173).
// Το HashRouter δουλεύει και στις δύο περιπτώσεις.
import { useEffect, useState } from "react";
import { HashRouter, NavLink, Routes, Route, useLocation } from "react-router-dom";

import { api } from "./api";
import { MetaProvider, useMeta } from "./MetaContext";
import { compactCount } from "./statFormat";
import HomeScreen from "./screens/HomeScreen";
import SearchScreen from "./screens/SearchScreen";
import ProspectsScreen from "./screens/ProspectsScreen";
import ProspectFormScreen from "./screens/ProspectFormScreen";

interface Health {
  status: string;
  players: number;
  rows: number;
}

// Οι ετικέτες δεξιά στο tab bar δίνουν στην κάθε οθόνη μια θέση στη ροή
// (workspace → engine → board → record) — μικρή αλλά χρήσιμη πλοήγηση σε ένα
// εργαλείο που ο χρήστης ανοίγει καθημερινά.
const SCREEN_LABELS: { match: RegExp; label: string }[] = [
  { match: /^\/search/, label: "▪2 match engine" },
  { match: /^\/prospects\/(new|.+\/edit)/, label: "▪4 record" },
  { match: /^\/prospects/, label: "▪3 board" },
  { match: /^\/$/, label: "▪1 workspace" },
];

function TitleBar() {
  return (
    <div className="titlebar">
      <span className="titlebar-mark" />
      <span className="titlebar-name">ProspectMatch</span>
      <span className="titlebar-meta">nba_stats_full.csv</span>
    </div>
  );
}

function StatusStrip({ health, featureCount }: { health: Health | null; featureCount: number }) {
  const ready = health?.status === "ok";

  return (
    <div className="statusstrip">
      <span className="status-state">
        <span className={`status-dot${ready ? "" : " pending"}`} />
        <span>{ready ? "DATASET READY" : "LOADING"}</span>
      </span>
      {health && (
        <>
          <span>{compactCount(health.rows)} season-rows</span>
          <span className="sep">|</span>
          <span>{compactCount(health.players)} players</span>
          <span className="sep">|</span>
          <span>{featureCount} features</span>
        </>
      )}
      <span className="push">tracking coverage 2016+ · defensive matchups 2013+</span>
      <span className="sep">|</span>
      <span>{api.base.replace(/^https?:\/\//, "")}</span>
    </div>
  );
}

function TabBar() {
  const { pathname } = useLocation();
  const label = SCREEN_LABELS.find((s) => s.match.test(pathname))?.label ?? "";

  return (
    <nav className="tabbar">
      <NavLink to="/" end className={({ isActive }) => `tab${isActive ? " active" : ""}`}>
        Home
      </NavLink>
      <NavLink to="/search" className={({ isActive }) => `tab${isActive ? " active" : ""}`}>
        Search
      </NavLink>
      <NavLink to="/prospects" className={({ isActive }) => `tab${isActive ? " active" : ""}`}>
        Prospects
      </NavLink>
      <span className="tabbar-right">{label}</span>
    </nav>
  );
}

function Shell() {
  const { error, stats } = useMeta();
  const [health, setHealth] = useState<Health | null>(null);

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  // Backend offline: πλήρης οθόνη σφάλματος για κάθε route — χωρίς /stats δεν
  // υπάρχει stat builder, οπότε κάθε οθόνη θα ήταν κέλυφος.
  if (error) {
    return (
      <div className="app">
        <TitleBar />
        <div className="fatal">
          <div className="fatal-box notice-box">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#c58e4a" strokeWidth="1.5">
              <path d="M12 9v4m0 4h.01M10.3 3.9 2.4 17.5A1.9 1.9 0 0 0 4 20.4h16a1.9 1.9 0 0 0 1.6-2.9L13.7 3.9a1.9 1.9 0 0 0-3.4 0Z" />
            </svg>
            <div>
              <div className="notice-box-title">Αποτυχία σύνδεσης με τον backend</div>
              <div className="notice-box-body">
                {error}
                <br />
                Ξεκίνα τον server με <code className="mono">uvicorn main:app</code> μέσα στο{" "}
                <code className="mono">backend/</code>, ή τρέξε <code className="mono">npm run dev</code>{" "}
                από τη ρίζα του project.
              </div>
              <div className="notice-box-actions">
                <button type="button" className="linkbtn" onClick={() => window.location.reload()}>
                  Επανάληψη
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <TitleBar />
      <StatusStrip health={health} featureCount={stats.length} />
      <TabBar />
      <Routes>
        <Route path="/" element={<HomeScreen />} />
        <Route path="/search" element={<SearchScreen />} />
        <Route path="/prospects" element={<ProspectsScreen />} />
        <Route path="/prospects/new" element={<ProspectFormScreen />} />
        <Route path="/prospects/:id/edit" element={<ProspectFormScreen />} />
      </Routes>
    </div>
  );
}

export default function App() {
  return (
    <MetaProvider>
      <HashRouter>
        <Shell />
      </HashRouter>
    </MetaProvider>
  );
}
