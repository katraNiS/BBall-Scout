// App shell: MetaProvider + router + persistent nav + routes.
//
// HashRouter (ΟΧΙ BrowserRouter): το packaged app φορτώνει το UI με loadFile()
// πάνω από file://. Το BrowserRouter στηρίζεται στο History API πάνω σε ένα
// πραγματικό origin και δίνει λευκή οθόνη στο packaged build (ενώ δουλεύει
// κανονικά σε dev, όπου το Vite σερβίρει πάνω από http://localhost:5173).
// Το HashRouter δουλεύει και στις δύο περιπτώσεις.
import { HashRouter, NavLink, Routes, Route } from "react-router-dom";

import { MetaProvider, useMeta } from "./MetaContext";
import HomeScreen from "./screens/HomeScreen";
import SearchScreen from "./screens/SearchScreen";
import ProspectsScreen from "./screens/ProspectsScreen";
import ProspectFormScreen from "./screens/ProspectFormScreen";

function Nav() {
  return (
    <nav className="top-nav">
      <span className="top-nav-brand">🏀 ProspectMatch</span>
      <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>
        Home
      </NavLink>
      <NavLink to="/search" className={({ isActive }) => (isActive ? "active" : "")}>
        Search
      </NavLink>
      <NavLink to="/prospects" className={({ isActive }) => (isActive ? "active" : "")}>
        Prospects
      </NavLink>
    </nav>
  );
}

function Shell() {
  const { error } = useMeta();

  // Backend offline: πλήρης οθόνη σφάλματος, για κάθε route — όχι μόνο search.
  if (error) {
    return (
      <div className="state-msg">
        <div className="error-box" style={{ maxWidth: 480, margin: "80px auto" }}>
          <b>Αποτυχία σύνδεσης με τον backend.</b>
          <div style={{ marginTop: 8 }}>{error}</div>
          <div style={{ marginTop: 10, color: "var(--text-dim2)" }}>
            Ξεκίνα τον server: <code>uvicorn main:app</code> στο <code>backend/</code>.
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      <Nav />
      <Routes>
        <Route path="/" element={<HomeScreen />} />
        <Route path="/search" element={<SearchScreen />} />
        <Route path="/prospects" element={<ProspectsScreen />} />
        <Route path="/prospects/new" element={<ProspectFormScreen />} />
        <Route path="/prospects/:id/edit" element={<ProspectFormScreen />} />
      </Routes>
    </>
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
