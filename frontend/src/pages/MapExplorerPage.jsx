import BuildingsMap from '../components/maps/BuildingsMap';

function MapExplorerPage() {
  return (
    <section>
      <div className="section-intro">
        <h2>Map Explorer</h2>
        <p>
          This tab focuses on spatial employer health, turnover, wage level, and employer size.
        </p>
      </div>

      <div className="map-layout">
        <div className="chart-card large">
          <h3>Employer Symbol Map</h3>
          <p className="chart-note">
            Large version of the map with controls for color mode and selected employer.
          </p>
          <BuildingsMap />
        </div>

        <aside className="details-panel">
          <h3>Selected Employer Details</h3>

          <div className="details-row">
            <span>Employer ID</span>
            <strong>—</strong>
          </div>
          <div className="details-row">
            <span>Sector</span>
            <strong>—</strong>
          </div>
          <div className="details-row">
            <span>Job Count</span>
            <strong>—</strong>
          </div>
          <div className="details-row">
            <span>Average Hourly Rate</span>
            <strong>—</strong>
          </div>
          <div className="details-row">
            <span>Turnover Count</span>
            <strong>—</strong>
          </div>
          <div className="details-row">
            <span>Turnover Rate</span>
            <strong>—</strong>
          </div>
          <div className="details-row">
            <span>Health Category</span>
            <strong>—</strong>
          </div>

          <div className="chart-placeholder" style={{ marginTop: '18px', minHeight: '160px' }}>
            Click an employer on the map to see details here.
          </div>
        </aside>
      </div>
    </section>
  );
}

export default MapExplorerPage;
