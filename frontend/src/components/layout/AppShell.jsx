import { NavLink } from 'react-router-dom';

const tabs = [
  { to: '/overview', label: 'Overview' },
  { to: '/audience', label: 'Audience Insights' },
  { to: '/performance', label: 'Event Performance' },
  { to: '/reports', label: 'Reports & Export' },
];

function AppShell({ children }) {
  return (
    <div className="app-shell">
      <header className="app-header">
        <h1 className="page-title">HPDA Analytics Dashboard</h1>
        <nav className="tabs" aria-label="Analytics tasks">
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
      </header>
      <main className="app-main">{children}</main>
    </div>
  );
}

export default AppShell;
