function AboutPage() {
  return (
    <section>
      <div className="section-intro">
        <h2>About this Dashboard</h2>
        <p>
          This dashboard was built to support the <strong>VAST Challenge 2022 — Challenge 3: Economic</strong> answer sheet.
          It provides visual analytics tools to explore the financial health of businesses, residents, wages,
          cost of living, employment, and turnover in the fictional city of <strong>Engagement, Ohio</strong>.
        </p>
      </div>

      <div className="chart-grid">

        <div className="chart-card">
          <h3>Challenge Questions</h3>
          <p className="chart-note">The three core questions this dashboard is designed to help answer.</p>
          <div style={{ lineHeight: '1.8', fontSize: '13px' }}>
            <p style={{ marginBottom: '12px' }}>
              <strong>Q1 — Business Health</strong><br />
              Which businesses appear prosperous or struggling? Are there employers that stand out
              as particularly stable or at risk of closing?
            </p>
            <p style={{ marginBottom: '12px' }}>
              <strong>Q2 — Resident Financial Health</strong><br />
              How does resident financial health change over time? How do wages compare to cost of living,
              and which resident groups are most financially vulnerable?
            </p>
            <p>
              <strong>Q3 — Employment &amp; Turnover</strong><br />
              What patterns exist in employment and turnover? Which employers have the highest
              worker instability, and how does the overall workforce participation change?
            </p>
          </div>
        </div>

        <div className="chart-card">
          <h3>Datasets Used</h3>
          <p className="chart-note">Source data from the VAST Challenge 2022 dataset, stored in a local SQLite database.</p>
          <div style={{ lineHeight: '1.9', fontSize: '13px' }}>
            {[
              ['FinancialJournal', 'Monthly income and spending per participant (wages, food, shelter, recreation, education)'],
              ['ParticipantStatusLogs', '72 snapshot tables recording participant job and location state over time'],
              ['Jobs', 'Job listings per employer including hourly rate and education requirement'],
              ['Employers', 'Employer IDs and building locations'],
              ['Participants', 'Demographics: age, education level, joviality, household size, interest group'],
              ['Buildings', 'Building polygons with type (Commercial, Residential, School)'],
              ['CheckinJournal', 'Timestamped venue visits (Workplace, Restaurant, Pub, School)'],
              ['Apartments', 'Residential unit locations'],
            ].map(([name, desc]) => (
              <div key={name} style={{ marginBottom: '8px' }}>
                <strong>{name}</strong>
                <span style={{ color: '#777', marginLeft: '8px' }}>{desc}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="chart-card full-width">
          <h3>Tab Guide</h3>
          <p className="chart-note">What each tab contains and how to use it.</p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', fontSize: '13px' }}>
            {[
              {
                tab: 'Overall View',
                desc: 'A high-level summary answering all three challenge questions at once. Shows KPI cards (total wages, spending, median net income, turnover rate, active employers and earners), a wages vs cost of living line chart, an employer health ranking, a business prosperity scatterplot, and a spatial employer map. Click any employer to highlight it across the ranking, scatter, and map.',
              },
              {
                tab: 'Business Health',
                desc: 'Deep-dive into employer health. Shows a full dashboard with four linked charts: a prosperity/stability scatterplot, an employer health ranking, an employer size and wage distribution chart, and a workplace activity over time chart. Health score is derived from job count, average wage, stable workers, and turnover rate — it is an estimate, not an official measure. Click any employer to highlight it across all four charts.',
              },
              {
                tab: 'Resident Financial Health',
                desc: 'Focuses on participant income and spending. Shows financial categories over time, wages vs cost of living, a net income distribution histogram, average income by education group, and a full-width parallel coordinates chart of individual participant financial profiles. Click an education level in the group chart to highlight matching participants in the parallel coordinates.',
              },
              {
                tab: 'Employment & Turnover',
                desc: 'Focuses on worker movement between employers. Shows a turnover ranking (stacked bars of departed vs arrived workers), a small multiples grid of monthly worker counts per employer, a dual-axis workforce participation chart, and a Sankey diagram of job sector transitions. Click an employer in the ranking to highlight its small multiple panel.',
              },
              {
                tab: 'Map Explorer',
                desc: 'An interactive spatial map of the city. Shows all building footprints (Commercial, Residential, School) and location dots for employers, restaurants, pubs, and schools. Supports zoom and pan. Use the toggle buttons to show or hide building types and location categories. Hover over any building or dot for details.',
              },
            ].map(({ tab, desc }) => (
              <div key={tab} style={{ background: '#f8fafc', borderRadius: '8px', padding: '12px', borderLeft: '3px solid #2f5d8c' }}>
                <div style={{ fontWeight: 'bold', marginBottom: '6px', color: '#2f5d8c' }}>{tab}</div>
                <div style={{ color: '#444', lineHeight: '1.6' }}>{desc}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="chart-card">
          <h3>Important Notes</h3>
          <p className="chart-note">Caveats and interpretation guidance.</p>
          <div style={{ lineHeight: '1.8', fontSize: '13px' }}>
            <div className="answer-box" style={{ marginBottom: '10px' }}>
              <strong>Business health scores are derived estimates.</strong> They are computed from
              job count, average wage, employee stability, and turnover rate — not from direct revenue data.
              FinancialJournal records participant income and spending, not business profit.
            </div>
            <div className="answer-box" style={{ marginBottom: '10px' }}>
              <strong>Job sector transitions use education requirement as a proxy.</strong> The dataset
              does not have explicit sector labels, so the Sankey diagram in Employment &amp; Turnover
              uses the education requirement of a participant's dominant job as a sector proxy.
            </div>
            <div className="answer-box">
              <strong>Turnover is measured between the first and last status log periods.</strong> The
              72 ParticipantStatusLog snapshots span the full study period. Departed = workers present
              at the start who are gone at the end. Arrived = workers not present at the start who
              appear at the end.
            </div>
          </div>
        </div>

      </div>
    </section>
  );
}

export default AboutPage;
