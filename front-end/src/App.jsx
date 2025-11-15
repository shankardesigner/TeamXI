import { Link, Route, Routes, useNavigate } from "react-router-dom";
import MatchPredictorPage from "./pages/MatchPredictor.jsx";
import XIPredictorPage from "./pages/XIPredictor.jsx";
import BeatAIPage from "./pages/BeatAI.jsx";

function AppShell({ children, showNav = true, showFooter = false }) {
  return (
    <div className="app-root">
      {showNav ? (
        <header className="site-nav">
          <Link to="/" className="nav-wordmark" aria-label="TeamXI Home">
            TeamXI
          </Link>
          <nav className="nav-links">
            <Link to="/xi" className="nav-link">
              XI Predictor
            </Link>
            <Link to="/beat" className="nav-link">
              Beat the AI
            </Link>
          </nav>
        </header>
      ) : null}
      <main className="main-content">
        <div className="main-inner">
          {children}
          {showFooter ? (
            <footer className="site-footer">
              Designed &amp; Developed by <strong>Shankar Bhattarai</strong>{" "}
              <span className="footer-heart" aria-hidden="true">
                &#10084;&#65039;
              </span>
            </footer>
          ) : null}
        </div>
      </main>
    </div>
  );
}

function App() {
  const navigate = useNavigate();
  const onMatchNavigateXI = () => navigate("/xi");

  return (
    <Routes>
      <Route
        path="/"
        element={
          <AppShell showFooter>
            <MatchPredictorPage onNavigateXI={onMatchNavigateXI} />
          </AppShell>
        }
      />
      <Route
        path="/xi"
        element={
          <AppShell showNav={false}>
            <XIPredictorPage onBack={() => navigate("/")} />
          </AppShell>
        }
      />
      <Route
        path="/beat"
        element={
          <AppShell showNav={false}>
            <BeatAIPage onBack={() => navigate("/")} />
          </AppShell>
        }
      />
      <Route
        path="*"
        element={
          <AppShell>
            <MatchPredictorPage onNavigateXI={onMatchNavigateXI} />
          </AppShell>
        }
      />
    </Routes>
  );
}

export default App;