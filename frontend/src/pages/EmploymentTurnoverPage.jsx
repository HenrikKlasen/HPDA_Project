function EmploymentTurnoverPage() {
  return (
    <section>
      <div className="section-intro">
        <h2>Employment &amp; Turnover</h2>
        <p>
          Employer stability, worker movement, job turnover, and changes in labor participation over time.
        </p>
      </div>

      <div className="chart-grid">

        <div className="chart-card">
          <h3>Turnover Ranking by Employer</h3>
          <p className="chart-note">Employers ranked by worker turnover count — departed vs arrived workers.</p>
          <div className="chart-placeholder">Chart placeholder — stacked bar ranking</div>
        </div>

        <div className="chart-card">
          <h3>Monthly Worker Count — Small Multiples</h3>
          <p className="chart-note">Monthly workplace check-in counts per employer (top 16).</p>
          <div className="chart-placeholder">Chart placeholder — small multiples grid</div>
        </div>

        <div className="chart-card">
          <h3>Workforce Participation Over Time</h3>
          <p className="chart-note">Active wage earners (left axis) and average wage per worker (right axis) by month.</p>
          <div className="chart-placeholder">Chart placeholder — dual-axis line chart</div>
        </div>

        <div className="chart-card">
          <h3>Job Transitions Between Sectors</h3>
          <p className="chart-note">Participant movement by job sector between the first and last study period.</p>
          <div className="chart-placeholder">Chart placeholder — Sankey diagram</div>
        </div>

      </div>
    </section>
  );
}

export default EmploymentTurnoverPage;
