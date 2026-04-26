import { useState } from 'react';
import DateRangeFilter from '../features/filters/DateRangeFilter';
import { useAnalyticsData } from '../hooks/useAnalyticsData';

function AudienceInsightsPage() {
  const [period, setPeriod] = useState('30d');
  const { data, loading, error } = useAnalyticsData(period);

  if (loading) return <p>Loading audience insights...</p>;
  if (error) return <p>{error}</p>;
  if (!data) return <p>No audience data available.</p>;

  return (
    <section>
      <h2 className="section-title">Audience Insights</h2>
      <p className="page-subtitle">Understand where users come from and how they distribute by channel.</p>
      <DateRangeFilter value={period} onChange={setPeriod} />

      <div className="card">
        <h3 className="chart-title">Traffic source share</h3>
        <ul className="simple-list">
          {data.sources.map((source) => (
            <li key={source.source}>
              <span>{source.source}</span>
              <strong>{source.value}%</strong>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

export default AudienceInsightsPage;
