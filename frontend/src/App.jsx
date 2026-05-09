import { Navigate, Route, Routes } from 'react-router-dom';
import AppShell from './components/layout/AppShell';
import AboutPage from './pages/AboutPage';
import BusinessHealthPage from './pages/BusinessHealthPage';
import EmploymentTurnoverPage from './pages/EmploymentTurnoverPage';
import EmploymentNetworkMapPage from './pages/EmploymentNetworkMapPage';
import MapExplorerPage from './pages/MapExplorerPage';
import EmployerDetailPage from './pages/EmployerDetailPage';
import EmployerFinancialsDashboard from './pages/EmployerFinancialsDashboard';
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
        <Route path="/network-map" element={<EmploymentNetworkMapPage />} />
        <Route path="/map" element={<MapExplorerPage />} />
        <Route path="/employer/:id" element={<EmployerDetailPage />} />
        <Route path="/employer/:id/financials" element={<EmployerFinancialsDashboard />} />
        <Route path="*" element={<Navigate to="/about" replace />} />
      </Routes>
    </AppShell>
  );
}

export default App;
