import { useState } from 'react';
import HorizontalBarChart from '../components/charts/HorizontalBarChart';
import MultiLineChart from '../components/charts/MultiLineChart';
import KpiCard from '../components/kpi/KpiCard';
import { mockBusinessHealth } from '../data/mockEconomics';

function EventPerformancePage() {
  const { revenueTrend, businessRanking } = mockBusinessHealth;
  const [selectedBusiness, setSelectedBusiness] = useState(null);

  const totalBusinesses = businessRanking.length;
  const growingCount = businessRanking.filter((b) => b.growth >= 0).length;
  const shrinkingCount = businessRanking.filter((b) => b.growth < 0).length;
  let topGrowthRate = businessRanking[0].growth;
  for (let i = 1; i < businessRanking.length; i++) {
    if (businessRanking[i].growth > topGrowthRate) {
      topGrowthRate = businessRanking[i].growth;
    }
  }

  function handleSelectBusiness(label) {
    setSelectedBusiness((prev) => (prev === label ? null : label));
  }

  return (
    <section>
      <h2 className="section-title">Business Health</h2>
      <p className="page-subtitle">Monthly revenue by business over time — identify who is growing and who is struggling.</p>

      <div className="grid kpis">
        <KpiCard title="Total Businesses" value={totalBusinesses} />
        <KpiCard title="Growing" value={growingCount} />
        <KpiCard title="Struggling" value={shrinkingCount} />
        <KpiCard title="Top Growth Rate" value={`+${topGrowthRate}%`} />
      </div>

      <div className="grid charts">
        <MultiLineChart data={revenueTrend} title="Monthly Revenue by Business ($)" highlightName={selectedBusiness} onSelect={handleSelectBusiness} />
        <HorizontalBarChart
          data={businessRanking}
          title="Total Revenue Ranking — green = growing, red = shrinking"
          valueFormat={(v) => `$${(v / 1000).toFixed(0)}k`}
          colorByGrowth
          selected={selectedBusiness}
          onSelect={handleSelectBusiness}
        />
      </div>
    </section>
  );
}

export default EventPerformancePage;
