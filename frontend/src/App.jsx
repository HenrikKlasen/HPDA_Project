import { Navigate, Route, Routes } from 'react-router-dom';
import AppShell from './components/layout/AppShell';
import AboutPage from './pages/AboutPage';
import AudienceInsightsPage from './pages/AudienceInsightsPage';
import DashboardPage from './pages/DashboardPage';
import EventPerformancePage from './pages/EventPerformancePage';
import ReportsPage from './pages/ReportsPage';

function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/overview" element={<DashboardPage />} />
        <Route path="/audience" element={<AudienceInsightsPage />} />
        <Route path="/performance" element={<EventPerformancePage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/about" element={<AboutPage />} />
        <Route path="*" element={<Navigate to="/overview" replace />} />
      </Routes>
    </AppShell>
  );
}

export default App;
