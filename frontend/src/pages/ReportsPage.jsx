import { useState } from 'react';
import DateRangeFilter from '../features/filters/DateRangeFilter';
import { useAnalyticsData } from '../hooks/useAnalyticsData';

function ReportsPage() {
  const [period, setPeriod] = useState('90d');
  const { data, loading, error } = useAnalyticsData(period);

  if (loading) return <p>Preparing reports...</p>;
  if (error) return <p>{error}</p>;
  if (!data) return <p>No report data available.</p>;

  return (
    <section>
      <h2 className="section-title">Reports & Export</h2>
      <p className="page-subtitle">Generate quick snapshots and export selected KPIs for offline analysis.</p>
      <DateRangeFilter value={period} onChange={setPeriod} />

      <div className="card">
        <h3 className="chart-title">Report preview</h3>
        <ul className="simple-list">
          <li>
            <span>Total visits</span>
            <strong>{data.summary.visits.toLocaleString()}</strong>
          </li>
          <li>
            <span>Unique users</span>
            <strong>{data.summary.uniqueUsers.toLocaleString()}</strong>
          </li>
          <li>
            <span>Top source</span>
            <strong>{data.sources[0]?.source ?? 'N/A'}</strong>
          </li>
        </ul>
      </div>
    </section>
  );
}

export default ReportsPage;
