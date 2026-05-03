import GroupedBarChart from '../components/charts/GroupedBarChart';
import MultiLineChart from '../components/charts/MultiLineChart';
import KpiCard from '../components/kpi/KpiCard';
import { mockResidentFinances } from '../data/mockEconomics';

function AudienceInsightsPage() {
  const { wageVsCostTrend, wageByGroup } = mockResidentFinances;
  const wageByGroupForChart = wageByGroup.map((d) => ({ group: d.group, a: d.wage, b: d.spending }));

  const wageSeries = wageVsCostTrend.find((s) => s.name === 'Avg Wage');
  const costSeries = wageVsCostTrend.find((s) => s.name === 'Cost of Living');

  let wageTotal = 0;
  for (let i = 0; i < wageSeries.values.length; i++) {
    wageTotal += wageSeries.values[i].value;
  }
  const avgWage = Math.round(wageTotal / wageSeries.values.length);

  let costTotal = 0;
  for (let i = 0; i < costSeries.values.length; i++) {
    costTotal += costSeries.values[i].value;
  }
  const avgCost = Math.round(costTotal / costSeries.values.length);
  const savingsRate = (((avgWage - avgCost) / avgWage) * 100).toFixed(1);
  const wageCostRatio = (avgWage / avgCost).toFixed(2);

  return (
    <section>
      <h2 className="section-title">Cost of Living</h2>
      <p className="page-subtitle">How do wages compare to cost of living over time? Are some groups falling behind?</p>

      <div className="grid kpis">
        <KpiCard title="Avg Monthly Wage" value={`$${avgWage.toLocaleString()}`} />
        <KpiCard title="Avg Monthly Cost" value={`$${avgCost.toLocaleString()}`} />
        <KpiCard title="Savings Rate" value={`${savingsRate}%`} />
        <KpiCard title="Wage / Cost Ratio" value={wageCostRatio} />
      </div>

      <div className="grid charts">
        <MultiLineChart data={wageVsCostTrend} title="Avg Wage vs Cost of Living Over Time ($)" />
        <GroupedBarChart
          data={wageByGroupForChart}
          title="Avg Monthly Wage vs Spending by Income Group"
          labelA="Avg Wage"
          labelB="Avg Spending"
          colorA="#2563eb"
          colorB="#dc2626"
        />
      </div>
    </section>
  );
}

export default AudienceInsightsPage;
