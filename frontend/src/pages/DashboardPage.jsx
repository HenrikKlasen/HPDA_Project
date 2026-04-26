import { useState } from 'react';
import CategoryBarChart from '../components/charts/CategoryBarChart';
import LineTrendChart from '../components/charts/LineTrendChart';
import SourcePieChart from '../components/charts/SourcePieChart';
import KpiCard from '../components/kpi/KpiCard';
import BuildingsMap from '../components/maps/BuildingsMap';
import DateRangeFilter from '../features/filters/DateRangeFilter';
import { useAnalyticsData } from '../hooks/useAnalyticsData';
import { formatDuration, formatPercent } from '../utils/metrics';

function DashboardPage() {
  const [period, setPeriod] = useState('7d');
  const { data, loading, error } = useAnalyticsData(period);

  if (loading) return <p>Loading dashboard...</p>;
  if (error) return <p>{error}</p>;
  if (!data) return <p>No analytics data available.</p>;

  return (
    <section>
      <p className="page-subtitle">Quick overview of platform behavior and KPIs.</p>

      <DateRangeFilter value={period} onChange={setPeriod} />

      <div className="grid kpis">
        <KpiCard title="Visits" value={data.summary.visits.toLocaleString()} />
        <KpiCard title="Unique users" value={data.summary.uniqueUsers.toLocaleString()} />
        <KpiCard title="Conversion rate" value={formatPercent(data.summary.conversionRate)} />
        <KpiCard
          title="Avg session duration"
          value={formatDuration(data.summary.avgSessionDuration)}
        />
      </div>

      <div style={{ display: 'flex', gap: '20px', height: '900px' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <BuildingsMap />
        </div>
        <div style={{ flex: 1, minWidth: 0, overflowY: 'auto' }}>
          <div className="grid charts">
            <LineTrendChart data={data.trend} />
            <CategoryBarChart data={data.categories} />
            <SourcePieChart data={data.sources} />
          </div>
        </div>
      </div>
    </section>
  );
}

export default DashboardPage;
