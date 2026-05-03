function AboutPage() {
  return (
    <section>
      <h2 className="section-title">About</h2>
      <p className="page-subtitle">Context and guide for this dashboard.</p>

      <div className="card" style={{ maxWidth: '720px', lineHeight: '1.7' }}>
        <h3 className="chart-title">The City of Engagement, Ohio</h3>
        <p>
          Engagement is a small city in Ohio, USA, that is experiencing rapid growth. To prepare for this
          growth, the city launched a participatory urban planning exercise in which around 1,000 representative
          residents agreed to share anonymised data through a city planning app. The data covers where residents
          go, what they spend, and how their jobs and finances change over time.
        </p>
      </div>

      <div className="card" style={{ maxWidth: '720px', lineHeight: '1.7', marginTop: '1rem' }}>
        <h3 className="chart-title">Challenge 3 — Economic</h3>
        <p>
          This dashboard focuses on the economic dimension of the dataset. The goal is to help city planners
          understand the financial health of businesses and residents, identify employment patterns, and
          spot areas of growth or decline.
        </p>
        <p style={{ marginTop: '0.75rem' }}>Three main questions are addressed:</p>
        <ul style={{ paddingLeft: '1.25rem', marginTop: '0.5rem' }}>
          <li><strong>Business Health:</strong> Which businesses are growing or shrinking over time?</li>
          <li><strong>Resident Finances:</strong> How do wages compare to cost of living? Are some groups falling behind?</li>
          <li><strong>Job Market:</strong> Which employers are healthy? Where is turnover highest?</li>
        </ul>
      </div>

      <div className="card" style={{ maxWidth: '720px', lineHeight: '1.7', marginTop: '1rem' }}>
        <h3 className="chart-title">How to use this dashboard</h3>
        <ul style={{ paddingLeft: '1.25rem' }}>
          <li><strong>Overall Finance</strong> — City map showing building locations. Use the filters to explore employers, restaurants, pubs, and schools.</li>
          <li><strong>Business Health</strong> — Revenue trends for individual businesses and a ranked comparison colored by growth rate.</li>
          <li><strong>Cost of Living</strong> — Average wage versus cost of living over time, and a breakdown by income group.</li>
          <li><strong>Job Market</strong> — Employer sizes, turnover rates, and monthly hiring vs departure trends.</li>
        </ul>
      </div>

      <div className="card" style={{ maxWidth: '720px', lineHeight: '1.7', marginTop: '1rem' }}>
        <h3 className="chart-title">Dataset</h3>
        <p>
          The data comes from the VAST Challenge 2022 Mini-Challenge 3. It includes activity logs,
          financial journals, job records, apartment locations, and building maps for approximately
          1,000 participants over a period of several months.
        </p>
      </div>
    </section>
  );
}

export default AboutPage;
