import { Navigate, Route, Routes } from 'react-router-dom';
import AppShell from './components/layout/AppShell';
import AboutPage from './pages/AboutPage';
import BusinessHealthPage from './pages/BusinessHealthPage';
import EmploymentTurnoverPage from './pages/EmploymentTurnoverPage';
import MapExplorerPage from './pages/MapExplorerPage';
import OverallViewPage from './pages/OverallViewPage';
import ResidentFinancialHealthPage from './pages/ResidentFinancialHealthPage';

function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/about" element={<AboutPage />} />
        <Route path="/overall" element={<OverallViewPage />} />
        <Route path="/business" element={<BusinessHealthPage />} />
        <Route path="/residents" element={<ResidentFinancialHealthPage />} />
        <Route path="/employment" element={<EmploymentTurnoverPage />} />
        <Route path="/map" element={<MapExplorerPage />} />
        <Route path="*" element={<Navigate to="/about" replace />} />
      </Routes>
    </AppShell>
  );
}

export default App;
