import { NavLink, Route, Routes } from "react-router-dom";
import { MOCK_MODE, api } from "./api/client";
import { CitationProvider } from "./components/CitationDrawer";
import { EmptyState } from "./components/Feedback";
import { Icon, type IconName } from "./components/Icon";
import { useTheme } from "./lib/theme";
import { useAsync } from "./lib/useAsync";
import { ChatPage } from "./pages/ChatPage";
import { ComparePage } from "./pages/ComparePage";
import { DatasetsPage } from "./pages/DatasetsPage";
import { LeaderboardPage } from "./pages/LeaderboardPage";
import { RunsPage } from "./pages/RunsPage";
import { StagesPage } from "./pages/StagesPage";

const NAV: { to: string; label: string; icon: IconName }[] = [
  { to: "/", label: "Compare", icon: "compare" },
  { to: "/leaderboard", label: "Leaderboard", icon: "trophy" },
  { to: "/stages", label: "Stages", icon: "stages" },
  { to: "/datasets", label: "Datasets", icon: "database" },
  { to: "/runs", label: "Runs", icon: "list" },
  { to: "/chat", label: "Chat", icon: "chat" },
];

function ThemeToggle() {
  const { pref, cycle } = useTheme();
  const icon: IconName = pref === "light" ? "sun" : pref === "dark" ? "moon" : "monitor";
  return (
    <button className="btn ghost sm" onClick={cycle} title={`Theme: ${pref} (click to change)`} aria-label={`Theme: ${pref}`}>
      <Icon name={icon} size={14} />
      <span className="health-label">{pref === "system" ? "System" : pref === "light" ? "Light" : "Dark"}</span>
    </button>
  );
}

function Health() {
  const { data, error } = useAsync(() => api.health(), []);
  const state = error ? "bad" : data?.ok ? "ok" : "";
  const title = error
    ? `API unreachable: ${error.message}`
    : data
      ? `index ${data.index} · ${data.models_with_keys} models with keys`
      : "Checking API…";
  return (
    <div className="health" title={title}>
      <span className={`dot ${state}`} />
      <span className="health-label">{MOCK_MODE ? "Mock data" : error ? "API offline" : data ? "API online" : "Connecting…"}</span>
    </div>
  );
}

export function App() {
  return (
    <CitationProvider>
      <div className="app">
        <aside className="sidebar">
          <NavLink to="/" className="brand" aria-label="Loupe Bench home">
            <Icon name="logo" size={20} />
            <span>Loupe Bench</span>
          </NavLink>
          <nav className="nav" aria-label="Main">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.to === "/"}>
                <Icon name={n.icon} />
                {n.label}
              </NavLink>
            ))}
          </nav>
          <div className="sidebar-foot">
            <Health />
            <ThemeToggle />
          </div>
        </aside>
        <main className="main">
          <Routes>
            <Route path="/" element={<ComparePage />} />
            <Route path="/leaderboard" element={<LeaderboardPage />} />
            <Route path="/stages" element={<StagesPage />} />
            <Route path="/datasets" element={<DatasetsPage />} />
            <Route path="/runs" element={<RunsPage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="*" element={<EmptyState icon="search" title="Page not found">Use the sidebar to pick a page.</EmptyState>} />
          </Routes>
        </main>
      </div>
    </CitationProvider>
  );
}
