import { NavLink } from 'react-router-dom';

const tabs = [
  { to: '/about', label: 'About' },
  { to: '/overview', label: 'Overall Finance' },
  { to: '/performance', label: 'Business Health' },
  { to: '/audience', label: 'Cost of Living' },
  { to: '/reports', label: 'Job Market' },
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
