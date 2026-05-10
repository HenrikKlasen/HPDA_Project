import React from "react";

function AboutPage() {
  return (
    <section>
      <div className="section-intro">
        <h2>Dashboard User Guide & Project Overview</h2>
        <p>
          This dashboard was built to support the{" "}
          <strong>VAST Challenge 2022 — Challenge 3: Economic</strong> answer
          sheet. <br /> It provides visual analytics tools to explore the
          financial health of businesses, residents, wages, cost of living,
          employment, and turnover in the fictional city of{" "}
          <strong>Engagement, Ohio</strong>.
        </p>
      </div>

      <div className="chart-grid">
        <div className="chart-card">
          <h3>Challenge Questions</h3>
          <p className="chart-note">
            The three core questions this dashboard is designed to help answer.
          </p>
          <div style={{ lineHeight: "1.8", fontSize: "13px" }}>
            <p style={{ marginBottom: "12px" }}>
              <strong>Q1 — Business Health</strong>
              <br />
              Which businesses appear prosperous or struggling? Are there
              employers that stand out as particularly stable or at risk of
              closing?
            </p>
            <p style={{ marginBottom: "12px" }}>
              <strong>Q2 — Resident Financial Health</strong>
              <br />
              How does resident financial health change over time? How do wages
              compare to cost of living, and which resident groups are most
              financially vulnerable?
            </p>
            <p>
              <strong>Q3 — Employment &amp; Turnover</strong>
              <br />
              What patterns exist in employment and turnover? Which employers
              have the highest worker instability, and how does the overall
              workforce participation change?
            </p>
          </div>
        </div>

        <div className="chart-card">
          <h3>Datasets Used</h3>
          <p className="chart-note">
            Source data from the VAST Challenge 2022 dataset, stored in a local
            SQLite database.
          </p>
          <div style={{ lineHeight: "1.9", fontSize: "13px" }}>
            {[
              [
                "FinancialJournal",
                "Monthly income and spending per participant (wages, food, shelter, recreation, education)",
              ],
              [
                "ParticipantStatusLogs",
                "72 snapshot tables recording participant job and location state over time",
              ],
              [
                "Jobs",
                "Job listings per employer including hourly rate and education requirement",
              ],
              ["Employers", "Employer IDs and building locations"],
              [
                "Participants",
                "Demographics: age, education level, joviality, household size, interest group",
              ],
              [
                "Buildings",
                "Building polygons with type (Commercial, Residential, School)",
              ],
              [
                "CheckinJournal",
                "Timestamped venue visits (Workplace, Restaurant, Pub, School)",
              ],
              ["Apartments", "Residential unit locations"],
            ].map(([name, desc]) => (
              <div key={name} style={{ marginBottom: "8px" }}>
                <strong>{name}</strong>
                <span style={{ color: "#777", marginLeft: "8px" }}>{desc}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="chart-card full-width">
          <h3>Tab Guide</h3>
          <p className="chart-note">
            What each tab contains and how to use it.
          </p>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, 1fr)",
              gap: "16px",
              fontSize: "13px",
            }}
          >
            {[
              {
                tab: "City Pulse",
                desc: "An executive summary providing a high-level overview of city economic health. Features six KPI cards for rapid inspection, city-wide wage trends, an employer prosperity map, and a detailed education-level wage breakdown.",
              },
              {
                tab: "Enterprise Health",
                desc: "A deep-dive into business stability. Linked charts allow you to correlate hourly rates with job listings and turnover. Click any employer to instantly highlight its specific workplace activity and size metrics across the entire dashboard. An Explorer Map is provided to select a specific employer to know more about them in detail, just click on one point in the map, and you will be redirected to enterprise dashboard for that employer.",
              },
              {
                tab: "Citizen Finances",
                desc: "Focuses on the financial well-being of Engagement's citizens. Includes expense category tracking and a Parallel Coordinates chart for individual financial profiling. Click education groups to filter the participant profile map.",
              },
              {
                tab: "Labor Dynamics",
                desc: "The core engine for workforce analysis. Features a dual-view toggle: 'Statistical Trends' for city-wide participation and work-life balance correlations, and 'Mobility Network' for a geographical view of job transfers between employers.",
              },
            ].map(({ tab, desc }) => (
              <div
                key={tab}
                style={{
                  background: "#f8fafc",
                  borderRadius: "8px",
                  padding: "12px",
                  borderLeft: "3px solid #2f5d8c",
                  transition: "transform 0.2s, box-shadow 0.2s",
                }}
                className="guide-card"
              >
                <div
                  style={{
                    fontWeight: "bold",
                    marginBottom: "6px",
                    color: "#2f5d8c",
                  }}
                >
                  {tab}
                </div>
                <div style={{ color: "#444", lineHeight: "1.6" }}>{desc}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="chart-card">
          <h3>Data Interpretation</h3>
          <p className="chart-note">Technical caveats and data proxies.</p>
          <div style={{ lineHeight: "1.8", fontSize: "13px" }}>
            <div className="answer-box" style={{ marginBottom: "10px" }}>
              <strong>Business health scores are derived estimates.</strong>{" "}
              <br />
              Computed as: 0.25×(jobs) + 0.25×(avg rate) + 0.25×(stable) −
              0.25×(turnover rate). This represents a relative prosperity index
              compared to other city employers, not an absolute financial
              profit.
            </div>
            <div className="answer-box" style={{ marginBottom: "10px" }}>
              <strong>Lifestyle Scatter (Leisure vs Productivity).</strong>{" "}
              <br />
              The 'Labor Dynamics' scatter plot samples 1,000 residents to
              maintain high frame rates. It correlates workplace visits with
              Pub/Restaurant visits to proxy for work-life balance and social
              engagement.
            </div>
            <div className="answer-box">
              <strong>Turnover measurement intervals.</strong> <br />
              Mobility and turnover are calculated by comparing worker snapshots
              at the absolute start and end of the study period (spanned by 72
              status logs) to identify long-term labor migration patterns.
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export default AboutPage;
