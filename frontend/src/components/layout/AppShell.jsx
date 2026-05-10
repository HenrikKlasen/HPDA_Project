import React, { useEffect, useState } from "react";
import { NavLink, useNavigate, useLocation } from "react-router-dom";

const tabs = [
  { to: "/about", label: "Guide", shortcut: "1" },
  { to: "/overall", label: "City Pulse", shortcut: "2" },
  { to: "/business", label: "Enterprise Health", shortcut: "3" },
  {
    to: "/residents",
    label: "Citizen Finances",
    shortcut: "4",
  },
  {
    to: "/employment",
    label: "Labor Dynamics",
    shortcut: "5",
  },
];

function AppShell({ children }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [showBackToTop, setShowBackToTop] = useState(false);
  const [isScrolled, setIsScrolled] = useState(false);

  // Scroll logic
  useEffect(() => {
    window.scrollTo(0, 0);

    const handleScroll = () => {
      setShowBackToTop(window.scrollY > 400);
      setIsScrolled(window.scrollY > 120);
    };

    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, [location.pathname]);

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Alt + number for tab navigation
      if (e.altKey && e.key >= "1" && e.key <= String(tabs.length)) {
        e.preventDefault();
        const tabIndex = parseInt(e.key) - 1;
        navigate(tabs[tabIndex].to);
      }
      // Ctrl/Cmd + H for home (About page)
      if ((e.ctrlKey || e.metaKey) && e.key === "h") {
        e.preventDefault();
        navigate("/about");
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [navigate]);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="header-content">
          <div>
            <h1>VAST Challenge 2022 — Challenge 3: Economic</h1>
            <p>
              Visual analytics dashboard for the financial health of businesses,
              residents, wages, cost of living, employment, and turnover in
              Engagement, Ohio.
            </p>
          </div>
          <div className="header-help">
            <span className="help-text" title="Keyboard shortcuts available">
              Press <kbd>Alt</kbd> + <kbd>1-{tabs.length}</kbd> to navigate tabs
            </span>
          </div>
        </div>
      </header>

      <main className="app-main">
        <div
          className={`tabs-sticky-container ${isScrolled ? "scrolled" : ""}`}
        >
          <nav className="tabs" aria-label="Dashboard tabs">
            {tabs.map((tab) => (
              <NavLink
                key={tab.to}
                to={tab.to}
                className={({ isActive }) =>
                  `tab-link${isActive ? " active" : ""}`
                }
                title={`${tab.label} (Alt+${tab.shortcut})`}
              >
                <span className="tab-label">{tab.label}</span>
                <span className="tab-shortcut">{tab.shortcut}</span>
              </NavLink>
            ))}
          </nav>
        </div>

        {children}
        <button
          className={`back-to-top ${showBackToTop ? "visible" : ""}`}
          onClick={scrollToTop}
          title="Back to Top"
        >
          🢁
        </button>
      </main>
    </div>
  );
}

export default AppShell;
