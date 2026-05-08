function OverallViewPage() {
  return (
    <section>
      <div className="section-intro">
        <h2>Overall View</h2>
        <p>
          Main summary evidence for the three challenge questions — KPIs, wages vs cost of living,
          employer health ranking, prosperity scatter, and spatial map.
        </p>
      </div>

      <div className="chart-grid">

        <div className="chart-card full-width">
          <h3>KPI Summary</h3>
          <p className="chart-note">Key performance indicators: total wages, spending, median net income, turnover rate, active employers and earners.</p>
          <div className="chart-placeholder">Chart placeholder — KPI cards</div>
        </div>

        <div className="chart-card">
          <h3>Wages vs Cost of Living</h3>
          <p className="chart-note">Monthly wage income, living costs, and net income over time.</p>
          <div className="chart-placeholder">Chart placeholder — line chart</div>
        </div>

        <div className="chart-card">
          <h3>Employer Health Ranking</h3>
          <p className="chart-note">Employers ranked by derived health score.</p>
          <div className="chart-placeholder">Chart placeholder — bar ranking</div>
        </div>

        <div className="chart-card">
          <h3>Business Prosperity Scatterplot</h3>
          <p className="chart-note">Avg hourly rate vs job count. Dot size = stable workers.</p>
          <div className="chart-placeholder">Chart placeholder — scatter</div>
        </div>

        <div className="chart-card">
          <h3>Employer Symbol Map</h3>
          <p className="chart-note">Employer locations with size = job count, colour = health category.</p>
          <div className="chart-placeholder">Chart placeholder — map</div>
        </div>

      </div>
    </section>
  );
}

export default OverallViewPage;
