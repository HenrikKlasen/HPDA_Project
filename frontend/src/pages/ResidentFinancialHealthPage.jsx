function ResidentFinancialHealthPage() {
  return (
    <section>
      <div className="section-intro">
        <h2>Resident Financial Health</h2>
        <p>
          Wages, expenses, net income, cost of living, and resident groups with similar patterns.
          FinancialJournal is interpreted as participant income and spending.
        </p>
      </div>

      <div className="chart-grid">

        <div className="chart-card">
          <h3>Financial Categories Over Time</h3>
          <p className="chart-note">Monthly totals by category: wages, food, shelter, recreation, education.</p>
          <div className="chart-placeholder">Chart placeholder — line chart</div>
        </div>

        <div className="chart-card">
          <h3>Wages vs Cost of Living</h3>
          <p className="chart-note">Monthly wage income, living costs, and net income.</p>
          <div className="chart-placeholder">Chart placeholder — line chart</div>
        </div>

        <div className="chart-card">
          <h3>Net Income Distribution</h3>
          <p className="chart-note">Per-participant net income histogram over the study period.</p>
          <div className="chart-placeholder">Chart placeholder — histogram</div>
        </div>

        <div className="chart-card">
          <h3>Net Income by Education Group</h3>
          <p className="chart-note">Average wage, expenses, and net income broken down by education level.</p>
          <div className="chart-placeholder">Chart placeholder — grouped bar chart</div>
        </div>

        <div className="chart-card full-width">
          <h3>Resident Financial Profiles (Parallel Coordinates)</h3>
          <p className="chart-note">Each line = one participant. Axes: wage, expenses, net income, joviality, age, household size.</p>
          <div className="chart-placeholder">Chart placeholder — parallel coordinates</div>
        </div>

      </div>
    </section>
  );
}

export default ResidentFinancialHealthPage;
