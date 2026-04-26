import { useState } from 'react';
import DateRangeFilter from '../features/filters/DateRangeFilter';
import { useAnalyticsData } from '../hooks/useAnalyticsData';

function EventPerformancePage() {
  const [period, setPeriod] = useState('7d');
  const { data, loading, error } = useAnalyticsData(period);

  if (loading) return <p>Loading event performance...</p>;
  if (error) return <p>{error}</p>;
  if (!data) return <p>No event performance data available.</p>;

  return (
    <section>
      <h2 className="section-title">Event Performance</h2>
      <p className="page-subtitle">Track top event categories and detect which actions drive engagement.</p>
      <DateRangeFilter value={period} onChange={setPeriod} />

      <div className="card">
        <h3 className="chart-title">Top categories by count</h3>
        <ul className="simple-list">
          {data.categories.map((category) => (
            <li key={category.category}>
              <span>{category.category}</span>
              <strong>{category.count.toLocaleString()}</strong>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

export default EventPerformancePage;
