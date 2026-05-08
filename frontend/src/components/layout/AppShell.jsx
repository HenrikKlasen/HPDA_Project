import { NavLink } from 'react-router-dom';

const tabs = [
  { to: '/about', label: 'About' },
  { to: '/overall', label: 'Overall View' },
  { to: '/business', label: 'Business Health' },
  { to: '/residents', label: 'Resident Financial Health' },
  { to: '/employment', label: 'Employment & Turnover' },
  { to: '/map', label: 'Map Explorer' },
];

function AppShell({ children }) {
  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>VAST Challenge 2022 — Challenge 3: Economic</h1>
        <p>
          Visual analytics dashboard for the financial health of businesses,
          residents, wages, cost of living, employment, and turnover in Engagement, Ohio.
        </p>
      </header>

      <main className="app-main">
        <nav className="tabs" aria-label="Dashboard tabs">
          {tabs.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              className={({ isActive }) => `tab-link${isActive ? ' active' : ''}`}
            >
              {tab.label}
            </NavLink>
          ))}
        </nav>

        {children}
      </main>
    </div>
  );
}

export default AppShell;
